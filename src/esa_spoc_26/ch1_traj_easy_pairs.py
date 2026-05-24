"""Ch1 Trajectory — focus on 96 nearly-circular-equatorial pairs.

16 Earth orbits and 6 Moon orbits have e<0.05, i<0.05 (near
circular-equatorial). 96 pairs total — these should be amenable to
Hohmann-direct transfer.

Use multi-config search per pair to find positive-mass transfers.
"""

from __future__ import annotations

import json
import sys
import time
import multiprocessing as mp
from pathlib import Path

import numpy as np

from esa_spoc_26.ch1_trajectory import LtlTrajectory


_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(
        "reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def _solve_full(args):
    """Per-pair sweep with MORE configs (10 raan × 4 argp × 6 t0)."""
    from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct
    idE, idL = args
    udp = _UDP[0]
    best = None
    raan_arr = np.linspace(0, 2 * np.pi, 10, endpoint=False)
    argp_arr = np.linspace(0, 2 * np.pi, 4, endpoint=False)
    t0_arr = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    for raan in raan_arr:
        for argp in argp_arr:
            for t0 in t0_arr:
                try:
                    r = solve_transfer_direct(udp, idE, idL, n_phase=16,
                                                t0=float(t0),
                                                raan=float(raan),
                                                argp=float(argp))
                except Exception:
                    continue
                if isinstance(r, tuple) and len(r) >= 4 and r[0] is not None:
                    row, mass, dv_ms, dt_d = r[0], r[1], r[2], r[3]
                    if best is None or mass > best[0]:
                        best = (float(mass), list(row), float(dv_ms), float(dt_d))
    return (idE, idL, best)


def main(n_workers=8):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    e_e = udp.earth_data[:, 1]
    i_e = udp.earth_data[:, 2]
    e_l = udp.moon_data[:, 1]
    i_l = udp.moon_data[:, 2]
    ee_idx = [int(i) for i in range(400) if e_e[i] < 0.05 and abs(i_e[i]) < 0.05]
    ll_idx = [int(i) for i in range(400) if e_l[i] < 0.05 and abs(i_l[i]) < 0.05]
    pairs = [(e, l) for e in ee_idx for l in ll_idx]
    print(f"Easy-pairs sweep: {len(pairs)} pairs (E={len(ee_idx)}, L={len(ll_idx)})",
          flush=True)
    print(f"  E idx: {ee_idx}")
    print(f"  L idx: {ll_idx}")
    t_start = time.time()
    results = {}
    n_done = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_solve_full, pairs, chunksize=2):
            n_done += 1
            if best is not None:
                results[(idE, idL)] = best
                print(f"  ✓ ({idE},{idL}): mass={best[0]:.0f} kg, "
                      f"dv={best[2]:.0f}, total_pos={len(results)}",
                      flush=True)
            if n_done % 10 == 0:
                wall = time.time() - t_start
                eta = (len(pairs) - n_done) / n_done * wall if n_done else 0
                print(f"  ... {n_done}/{len(pairs)}, pos={len(results)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
    wall = time.time() - t_start
    print(f"\nDone: {len(results)}/{len(pairs)} positive in {wall:.0f}s",
          flush=True)
    if not results:
        return {"status": "no_positive"}

    # Hungarian
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
            print(f"BANKED (improved {old_mass:.1f} → {-f[0]:.1f} kg)",
                  flush=True)
        else:
            print(f"Existing bank {old_mass:.1f} kg >= new {-f[0]:.1f}",
                  flush=True)
        return {"status": "evaluated", "mass": float(-f[0]),
                "n_transfers": len(selected)}
    return {"status": "non_positive"}


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(json.dumps(main(n_workers=nw), indent=2))
