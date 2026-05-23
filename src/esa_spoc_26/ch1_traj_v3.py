"""Ch1 Trajectory v3 — Lambert-seeded forward shooting with closest-approach LOI.

The proven pattern of solve_transfer_direct (12.6 kg @ (0,0)):
  Hohmann seed → forward propagate BCP → closest-approach LOI

This v3 uses LAMBERT seed instead of Hohmann. Lambert gives a much
better initial velocity (~3.2 km/s dv1 vs Hohmann's ~3.5+ extra for
misalignment), so the forward propagation should land MUCH closer to
the Moon orbit, requiring a smaller LOI burn.

Pipeline:
1. Lambert grid search → best (raan_e, argp_e, ea_e, raan_m, argp_m,
   ea_m, tof, dv1).
2. BCP-synodic forward propagation with dv0 = dv1/V.
3. Scan tof_scale to find closest approach to Moon orbit radius aM.
4. If close enough: solve_arrival_dv (LOI burn dv2).
5. Compute UDP fitness; if mass > 0, accept.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_traj_lambert import (
    lambert_dv, moon_inertial_pos_vel,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv, _r_moon


def solve_one(udp, idE, idL, verbose=False):
    """Lambert-seeded + forward BCP + closest-approach LOI pipeline."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]

    # 1) Lambert grid search
    best_lambert = None
    raan_e_arr = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    argp_e_arr = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    ea_e_arr = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    ea_m_arr = [0.0, np.pi / 2, np.pi, 3 * np.pi / 2]
    for re_ in raan_e_arr:
        for ae_ in argp_e_arr:
            for ee_ in ea_e_arr:
                for em_ in ea_m_arr:
                    for tof_d in [5, 10, 20, 30, 50]:
                        r = lambert_dv(idE, idL, re_, ae_, ee_,
                                          0.0, 0.0, em_, 0.0, tof_d * 86400,
                                          aE, eE, iE, aM, eM, iM)
                        if r is None:
                            continue
                        if best_lambert is None or r["total"] < best_lambert["total"]:
                            best_lambert = {**r, "raan_e": re_, "argp_e": ae_,
                                             "ea_e": ee_, "tof_d": tof_d}
    if best_lambert is None:
        return None

    if verbose:
        print(f"  Lambert: total={best_lambert['total']:.0f} m/s, "
              f"tof={best_lambert['tof_d']}d", flush=True)

    # 2) Forward BCP with Lambert dv0 seed
    pv0 = earth_orbit_state(aE, eE, iE, best_lambert["raan_e"],
                              best_lambert["argp_e"],
                              best_lambert["ea_e"])
    dv0 = (best_lambert["dv1"] / V).tolist()
    tof_si = best_lambert["tof_d"] * 86400
    tof_seed = tof_si / T

    def closest(scale_tof):
        pv = propagate(pv0, 0.0, [dv0, [0, 0, 0], [0, 0, 0]],
                         [scale_tof * tof_seed, 0.0])
        if len(pv) == 0:
            return None
        return pv, abs(_r_moon(pv) - aM)

    # 3) Coarse scan + refine on closest-approach
    cand = [(s, closest(s)) for s in np.linspace(0.5, 2.0, 16)]
    cand = [(s, c) for s, c in cand if c is not None]
    if not cand:
        return None
    s_best = min(cand, key=lambda z: z[1][1])[0]
    if verbose:
        print(f"  Closest scan: s={s_best:.3f}, err={dict(cand)[s_best][1]:.2e}",
              flush=True)
    try:
        sol = least_squares(
            lambda s: (closest(s[0])[1] if closest(s[0]) else 1e9),
            [s_best], bounds=([0.3], [2.5]), xtol=1e-10, max_nfev=40,
        )
    except Exception:
        return None
    c = closest(sol.x[0])
    if c is None:
        return None
    pv_a, err = c
    if err > aM * 1e-2:  # 1% of Moon orbit radius
        if verbose:
            print(f"  Endpoint too far from Moon (err={err:.2e} m)",
                  flush=True)
        return None

    # 4) LOI burn
    dv2_res = solve_arrival_dv(pv_a, aM, eM, iM)
    if dv2_res is None:
        if verbose:
            print(f"  LOI failed; endpoint not near LLO precisely")
        return None
    dv2, _ = dv2_res
    tof = sol.x[0] * tof_seed
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
    dt_d = tof * T * pk.SEC2DAY
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
           *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    f = udp.fitness(row)[0]
    if f < 0:
        mass = -f
        return {"row": row, "mass": float(mass), "dv_ms": float(dv_ms),
                "dt_d": float(dt_d)}
    return None


def main(n_pairs=10):
    """Test on first n_pairs (E, L) combinations."""
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    print(f"Lambert v3: testing first {n_pairs} (E, L) pairs", flush=True)
    results = []
    t_start = time.time()
    for idE in range(n_pairs):
        for idL in range(n_pairs):
            t0 = time.time()
            res = solve_one(udp, idE, idL, verbose=False)
            wall = time.time() - t0
            if res:
                results.append((idE, idL, res))
                print(f"  ✓ ({idE},{idL}): mass={res['mass']:.0f} kg, "
                      f"dv={res['dv_ms']:.0f}, dt={res['dt_d']:.1f}d, "
                      f"wall={wall:.0f}s", flush=True)
    print(f"\nTotal: {len(results)}/{n_pairs**2} positive-mass in "
          f"{time.time()-t_start:.0f}s", flush=True)
    if not results:
        return {"status": "no_positive"}
    # Build chromosome
    from scipy.optimize import linear_sum_assignment
    mass_mat = np.zeros((n_pairs, n_pairs))
    for (idE, idL, res) in results:
        mass_mat[idE, idL] = res["mass"]
    row_idx, col_idx = linear_sum_assignment(-mass_mat)
    selected = [(r, c, dict([(rr, res) for (rr, _, res) in
                              [(r2, c2, res2) for (r2, c2, res2) in
                               results if r2 == r and c2 == c]
                              if rr == r])[r])
                 for r, c in zip(row_idx, col_idx)
                 if mass_mat[r, c] > 0]
    # Simpler: re-build via dict
    results_dict = {(idE, idL): res for (idE, idL, res) in results}
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results_dict:
            selected.append((r, c, results_dict[(r, c)]))
    total_mass = sum(s[2]["mass"] for s in selected)
    print(f"Hungarian: {len(selected)} transfers, total mass = {total_mass:.0f} kg",
          flush=True)
    # Build chromosome
    chromosome = []
    for (idE, idL, res) in selected:
        chromosome.extend(res["row"])
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)
    f = udp.fitness(chromosome)
    print(f"\nUDP verify: fitness={f[0]:.1f}, total mass={-f[0]:.0f} kg",
          flush=True)
    if f[0] < 0:
        p = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
        p.write_text(json.dumps([{
            "decisionVector": [float(v) for v in chromosome],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        print(f"BANKED: {p}", flush=True)
        return {"status": "banked", "mass": float(-f[0]),
                "n_transfers": len(selected)}
    return {"status": "non_positive"}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(json.dumps(main(n_pairs=n), indent=2))
