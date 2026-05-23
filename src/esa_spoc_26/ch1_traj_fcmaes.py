"""Ch1 Trajectory Matching — fcmaes BiteOpt/CMA-ES + Hungarian.

Per T-005: stiff geometric shooting found geometry-valid but ΔV-
pathological transfers. pygmo SADE smoke-failed. Try fcmaes
BiteOpt/CMA-ES which are different algorithm families.

Strategy:
1. Pre-compute LTL (idL, idD) → mass-cap dict (already in UDP)
2. For a subset of (idE, idL) pairs: run fcmaes BiteOpt on the 7-dim
   TransferUDP to find any positive-mass transfer.
3. Build a mass matrix (idE × idL × idD).
4. Hungarian assignment to maximize total mass.
5. Build submission chromosome.

Even ONE positive-mass transfer scores us in top-10.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch1_trajectory import (
    LtlTrajectory, V, moon_orbit_state, T as _T,
)
from esa_spoc_26.ch1_trajectory_solve import (
    _back_state, solve_departure_dv,
)
from esa_spoc_26.ch1_traj_pygmo import TransferUDP, DAY


def evaluate_transfer(udp, idE, idL, x):
    """Evaluate one (idE, idL) transfer with x = 7-dim. Return
    (fitness, mass, row_21d) where row_21d is the 21-element row for
    the UDP submission."""
    tof = x[0] * DAY / _T
    t_arr = x[1]
    arr = moon_orbit_state(udp.moon_data[idL][0],
                              udp.moon_data[idL][1],
                              udp.moon_data[idL][2], x[2], 0.0, x[3])
    dv2 = np.array(x[4:7]) / V
    S0 = arr[0]
    S1 = [arr[1][0] - dv2[0], arr[1][1] - dv2[1], arr[1][2] - dv2[2]]
    D = _back_state(S0, S1, t_arr, tof)
    if D is None:
        return 1e7, 0, None
    dep = solve_departure_dv(
        [[D[0], D[1], D[2]], [D[3], D[4], D[5]]],
        udp.earth_data[idE][0],
        udp.earth_data[idE][1],
        udp.earth_data[idE][2],
    )
    if dep is None:
        return 1e6, 0, None
    posvel0, dv0, _ = dep
    return None, None, (idE, idL, posvel0, dv0, dv2, t_arr, tof)


def fcmaes_search(udp_traj, idE, idL, n_evals=2000, popsize=20, seed=0):
    """fcmaes Bite-CMA search for ONE (idE, idL) pair. Returns
    (best_x, best_fitness)."""
    from fcmaes.optimizer import Bite_cpp, Cma_cpp, de_cma
    from fcmaes.retry import minimize as retry_minimize
    from scipy.optimize import Bounds

    udp_t = TransferUDP(udp_traj, idE, idL)
    bounds_lo, bounds_hi = udp_t.get_bounds()
    bounds = Bounds(bounds_lo, bounds_hi)

    def fitness(x):
        return udp_t.fitness(x)[0]

    # Use de_cma (DE + CMA-ES retry) — proven for global trajopt
    opt = de_cma(max_evaluations=n_evals, popsize=popsize)
    res = retry_minimize(fitness, bounds, num_retries=4,
                          optimizer=opt, workers=1)
    return res.x, res.fun


def main(n_E=20, n_L=20, n_evals=2000, out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    print(f"UDP: nE={udp.earth_data.shape[0]}, nL={udp.moon_data.shape[0]}, "
          f"LTL pairs={len(udp.ltl_dict)}", flush=True)
    print(f"Searching {n_E} × {n_L} = {n_E * n_L} (E, L) pairs", flush=True)

    # Build (idL, idD) → cld dict, get top (idL, idD) per idL by capacity
    # Actually for ANY positive-mass transfer, we need an idD. The
    # ltl_dict[(idl, idd)] = capacity. We pick best idD per idL.
    best_idD_for_idL = {}
    for (idl, idd), cld in udp.ltl_dict.items():
        if idl not in best_idD_for_idL or cld > best_idD_for_idL[idl][1]:
            best_idD_for_idL[idl] = (idd, cld)

    print(f"\nBest idD per idL identified for {len(best_idD_for_idL)} idL",
          flush=True)
    # Search subset of (E, L) pairs
    results = {}  # (idE, idL) -> (mass, x, idD)
    t_total = time.time()
    for idE in range(n_E):
        for idL in range(n_L):
            if idL not in best_idD_for_idL:
                continue
            idD, cld = best_idD_for_idL[idL]
            t0 = time.time()
            try:
                best_x, best_fit = fcmaes_search(udp, idE, idL,
                                                   n_evals=n_evals)
            except Exception as e:
                print(f"  ({idE}, {idL}): ERR {e}", flush=True)
                continue
            wall = time.time() - t0
            mass = -best_fit if best_fit < 0 else 0.0
            print(f"  ({idE}, {idL}) idD={idD}: fit={best_fit:.2f}, "
                  f"mass={mass:.0f} kg, wall={wall:.0f}s",
                  flush=True)
            if mass > 0:
                results[(idE, idL)] = (mass, best_x, idD)
    print(f"\nFound {len(results)} positive-mass transfers in "
          f"{time.time()-t_total:.0f}s", flush=True)

    if not results:
        return {"status": "no_positive_mass"}

    # Hungarian assignment on mass matrix
    print(f"\nBuilding mass matrix and Hungarian assignment...", flush=True)
    from scipy.optimize import linear_sum_assignment
    mass_mat = np.zeros((n_E, n_L))
    for (idE, idL), (mass, _, _) in results.items():
        mass_mat[idE, idL] = mass
    # Hungarian minimizes; we want to maximize → negate
    row, col = linear_sum_assignment(-mass_mat)
    selected = []
    total_mass = 0
    for r, c in zip(row, col):
        if (r, c) in results:
            mass, x, idD = results[(r, c)]
            total_mass += mass
            selected.append((r, c, idD, x, mass))
    print(f"Hungarian: selected {len(selected)} transfers, "
          f"total mass = {total_mass:.0f} kg", flush=True)

    # Build chromosome
    chromosome = []
    for idE, idL, idD, x_7d, mass in selected:
        tof = x_7d[0] * DAY / _T
        t_arr = x_7d[1]
        arr = moon_orbit_state(udp.moon_data[idL][0],
                                  udp.moon_data[idL][1],
                                  udp.moon_data[idL][2], x_7d[2], 0.0,
                                  x_7d[3])
        dv2 = np.array(x_7d[4:7]) / V
        S0 = arr[0]
        S1 = [arr[1][0] - dv2[0], arr[1][1] - dv2[1], arr[1][2] - dv2[2]]
        D = _back_state(S0, S1, t_arr, tof)
        dep = solve_departure_dv(
            [[D[0], D[1], D[2]], [D[3], D[4], D[5]]],
            udp.earth_data[idE][0],
            udp.earth_data[idE][1],
            udp.earth_data[idE][2],
        )
        posvel0, dv0, _ = dep
        row = [idE, idL, idD, t_arr - tof, *posvel0[0], *posvel0[1],
               *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), float(tof), 0.0]
        chromosome.extend(row)
    # Pad with empty rows (ide=-1) to reach dim=8400
    pad_count = (udp.dim - len(chromosome)) // 21
    for _ in range(pad_count):
        chromosome.extend([-1] + [0.0] * 20)

    # Verify
    f = udp.fitness(chromosome)
    print(f"\nUDP fitness: {f}, total mass: {-f[0]:.0f} kg", flush=True)
    if f[0] < 0:
        p = Path(out) / "trajectory.json"
        p.write_text(json.dumps([{
            "decisionVector": [float(v) for v in chromosome],
            "problem": "trajectory",
            "challenge": 1,
        }]))
        print(f"BANKED to {p}", flush=True)
        return {"status": "banked", "n_transfers": len(selected),
                "mass": float(-f[0]), "banked": str(p)}
    return {"status": "non_positive", "n_transfers": len(selected)}


if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    nl = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    nv = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    print(json.dumps(main(n_E=ne, n_L=nl, n_evals=nv), indent=2))
