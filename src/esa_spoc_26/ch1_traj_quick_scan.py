"""Ch1 Trajectory — fast (raan=0, argp=0, t0=0) scan over all 400×400.

The previous sweep with raan/argp/t0 grid was too slow. This simpler
scan just tries the SAME params (raan=0, argp=0, t0=0) that worked
for (0,0) and checks if other pairs also work. Each call ~10s; 160k
pairs / 8 workers = 200000s = 55h. So scan a SUBSET (e.g., 1000
random pairs) to find ANY working transfers.
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


def _scan_one(args):
    from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct
    idE, idL = args
    udp = _UDP[0]
    best = None
    # Try just (0,0,0) and a couple variations
    for t0 in [0.0]:
        for raan in [0.0]:
            for argp in [0.0]:
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


def main(n_pairs=2000, n_workers=8, seed=0):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    rng = np.random.default_rng(seed)
    # Generate pairs to sample
    all_pairs = [(e, l) for e in range(400) for l in range(400)]
    rng.shuffle(all_pairs)
    pairs = all_pairs[:n_pairs]
    print(f"Quick scan: {len(pairs)} random pairs (of 160k) × {n_workers} workers",
          flush=True)
    t_start = time.time()
    results = {}
    n_done = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idE, idL, best in p.imap_unordered(_scan_one, pairs, chunksize=10):
            n_done += 1
            if best is not None:
                results[(idE, idL)] = best
                print(f"  ✓ ({idE},{idL}): mass={best[0]:.0f} kg, "
                      f"dv={best[2]:.0f}, n_pos_total={len(results)}",
                      flush=True)
            if n_done % 50 == 0:
                wall = time.time() - t_start
                rate = n_done / wall if wall else 0
                eta = (len(pairs) - n_done) / rate if rate else 0
                print(f"  ... {n_done}/{len(pairs)} done, pos={len(results)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
    wall = time.time() - t_start
    print(f"\nScan done in {wall:.0f}s: {len(results)}/{len(pairs)} positive",
          flush=True)
    if not results:
        return {"status": "no_positive"}

    # Hungarian on the partial mass matrix
    from scipy.optimize import linear_sum_assignment
    # Find max idE and idL
    max_e = max(k[0] for k in results) + 1
    max_l = max(k[1] for k in results) + 1
    mass_mat = np.zeros((max_e, max_l))
    for (e, l), best in results.items():
        mass_mat[e, l] = best[0]
    row_idx, col_idx = linear_sum_assignment(-mass_mat)
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results:
            selected.append((r, c, results[(r, c)]))
    total = sum(s[2][0] for s in selected)
    print(f"\nHungarian: {len(selected)} transfers, total mass = {total:.0f} kg",
          flush=True)

    chromosome = []
    for r, c, best in selected:
        chromosome.extend(best[1])
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)
    f = udp.fitness(chromosome)
    print(f"UDP verify: fitness={f[0]:.1f}, mass={-f[0]:.0f} kg", flush=True)
    if f[0] < 0:
        p = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
        # Read existing for comparison
        try:
            old = json.load(open(p))
            old_f = udp.fitness(old[0]["decisionVector"])
            old_mass = -old_f[0]
            print(f"Existing bank: {old_mass:.1f} kg", flush=True)
            if -f[0] > old_mass + 0.5:
                p.write_text(json.dumps([{
                    "decisionVector": [float(v) for v in chromosome],
                    "problem": "trajectory",
                    "challenge": "spoc-4-luna-tomato-logistics",
                }]))
                print(f"BANKED (better): {p}, mass={-f[0]:.1f}", flush=True)
        except Exception:
            p.write_text(json.dumps([{
                "decisionVector": [float(v) for v in chromosome],
                "problem": "trajectory",
                "challenge": "spoc-4-luna-tomato-logistics",
            }]))
            print(f"BANKED: {p}, mass={-f[0]:.1f}", flush=True)
        return {"status": "banked", "mass": float(-f[0]),
                "n_transfers": len(selected)}
    return {"status": "non_positive"}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    print(json.dumps(main(n_pairs=n, n_workers=nw), indent=2))
