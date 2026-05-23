"""Ch1 Trajectory — massively parallel solve_transfer_direct sweep.

Build on the proven 12.6 kg (0,0) bank. Search across (E, L, raan,
argp, t0) for ALL positive-mass transfers via mp.Pool parallelism.
Hungarian-assign the best set into a multi-transfer chromosome.
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


def _init_worker():
    _UDP[0] = LtlTrajectory(
        "reference/SpOC4/Challenge 1 Luna Tomato Logistics/")


def _solve_one_grid(args):
    """Search one (idE, idL) pair across raan/argp/t0 grid for best mass."""
    from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct
    idE, idL = args
    udp = _UDP[0]
    best = None
    raan_arr = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    argp_arr = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    t0_arr = [0.0, np.pi / 2, np.pi, 3 * np.pi / 2]
    for raan in raan_arr:
        for argp in argp_arr:
            for t0 in t0_arr:
                try:
                    r = solve_transfer_direct(udp, idE, idL,
                                                n_phase=16,
                                                t0=float(t0),
                                                raan=float(raan),
                                                argp=float(argp))
                except Exception:
                    continue
                if isinstance(r, tuple) and len(r) >= 4 and r[0] is not None:
                    row, mass, dv_ms, dt_d = r[0], r[1], r[2], r[3]
                    if best is None or mass > best[0]:
                        best = (float(mass), list(row), float(dv_ms),
                                 float(dt_d))
    return (idE, idL, best)


def main(n_E=20, n_L=20, n_workers=8,
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    pairs = [(idE, idL) for idE in range(n_E) for idL in range(n_L)]
    print(f"Parallel sweep: {len(pairs)} pairs × {n_workers} workers",
          flush=True)
    t_start = time.time()
    results = {}  # (idE, idL) -> (mass, row, dv_ms, dt_d)
    n_done = 0
    with mp.Pool(n_workers, initializer=_init_worker) as p:
        for (idE, idL, best) in p.imap_unordered(_solve_one_grid,
                                                    pairs, chunksize=2):
            n_done += 1
            if best is not None:
                mass, row, dv_ms, dt_d = best
                results[(idE, idL)] = best
                print(f"  ✓ ({idE},{idL}): mass={mass:.0f} kg, "
                      f"dv={dv_ms:.0f}, dt={dt_d:.1f}d", flush=True)
            if n_done % 20 == 0:
                wall = time.time() - t_start
                eta = (len(pairs) - n_done) / n_done * wall
                print(f"  ... {n_done}/{len(pairs)}, pos={len(results)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
    wall = time.time() - t_start
    print(f"\nDone in {wall:.0f}s: {len(results)}/{len(pairs)} pairs positive",
          flush=True)

    if not results:
        return {"status": "no_positive"}

    # Hungarian assignment
    from scipy.optimize import linear_sum_assignment
    mass_mat = np.zeros((n_E, n_L))
    for (idE, idL), best in results.items():
        mass_mat[idE, idL] = best[0]
    row_idx, col_idx = linear_sum_assignment(-mass_mat)
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results:
            mass, row, _, _ = results[(r, c)]
            selected.append((r, c, mass, row))
    total_mass = sum(s[2] for s in selected)
    print(f"\nHungarian: {len(selected)} transfers, total = {total_mass:.0f} kg",
          flush=True)

    # Build chromosome
    chromosome = []
    for r, c, mass, row in selected:
        chromosome.extend(row)
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)

    f = udp.fitness(chromosome)
    print(f"UDP verify: fitness={f[0]:.1f}, mass={-f[0]:.0f} kg", flush=True)
    if f[0] < 0:
        p = Path(out) / "trajectory.json"
        # Preserve old if better — but for now overwrite if any positive
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
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    print(json.dumps(main(n_E=ne, n_L=nl, n_workers=nw), indent=2))
