"""Per-pair differential evolution polish on full continuous chromosome.

For each banked transfer (idE, idL, idD), run scipy DE on 12 params:
- raan_e, argp_e, ea_dep, t0  (4 angles)
- dv0[3], dv1[3]  (6 burn components)
- T1, T2  (2 TOFs)

dv2 auto-computed via solve_arrival_eccentric. Objective: -mass.

This is GLOBAL optimization — doesn't need good seed. Will find any
basin including 3-impulse plane-change-at-apogee architectures
automatically.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
from scipy.optimize import differential_evolution
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, earth_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def evaluate_row(row, udp):
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    return -udp.fitness(chr_padded)[0]


def _de_eval(p, idE, idL, current_mass):
    """Evaluate DE candidate: returns -mass (DE minimizes)."""
    udp = _UDP[0]
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    raan_e, argp_e, ea_dep, t0 = p[0], p[1], p[2], p[3]
    dv0 = p[4:7]
    dv1 = p[7:10]
    T1, T2 = max(p[10], 0.05), max(p[11], 0.0)

    if T1 + T2 > 50:  # > ~217 days total → reject
        return -current_mass + 0.1

    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return -current_mass + 0.1
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return -current_mass + 0.1
    dv2, _ = dv2_res
    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0.tolist(), *dv1.tolist(), *dv2.tolist(), T1, T2]
    mass = evaluate_row(row, udp)
    if mass <= 0:
        return -current_mass + 0.1
    return -mass


def _task(args):
    idx, current_row, current_mass = args
    udp = _UDP[0]
    idE = int(current_row[0])
    idL = int(current_row[1])
    idD = int(current_row[2])

    # Decision variable bounds
    bounds = [
        (0, 2 * np.pi),    # raan_e
        (0, 2 * np.pi),    # argp_e
        (0, 2 * np.pi),    # ea_dep
        (0, 2 * np.pi),    # t0
        (-3.0, 3.0),       # dv0_x
        (-3.0, 3.0),       # dv0_y
        (-3.0, 3.0),       # dv0_z
        (-1.5, 1.5),       # dv1_x
        (-1.5, 1.5),       # dv1_y
        (-1.5, 1.5),       # dv1_z
        (0.5, 8.0),        # T1 (nondim, 2-35 days)
        (0.0, 3.0),        # T2 (0-13 days)
    ]

    try:
        result = differential_evolution(
            lambda p: _de_eval(p, idE, idL, current_mass),
            bounds, strategy='best1bin', popsize=15, maxiter=40,
            mutation=(0.5, 1.5), recombination=0.7, seed=idx,
            polish=False, disp=False, tol=1e-3,
        )
    except Exception:
        return idx, current_row, current_mass, current_mass

    new_mass = -result.fun if result.fun < -0.5 else current_mass
    if new_mass <= current_mass + 0.5:
        return idx, current_row, current_mass, current_mass

    # Re-build the row from optimum
    p = result.x
    raan_e, argp_e, ea_dep, t0 = p[0], p[1], p[2], p[3]
    dv0 = p[4:7]
    dv1 = p[7:10]
    T1, T2 = max(p[10], 0.05), max(p[11], 0.0)
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, t0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                        [T1, T2])
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return idx, current_row, current_mass, current_mass
    dv2, _ = dv2_res
    new_row = [idE, idL, idD, t0, *pv0[0], *pv0[1],
                *dv0.tolist(), *dv1.tolist(), *dv2.tolist(), T1, T2]
    verified_mass = evaluate_row(new_row, udp)
    if verified_mass > current_mass + 0.5:
        return idx, new_row, verified_mass, current_mass
    return idx, current_row, current_mass, current_mass


def main(n_workers=8):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
    bank = json.load(open(bank_path))
    dv = bank[0]["decisionVector"]
    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            row = dv[i:i + 21]
            m = evaluate_row(row, udp)
            active.append((i // 21, row, m))
    baseline = -udp.fitness(dv)[0]
    print(f"{len(active)} transfers, baseline {baseline:.0f}kg", flush=True)
    print(f"Estimated wall: ~{len(active) * 60 / n_workers / 60:.0f} min", flush=True)

    t0 = time.time()
    polished = list(dv)
    n_imp = 0
    total_gain = 0
    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _task, active, chunksize=1):
            gain = new_mass - orig_mass
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                n_imp += 1
                total_gain += gain
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg "
                      f"(+{gain:.0f})", flush=True)
                if n_imp % 3 == 0:
                    bank_path.write_text(json.dumps([{
                        "decisionVector": [float(v) for v in polished],
                        "problem": "trajectory",
                        "challenge": "spoc-4-luna-tomato-logistics"}]))
    f_p = -udp.fitness(polished)[0]
    print(f"\n{n_imp}/{len(active)} improved, +{total_gain:.0f}kg "
          f"in {time.time() - t0:.0f}s", flush=True)
    if f_p > baseline + 0.5:
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics"}]))
        print(f"BANKED: {baseline:.0f} → {f_p:.0f}kg", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
