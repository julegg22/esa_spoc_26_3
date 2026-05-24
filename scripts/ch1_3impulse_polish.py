"""Tier 1B: 3-impulse polish — add mid-course dv1 burn.

For each banked transfer, attempt to find dv1 ≠ 0 (mid-course correction)
that reduces total dv. 7-var optimization: (dv0[3], dv1[3], T1_frac).

Strategy:
- Keep pv0, T_total = T1+T2 fixed from the 2-impulse solution.
- Optimize the dv1 burn timing (T1 fraction) and direction/magnitude.
- Recompute dv2 via solve_arrival_eccentric.

Expected gain: -200 to -500 m/s on hard inclined pairs → +20-50% mass.
"""
import sys
import time
import json
import numpy as np
import multiprocessing as mp
from pathlib import Path
from scipy.optimize import minimize
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import (
    L, T, V, LtlTrajectory, propagate,
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


def polish_3impulse(row, idE, idL):
    """Try adding dv1 mid-course correction to a 2-impulse trajectory.

    Args:
        row: 21-element chromosome from 2-impulse bank.

    Returns:
        (new_row, new_mass, orig_mass)
    """
    udp = _UDP[0]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = [row[4:7], row[7:10]]
    t0_val = row[3]
    orig_dv0 = np.array(row[10:13])
    orig_T1 = row[19]
    orig_T2 = row[20]
    T_total = orig_T1 + orig_T2
    orig_mass = evaluate_row(row, udp)

    # 7 vars: dv0_x, dv0_y, dv0_z, dv1_x, dv1_y, dv1_z, T1_frac
    def neg_mass(x):
        dv0 = x[:3]
        dv1 = x[3:6]
        T1_frac = np.clip(x[6], 0.1, 0.9)
        T1 = T1_frac * T_total
        T2 = (1 - T1_frac) * T_total
        pv_arr = propagate(pv0, t0_val,
                            [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                            [T1, T2])
        if len(pv_arr) == 0:
            return 1e3
        dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if dv2_res is None:
            return 1e3
        dv2, _ = dv2_res
        new_row = list(row)
        new_row[10:13] = dv0.tolist()
        new_row[13:16] = dv1.tolist()
        new_row[16:19] = dv2.tolist()
        new_row[19] = T1
        new_row[20] = T2
        mass = evaluate_row(new_row, udp)
        if mass <= 0:
            return 1e3
        return -mass

    # Seed: original 2-impulse (T1_frac=1.0 → T2=0; we use 0.5 to start)
    x0 = np.array([
        orig_dv0[0], orig_dv0[1], orig_dv0[2],
        0.0, 0.0, 0.0,  # dv1 starts at 0 (degenerate to 2-impulse)
        0.5,  # T1_frac
    ])
    try:
        sol = minimize(neg_mass, x0, method="Nelder-Mead",
                        options={"xatol": 1e-4, "fatol": 0.5,
                                  "maxiter": 200, "disp": False})
    except Exception:
        return row, orig_mass, orig_mass

    if sol.fun >= 1e3:
        return row, orig_mass, orig_mass

    dv0_opt = sol.x[:3]
    dv1_opt = sol.x[3:6]
    T1_frac = np.clip(sol.x[6], 0.1, 0.9)
    T1_opt = T1_frac * T_total
    T2_opt = (1 - T1_frac) * T_total

    pv_arr = propagate(pv0, t0_val,
                        [dv0_opt.tolist(), dv1_opt.tolist(), [0, 0, 0]],
                        [T1_opt, T2_opt])
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return row, orig_mass, orig_mass
    dv2_opt, _ = dv2_res
    new_row = list(row)
    new_row[10:13] = dv0_opt.tolist()
    new_row[13:16] = dv1_opt.tolist()
    new_row[16:19] = dv2_opt.tolist()
    new_row[19] = T1_opt
    new_row[20] = T2_opt
    polished_mass = evaluate_row(new_row, udp)
    if polished_mass > orig_mass:
        return new_row, polished_mass, orig_mass
    return row, orig_mass, orig_mass


def _polish_task(args):
    idx, row = args
    idE = int(row[0])
    idL = int(row[1])
    new_row, new_mass, orig_mass = polish_3impulse(row, idE, idL)
    return idx, new_row, new_mass, orig_mass


def main(input_bank=None, n_workers=8):
    udp = LtlTrajectory(ROOT)
    if input_bank is None:
        input_bank = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json"

    print(f"Reading bank: {input_bank}", flush=True)
    bank = json.load(open(input_bank))
    dv = bank[0]["decisionVector"]

    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            active.append((i // 21, dv[i:i + 21]))
    print(f"Active rows: {len(active)}", flush=True)

    if not active:
        return

    f_baseline = udp.fitness(dv)[0]
    print(f"Baseline mass: {-f_baseline:.0f} kg", flush=True)

    print(f"\n3-impulse polish on {len(active)} rows with {n_workers} workers...",
          flush=True)
    t_start = time.time()
    polished = list(dv)
    improvements = []

    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _polish_task, active, chunksize=2):
            gain = new_mass - orig_mass
            improvements.append(gain)
            if gain > 0.5:
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg (+{gain:.0f})",
                      flush=True)
    wall = time.time() - t_start
    n_improved = sum(1 for g in improvements if g > 0.5)
    total_gain = sum(g for g in improvements if g > 0.5)
    print(f"\n3-impulse polish done in {wall:.0f}s: {n_improved}/{len(active)} "
          f"improved, +{total_gain:.0f} kg total", flush=True)

    f_polished = udp.fitness(polished)[0]
    if -f_polished > -f_baseline + 0.5:
        Path(input_bank).write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        print(f"BANKED 3-impulse: {-f_baseline:.0f} → {-f_polished:.0f} kg",
              flush=True)
    else:
        print("No improvement to bank", flush=True)


if __name__ == "__main__":
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=n_workers)
