"""Ch1 Trajectory — analytically-targeted (raan, argp) + parallel sweep.

For each (idE, idL): compute the (raan_E, argp_E) that aligns the
Hohmann apoapsis toward the Moon's expected arrival position. This
analytical seed is far better than blind (raan=0, argp=0) for all
pairs.

Hohmann from Earth orbit at radius r_E to apoapsis at Moon distance L:
- tof_Hohmann = π * sqrt(a_t^3 / mu_E), a_t = (r_E + L) / 2
- Moon's inertial angle at arrival = N_moon * tof_Hohmann
- Spacecraft apoapsis at orbital angle θ_E + π (true longitude)
- For apoapsis to align with Moon: θ_E = N_moon * tof_Hohmann - π

For inclined orbits, raan_E sets the line-of-nodes. The apoapsis
direction projected onto equator plane = θ_E.

For circular (e=0): θ_E = raan_E + ea_E. So set raan_E + ea_E = θ_E.
With argp_E = 0 and raan_E free, pick ea_E = θ_E - raan_E.

Strategy: set raan_E = 0 (default plane), argp_E = 0, compute ea_E
analytically. Then call solve_transfer_direct with n_phase=4
centered around the predicted ea_E.
"""

from __future__ import annotations

import json
import sys
import time
import multiprocessing as mp
from pathlib import Path

import numpy as np

from esa_spoc_26.ch1_trajectory import (
    L, T, MU_EARTH, MU_MOON, LtlTrajectory,
)


N_MOON_SI = np.sqrt((MU_EARTH + MU_MOON) / L**3)


def predict_optimal_ea_e(udp, idE):
    """Predict the optimal departure true anomaly for orbit idE."""
    aE = udp.earth_data[idE][0]
    a_t = (aE + L) / 2
    tof_Hohmann_si = np.pi * np.sqrt(a_t**3 / MU_EARTH)
    moon_angle_at_arrival = N_MOON_SI * tof_Hohmann_si
    # In inertial: spacecraft apoapsis position vector = -r_dep_unit * a_apo
    # For circular orbit at raan=0, argp=0: position at ea = (cos(ea), sin(ea), ...)
    # We want position at ea + π (apoapsis) to be in direction of moon_angle
    # → ea + π = moon_angle_at_arrival → ea = moon_angle - π (mod 2π)
    return float(moon_angle_at_arrival - np.pi) % (2 * np.pi)


_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(
        "reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def _solve_targeted(args):
    """Targeted solve for (idE, idL) with analytical (raan, argp, ea)."""
    from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct
    idE, idL = args
    udp = _UDP[0]
    best = None
    # Analytical ea_E target
    ea_target = predict_optimal_ea_e(udp, idE)
    # Also try ±π/4, ±π/8 around target (the prediction may be off)
    # plus a few fallback configurations
    configs = []
    # Per-Earth-orbit: try predicted ea + perturbations
    # Different raan / argp / t0 combos
    for raan in [0.0, np.pi / 2]:
        for argp in [0.0]:
            for t0 in [0.0, np.pi / 2, np.pi]:
                configs.append((raan, argp, t0))
    for raan, argp, t0 in configs:
        try:
            r = solve_transfer_direct(udp, idE, idL, n_phase=16,
                                        t0=t0, raan=raan, argp=argp)
        except Exception:
            continue
        if isinstance(r, tuple) and len(r) >= 4 and r[0] is not None:
            row, mass, dv_ms, dt_d = r[0], r[1], r[2], r[3]
            if best is None or mass > best[0]:
                best = (float(mass), list(row), float(dv_ms), float(dt_d))
    return (idE, idL, best)


def main(n_pairs=400, seed=0, n_workers=8):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    rng = np.random.default_rng(seed)
    # Random sample of pairs
    all_pairs = [(e, l) for e in range(400) for l in range(400)]
    rng.shuffle(all_pairs)
    pairs = all_pairs[:n_pairs]
    # ALWAYS include known-working (0, 0) for sanity
    pairs = [(0, 0)] + [p for p in pairs if p != (0, 0)]
    pairs = pairs[:n_pairs + 1]
    print(f"Targeted sweep: {len(pairs)} pairs × {n_workers} workers",
          flush=True)
    t_start = time.time()
    results = {}
    n_done = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve_targeted,
                                                  pairs, chunksize=4):
            n_done += 1
            if best is not None:
                results[(idE, idL)] = best
                print(f"  ✓ ({idE},{idL}): mass={best[0]:.0f} kg, "
                      f"dv={best[2]:.0f}, total_pos={len(results)}",
                      flush=True)
            if n_done % 25 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall else 1
                eta = (len(pairs) - n_done) / rate
                print(f"  ... {n_done}/{len(pairs)} done, pos={len(results)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
    wall = time.time() - t_start
    print(f"\nDone: {len(results)}/{len(pairs)} positive in {wall:.0f}s",
          flush=True)

    if not results:
        return {"status": "no_positive"}

    # Hungarian assignment
    from scipy.optimize import linear_sum_assignment
    max_e = max(k[0] for k in results) + 1
    max_l = max(k[1] for k in results) + 1
    mass_mat = np.zeros((max_e, max_l))
    for (e, l), best in results.items():
        mass_mat[e, l] = best[0]
    row_idx, col_idx = linear_sum_assignment(-mass_mat)
    selected = [(r, c, results[(r, c)]) for r, c in zip(row_idx, col_idx)
                  if (r, c) in results]
    total = sum(s[2][0] for s in selected)
    print(f"Hungarian: {len(selected)} transfers, total = {total:.0f} kg",
          flush=True)

    # Build chromosome
    chromosome = []
    for r, c, best in selected:
        chromosome.extend(best[1])
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)
    f = udp.fitness(chromosome)
    print(f"UDP verify: fitness={f[0]:.1f}, mass={-f[0]:.0f} kg",
          flush=True)
    if f[0] < 0:
        p = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
        # Compare to existing bank
        try:
            old = json.load(open(p))
            old_f = udp.fitness(old[0]["decisionVector"])
            old_mass = -old_f[0]
        except Exception:
            old_mass = 0
        if -f[0] > old_mass + 0.5:
            p.write_text(json.dumps([{
                "decisionVector": [float(v) for v in chromosome],
                "problem": "trajectory",
                "challenge": "spoc-4-luna-tomato-logistics",
            }]))
            print(f"BANKED (improved from {old_mass:.1f} → {-f[0]:.1f} kg): {p}",
                  flush=True)
        else:
            print(f"Existing bank {old_mass:.1f} kg > new {-f[0]:.1f} kg; not updating",
                  flush=True)
        return {"status": "evaluated", "mass": float(-f[0]),
                "n_transfers": len(selected)}
    return {"status": "non_positive"}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    print(json.dumps(main(n_pairs=n, n_workers=nw), indent=2))
