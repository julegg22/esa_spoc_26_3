"""Tier 1A: per-transfer continuous polish (Nelder-Mead on dv0, T1, dv2).

Input: trajectory.json (post-sweep bank).
For each banked transfer row (21 elements):
- Keep idE, idL, idD, pv0 fixed (pv0 already on Earth orbit by construction).
- Polish (dv0, T1, dv2_inferred-from-arrival) continuously.
- Objective: -mass from UDP fitness.
- Constraints handled implicitly: UDP returns 0 for invalid → polish naturally
  prefers valid trajectories.

Expected gain: +15-25% per pair, based on (0,0) test (669 → 794 kg).
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
    L, T, V, MU_EARTH, LtlTrajectory, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
_UDP = [None]


def _init():
    _UDP[0] = LtlTrajectory(ROOT)


def evaluate_row(row, udp):
    """Compute mass from a 21-element chromosome row via UDP fitness."""
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    return -f  # mass (negated fitness)


def polish_row(row, idE, idL):
    """Polish 2-impulse row: vary dv0[3], T1 (T2=0); recompute dv2.

    The row's pv0 stays fixed (already on Earth orbit). We optimize:
      x = (dv0_x, dv0_y, dv0_z, T1_log)  -- T1_log = log(T1) for positivity
    """
    udp = _UDP[0]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = [row[4:7], row[7:10]]
    t0_val = row[3]
    orig_dv0 = np.array(row[10:13])
    orig_T1 = row[19]
    orig_mass = evaluate_row(row, udp)

    def neg_mass(x):
        dv0 = x[:3]
        T1 = np.exp(x[3])  # always positive
        # Propagate with no dv1
        pv_arr = propagate(pv0, t0_val, [dv0.tolist(), [0, 0, 0], [0, 0, 0]],
                            [T1, 0.0])
        if len(pv_arr) == 0:
            return 1e3
        # Compute dv2 via eccentric-aware solver
        dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if dv2_res is None:
            return 1e3
        dv2, _ = dv2_res
        new_row = list(row)
        new_row[10:13] = dv0.tolist()
        new_row[13:16] = [0.0, 0.0, 0.0]
        new_row[16:19] = dv2.tolist()
        new_row[19] = T1
        new_row[20] = 0.0
        mass = evaluate_row(new_row, udp)
        if mass <= 0:
            return 1e3
        return -mass

    x0 = np.array([orig_dv0[0], orig_dv0[1], orig_dv0[2], np.log(max(orig_T1, 1e-3))])
    try:
        sol = minimize(neg_mass, x0, method="Nelder-Mead",
                        options={"xatol": 1e-4, "fatol": 0.5,
                                  "maxiter": 100, "disp": False,
                                  "initial_simplex": np.array([
                                      x0,
                                      x0 + np.array([0.01, 0, 0, 0]),
                                      x0 + np.array([0, 0.01, 0, 0]),
                                      x0 + np.array([0, 0, 0.01, 0]),
                                      x0 + np.array([0, 0, 0, 0.05]),
                                  ])})
    except Exception:
        return row, orig_mass, orig_mass

    if sol.fun >= 1e3:
        return row, orig_mass, orig_mass

    # Reconstruct polished row
    dv0_opt = sol.x[:3]
    T1_opt = np.exp(sol.x[3])
    pv_arr = propagate(pv0, t0_val, [dv0_opt.tolist(), [0, 0, 0], [0, 0, 0]],
                        [T1_opt, 0.0])
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return row, orig_mass, orig_mass
    dv2_opt, _ = dv2_res
    new_row = list(row)
    new_row[10:13] = dv0_opt.tolist()
    new_row[13:16] = [0.0, 0.0, 0.0]
    new_row[16:19] = dv2_opt.tolist()
    new_row[19] = T1_opt
    new_row[20] = 0.0
    polished_mass = evaluate_row(new_row, udp)
    if polished_mass > orig_mass:
        return new_row, polished_mass, orig_mass
    return row, orig_mass, orig_mass


def _polish_task(args):
    idx, row_with_ids = args
    row = row_with_ids[:21]
    idE = int(row[0])
    idL = int(row[1])
    new_row, new_mass, orig_mass = polish_row(row, idE, idL)
    return idx, new_row, new_mass, orig_mass


def main(input_bank=None, n_workers=8):
    udp = LtlTrajectory(ROOT)
    if input_bank is None:
        input_bank = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json"

    print(f"Reading bank: {input_bank}", flush=True)
    bank = json.load(open(input_bank))
    dv = bank[0]["decisionVector"]
    print(f"Bank has {len(dv)} elements ({len(dv) // 21} rows)", flush=True)

    # Identify active rows (idE >= 0)
    active = []
    for i in range(0, len(dv), 21):
        if dv[i] >= 0:
            active.append((i // 21, dv[i:i + 21]))
    print(f"Active rows: {len(active)}", flush=True)

    if not active:
        print("No active rows to polish", flush=True)
        return

    # Baseline mass
    f_baseline = udp.fitness(dv)[0]
    print(f"Baseline mass: {-f_baseline:.0f} kg", flush=True)

    # Polish each row in parallel
    print(f"\nPolishing {len(active)} rows with {n_workers} workers...", flush=True)
    t_start = time.time()
    polished = list(dv)
    improvements = []

    with mp.Pool(n_workers, initializer=_init) as p:
        for idx, new_row, new_mass, orig_mass in p.imap_unordered(
                _polish_task, active, chunksize=2):
            gain = new_mass - orig_mass
            improvements.append(gain)
            if gain > 0.1:
                # Update the row in place
                offset = idx * 21
                polished[offset:offset + 21] = list(new_row)
                print(f"  [{idx:3d}] {orig_mass:.0f} → {new_mass:.0f} kg (+{gain:.0f})",
                      flush=True)
    wall = time.time() - t_start
    n_improved = sum(1 for g in improvements if g > 0.1)
    total_gain = sum(g for g in improvements if g > 0.1)
    print(f"\nPolish done in {wall:.0f}s: {n_improved}/{len(active)} improved, "
          f"+{total_gain:.0f} kg total", flush=True)

    # Verify and bank
    f_polished = udp.fitness(polished)[0]
    polished_mass = -f_polished
    print(f"\nNew total mass: {polished_mass:.0f} kg (was {-f_baseline:.0f})",
          flush=True)

    if polished_mass > -f_baseline + 0.5:
        bank_path = Path(input_bank)
        bank_path.write_text(json.dumps([{
            "decisionVector": [float(v) for v in polished],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        print(f"BANKED polished: {-f_baseline:.0f} → {polished_mass:.0f} kg",
              flush=True)
    else:
        print("No improvement to bank", flush=True)


if __name__ == "__main__":
    n_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=n_workers)
