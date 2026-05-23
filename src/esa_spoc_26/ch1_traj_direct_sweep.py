"""Ch1 Trajectory — sweep solve_transfer_direct over many (E, L, raan, argp, t0).

After diagnostic confirmed solve_transfer_direct finds POSITIVE mass at
(0,0): 12.6 kg, this sweeps over more (E, L) pairs and the missing
parameters (raan, argp, t0/Sun phase).

Each Earth orbit may need a different raan/argp pairing for the
transfer to reach the Moon orbit.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch1_trajectory import LtlTrajectory
from esa_spoc_26.ch1_trajectory_solve import solve_transfer_direct


def sweep_pair(udp, idE, idL, n_phase=12, raan_grid=None, argp_grid=None,
                t0_grid=None):
    """For (idE, idL), sweep raan, argp, t0 to find best positive-mass
    transfer."""
    if raan_grid is None:
        raan_grid = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    if argp_grid is None:
        argp_grid = np.linspace(0, 2 * np.pi, 6, endpoint=False)
    if t0_grid is None:
        t0_grid = [0.0, np.pi, np.pi / 2, 3 * np.pi / 2]
    best = None  # (mass, row, dv_ms, dt_d, raan, argp, t0)
    for raan in raan_grid:
        for argp in argp_grid:
            for t0 in t0_grid:
                try:
                    r = solve_transfer_direct(udp, idE, idL,
                                                n_phase=n_phase, t0=t0,
                                                raan=float(raan),
                                                argp=float(argp))
                except Exception:
                    continue
                if isinstance(r, tuple) and len(r) >= 4 and r[0] is not None:
                    row, mass, dv_ms, dt_d = r[0], r[1], r[2], r[3]
                    if best is None or mass > best[0]:
                        best = (mass, row, dv_ms, dt_d, float(raan),
                                float(argp), float(t0))
    return best


def main(n_E=20, n_L=20, n_phase=12, out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    print(f"Sweep: {n_E} × {n_L} (E, L) pairs × raan/argp/t0 grid",
          flush=True)
    results = {}
    t_start = time.time()
    for idE in range(n_E):
        for idL in range(n_L):
            t0 = time.time()
            best = sweep_pair(udp, idE, idL, n_phase=n_phase)
            wall = time.time() - t0
            if best is not None:
                mass, row, dv_ms, dt_d, raan, argp, t0_ = best
                results[(idE, idL)] = best
                print(f"  ✓ ({idE},{idL}): mass={mass:.0f} kg, "
                      f"dv={dv_ms:.0f}, dt={dt_d:.1f}d, "
                      f"raan={raan:.2f}, argp={argp:.2f}, t0={t0_:.2f}, "
                      f"wall={wall:.0f}s", flush=True)
            else:
                if (idE * n_L + idL) % 10 == 0:
                    print(f"  ({idE},{idL}): no mass, wall={wall:.0f}s",
                          flush=True)
    print(f"\nTotal positive: {len(results)}/{n_E * n_L} pairs "
          f"in {time.time()-t_start:.0f}s", flush=True)

    if not results:
        return {"status": "no_positive"}

    # Hungarian assignment to maximize total mass
    print(f"\nHungarian assignment over {len(results)} positive-mass pairs",
          flush=True)
    from scipy.optimize import linear_sum_assignment
    mass_mat = np.zeros((n_E, n_L))
    for (idE, idL), best in results.items():
        mass_mat[idE, idL] = best[0]
    row_idx, col_idx = linear_sum_assignment(-mass_mat)
    selected = []
    total_mass = 0
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results:
            mass, row, dv_ms, dt_d, _, _, _ = results[(r, c)]
            total_mass += mass
            selected.append((r, c, row))
    print(f"Selected {len(selected)} transfers, total mass = "
          f"{total_mass:.0f} kg", flush=True)

    # Build chromosome (8400 dim)
    chromosome = []
    for r, c, row21 in selected:
        chromosome.extend(row21)
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)

    # Verify via UDP
    f = udp.fitness(chromosome)
    print(f"\nUDP fitness: {f}, total mass: {-f[0]:.0f} kg", flush=True)
    if f[0] < 0:
        p = Path(out) / "trajectory.json"
        p.write_text(json.dumps([{
            "decisionVector": [float(v) for v in chromosome],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        print(f"BANKED to {p}", flush=True)
        return {"status": "banked", "n_transfers": len(selected),
                "mass": float(-f[0])}
    return {"status": "non_positive", "n_transfers": len(selected)}


if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    np_ = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    print(json.dumps(main(n_E=ne, n_L=nl, n_phase=np_), indent=2))
