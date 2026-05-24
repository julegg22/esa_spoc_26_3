"""Production Ch1 trajectory sweep with eccentric-orbit fix.

Strategy:
1. Pre-filter: pick top 2000 (idE, idL) pairs by Hohmann theoretical mass
   (computed naïvely, ignoring inclination changes)
2. Parallel solve via Lambert+3D-DC+solve_arrival_eccentric (8 workers)
3. Hungarian assignment on valid (idE, idL) pairs to maximize total mass
   (subject to unique idE, idL constraints)
4. For each selected pair: pick best idD (high cld, unique)
5. Build chromosome, verify via UDP fitness, bank.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_traj_proper_v2 import lambert_dv0
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric
from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, LtlTrajectory, earth_orbit_state,
    moon_orbit_state, propagate,
)
from scipy.optimize import least_squares, linear_sum_assignment
import pykep as pk

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def _try_transfer(udp, pv0, pv_tgt, aE, eE, iE, aL, eL, iL, tof,
                   idE, idL):
    """Lambert + 3-D DC + eccentric-aware solve_arrival."""
    dv0_seed = lambert_dv0(pv0, pv_tgt, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) > 15:
        return None

    def residual(p):
        pv_a = propagate(pv0, 0.0, [p.tolist(), [0, 0, 0], [0, 0, 0]],
                          [tof, 0.0])
        if len(pv_a) == 0:
            return [100.0] * 3
        return [pv_a[0][0] - pv_tgt[0][0],
                pv_a[0][1] - pv_tgt[0][1],
                pv_a[0][2] - pv_tgt[0][2]]
    try:
        sol = least_squares(residual, dv0_seed, method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=50)
    except Exception:
        return None
    dv0 = sol.x
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), [0, 0, 0], [0, 0, 0]],
                        [tof, 0.0])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(), tof, 0.0]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
    return mass, row, dv_ms


def _solve(args):
    """Per-pair solver: grid search over (ea_dep, ea_arr, TOF), best valid."""
    idE, idL = args
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None
    for tof_d in (5, 8, 11):
        tof = tof_d * 86400.0 / T
        for ea_dep in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
            for ea_arr in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                pv_tgt = moon_orbit_state(aL, eL, iL, 0.0, 0.0, ea_arr)
                res = _try_transfer(udp, pv0, pv_tgt, aE, eE, iE,
                                      aL, eL, iL, tof, idE, idL)
                if res is not None and (best is None or res[0] > best[0]):
                    best = res
    return idE, idL, best


def hohmann_lower_bound(aE, aL):
    """Theoretical mass for ideal Hohmann from circular aE to circular aL."""
    MU_E = pk.MU_EARTH
    MU_M = 4.902800066e12
    R_MOON = 384400e3
    a_trans = (aE + R_MOON) / 2
    v_circ = np.sqrt(MU_E / aE)
    v_peri = np.sqrt(MU_E * (2 / aE - 1 / a_trans))
    dv0 = v_peri - v_circ
    v_apo = np.sqrt(MU_E * (2 / R_MOON - 1 / a_trans))
    v_moon = np.sqrt(MU_E / R_MOON)
    v_inf = v_moon - v_apo
    v_arrive = np.sqrt(v_inf**2 + 2 * MU_M / aL)
    v_llo = np.sqrt(MU_M / aL)
    dv2 = v_arrive - v_llo
    return max(0, 5000 * np.exp(-(dv0 + dv2) / (311 * 9.80665)) - 500)


def main(n_pairs=2000, n_workers=8):
    udp = LtlTrajectory(ROOT)
    aE = udp.earth_data[:, 0]
    aL = udp.moon_data[:, 0]
    eL = udp.moon_data[:, 1]

    # Pre-filter: compute Hohmann theoretical for ALL 160k pairs,
    # sort by theoretical mass, take top n_pairs
    print(f"Pre-computing Hohmann theoretical mass matrix...", flush=True)
    flat = []
    for i in range(400):
        for j in range(400):
            m = hohmann_lower_bound(aE[i], aL[j])
            # Bonus for eccentric Moon orbits (wider window)
            m_adjusted = m * (1 + eL[j])  # crude heuristic
            flat.append((m_adjusted, i, j))
    flat.sort(reverse=True)
    pairs = [(i, j) for m, i, j in flat[:n_pairs]]
    print(f"Selected top {n_pairs} pairs by adjusted Hohmann mass "
          f"(top: {flat[0][0]:.0f} kg, #{n_pairs}: {flat[n_pairs-1][0]:.0f} kg)",
          flush=True)

    # Parallel solve
    print(f"\nLaunching parallel solver ({n_workers} workers, {len(pairs)} pairs)...",
          flush=True)
    t_start = time.time()
    results = {}  # (idE, idL) -> (mass, row, dv_ms)
    n_done = 0
    n_valid = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve, pairs, chunksize=2):
            n_done += 1
            if best is not None:
                n_valid += 1
                results[(idE, idL)] = best
            if n_done % 10 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall > 0 else 0
                eta = (len(pairs) - n_done) / rate if rate > 0 else 0
                # Show top-3 masses seen so far
                top_masses = sorted([v[0] for v in results.values()],
                                     reverse=True)[:3]
                top_str = ",".join(f"{m:.0f}" for m in top_masses)
                print(f"  [{n_done:4d}/{len(pairs)}] valid={n_valid} "
                      f"top=[{top_str}]kg wall={wall:.0f}s ETA={eta:.0f}s",
                      flush=True)
    wall = time.time() - t_start
    print(f"\nSolved {n_done} pairs in {wall:.0f}s, {n_valid} valid", flush=True)

    # Save all results to disk for re-use in rebank/extended sweep
    results_path = Path("/home/julian/Projects/esa_spoc_26_3/runs/ch1/sweep_results.json")
    serializable = {f"{k[0]},{k[1]}": [v[0], list(v[1]), v[2]]
                     for k, v in results.items()}
    results_path.write_text(json.dumps(serializable))
    print(f"Sweep results saved: {results_path}", flush=True)

    if n_valid == 0:
        print("NO valid transfers found — abort", flush=True)
        return

    # Hungarian: maximize total mass with unique idE, idL constraints
    print(f"\nHungarian assignment on {n_valid}-pair mass matrix...", flush=True)
    # Build mass matrix indexed by [idE, idL]
    M = np.zeros((400, 400))
    for (idE, idL), (mass, _, _) in results.items():
        M[idE, idL] = mass
    row_idx, col_idx = linear_sum_assignment(-M)  # negate: maximize
    # Filter to assignments with actual mass > 0
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results:
            selected.append((r, c, results[(r, c)]))
    total_hungarian = sum(s[2][0] for s in selected)
    print(f"Hungarian: {len(selected)} transfers, total = {total_hungarian:.0f} kg",
          flush=True)

    # Assign idD uniquely — for each transfer (idE, idL), pick best available idD
    # by cld * remaining_time. Greedy: process transfers by descending mass,
    # pick highest-cld idD not yet used.
    print(f"\nAssigning idD (greedy by cld)...", flush=True)
    selected.sort(key=lambda s: -s[2][0])
    used_d = set()
    final = []
    for idE, idL, (mass, row, dv_ms) in selected:
        # Find best idD for this idL (highest cld * (HORIZON - dt))
        best_d, best_cap = None, 0
        dt = (row[19] + row[20]) * T * pk.SEC2DAY
        for idd in range(400):
            if idd in used_d:
                continue
            if (idL, idd) not in udp.ltl_dict:
                continue
            cld = udp.ltl_dict[(idL, idd)]
            cap = cld * (200 - dt)
            if cap > best_cap:
                best_cap = cap
                best_d = idd
        if best_d is None:
            continue
        used_d.add(best_d)
        # Update row's idD
        new_row = list(row)
        new_row[2] = best_d
        final.append((idE, idL, best_d, mass, new_row))

    # Build chromosome and verify
    chromosome = []
    for idE, idL, idD, mass, row in final:
        chromosome.extend(row)
    pad = (udp.dim - len(chromosome)) // 21
    for _ in range(pad):
        chromosome.extend([-1] + [0.0] * 20)

    f_total = udp.fitness(chromosome)[0]
    print(f"\nUDP verify: fitness={f_total:.1f}, total mass={-f_total:.0f} kg",
          flush=True)
    print(f"  {len(final)} transfers banked", flush=True)

    if f_total < 0:
        bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
        # Compare to existing
        try:
            old = json.load(open(bank_path))
            old_mass = -udp.fitness(old[0]["decisionVector"])[0]
        except Exception:
            old_mass = 0.0
        if -f_total > old_mass + 0.5:
            bank_path.write_text(json.dumps([{
                "decisionVector": [float(v) for v in chromosome],
                "problem": "trajectory",
                "challenge": "spoc-4-luna-tomato-logistics",
            }]))
            print(f"BANKED: {old_mass:.0f} → {-f_total:.0f} kg "
                  f"({len(final)} transfers)", flush=True)
        else:
            print(f"Existing bank {old_mass:.0f} kg >= new {-f_total:.0f}",
                  flush=True)


if __name__ == "__main__":
    import sys
    n_pairs = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    n_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    main(n_pairs=n_pairs, n_workers=n_workers)
