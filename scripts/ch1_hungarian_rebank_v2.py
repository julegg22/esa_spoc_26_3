"""Hungarian rebank v2 — fixes audit findings B4 and B5.

B5: score (idE, idL) Hungarian by *m_d* (= min(m_l, (200-ΔT)·c_ld)) not m_l.
    Use the OPTIMISTIC m_d that assumes the best idD is available.
B4: after picking transfers, run a second-stage Hungarian on (transfer, idD)
    with the *actual* m_d weight, so high-m_l transfers get high-c_ld idDs
    rather than letting greedy waste them.

Also fixes a hidden bug: results files store mass = udp.fitness() = m_d using
idD=0. If c_ld[idL][0] is low, the cached mass under-represents the trajectory's
true m_l. We recompute m_l from the dv components in the row.

Usage: python ch1_hungarian_rebank_v2.py [extra_results.json ...]
"""
import sys
import json
import math
import numpy as np
from pathlib import Path
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, T
import pykep as pk

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
M0 = 5000.0
M_DRY = 500.0
ISP = 311.0
G0 = pk.G0
T_UNIT_TO_DAYS = pk.SEC2DAY * T  # T already imported (= 3.7567696752e5 s)


def m_l_from_row(row):
    """Recover m_l (mass after all impulses, before cld discount) from a row."""
    dv0 = math.sqrt(row[10] ** 2 + row[11] ** 2 + row[12] ** 2) * V
    dv1 = math.sqrt(row[13] ** 2 + row[14] ** 2 + row[15] ** 2) * V
    dv2 = math.sqrt(row[16] ** 2 + row[17] ** 2 + row[18] ** 2) * V
    dv_tot = dv0 + dv1 + dv2
    return math.exp(-dv_tot / (ISP * G0)) * M0 - M_DRY


def dt_d_from_row(row):
    """Transfer duration ΔT in days."""
    return (row[19] + row[20]) * T_UNIT_TO_DAYS


def main(extra_jsons=None):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")

    # Collect candidate (idE, idL) → (m_l, dt_d, row, dv_ms). Best m_l per pair.
    results = {}  # (idE, idL) → (m_l, dt_d, row)

    # 1. Current bank
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        n_bank = 0
        for i in range(0, len(dv), 21):
            row = list(dv[i:i + 21])
            if row[0] < 0:
                continue
            n_bank += 1
            idE = int(row[0])
            idL = int(row[1])
            m_l = m_l_from_row(row)
            if m_l <= 0:
                continue
            dt_d = dt_d_from_row(row)
            key = (idE, idL)
            if key not in results or results[key][0] < m_l:
                results[key] = (m_l, dt_d, row)
        print(f"From existing bank: {n_bank} transfers → {len(results)} pairs",
              flush=True)

    # 2. Extra results JSONs (each entry: 'idE,idL' → [mass_with_idD0, row, dv_ms])
    if extra_jsons:
        for jpath in extra_jsons:
            extra = json.load(open(jpath))
            n_added = 0
            for k, v in extra.items():
                idE, idL = map(int, k.split(','))
                row = list(v[1])
                m_l = m_l_from_row(row)
                if m_l <= 0:
                    continue
                dt_d = dt_d_from_row(row)
                key = (idE, idL)
                if key not in results or results[key][0] < m_l:
                    results[key] = (m_l, dt_d, row)
                    n_added += 1
            print(f"From {jpath}: {n_added} new/better → total {len(results)}",
                  flush=True)

    if not results:
        print("No candidates found", flush=True)
        return

    # Per-idL max c_ld (for OPTIMISTIC m_d in stage-1 Hungarian)
    max_cld_per_l = np.zeros(400)
    for l in range(400):
        for d in range(400):
            if (l, d) in udp.ltl_dict:
                v_ = udp.ltl_dict[(l, d)]
                if v_ > max_cld_per_l[l]:
                    max_cld_per_l[l] = v_

    # ─── STAGE 1: Hungarian on (idE, idL) with OPTIMISTIC m_d ──────────────
    M = np.zeros((400, 400))
    for (idE, idL), (m_l, dt_d, _) in results.items():
        cap_opt = max_cld_per_l[idL] * max(0.0, 200.0 - dt_d)
        M[idE, idL] = min(m_l, cap_opt)
    print(f"\nStage 1: Hungarian on (idE, idL) with min(m_l, optimistic_cap)",
          flush=True)
    row_idx, col_idx = linear_sum_assignment(-M)
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results and M[r, c] > 0.5:
            selected.append((r, c, results[(r, c)]))
    sum_optimistic = sum(M[r, c] for r, c, _ in selected)
    print(f"  picked {len(selected)} transfers, "
          f"optimistic sum = {sum_optimistic:.0f} kg", flush=True)

    # ─── STAGE 2: Hungarian on (transfer_index, idD) with ACTUAL m_d ────────
    N = len(selected)
    M2 = np.zeros((N, 400))
    for ti, (idE, idL, (m_l, dt_d, _)) in enumerate(selected):
        cap_window = max(0.0, 200.0 - dt_d)
        for d in range(400):
            if (idL, d) in udp.ltl_dict:
                cap = udp.ltl_dict[(idL, d)] * cap_window
                M2[ti, d] = min(m_l, cap)
    print(f"\nStage 2: Hungarian on (transfer, idD)", flush=True)
    row_idx2, col_idx2 = linear_sum_assignment(-M2)
    sum_actual = M2[row_idx2, col_idx2].sum()
    print(f"  actual sum = {sum_actual:.0f} kg", flush=True)

    # ─── Build final chromosome ────────────────────────────────────────────
    final_rows = []
    for ti, dd in zip(row_idx2, col_idx2):
        if M2[ti, dd] < 0.5:
            continue
        idE, idL, (m_l, dt_d, row) = selected[ti]
        new_row = list(row)
        new_row[2] = float(dd)
        final_rows.append(new_row)

    chromosome = []
    for r in final_rows:
        chromosome.extend(r)
    pad = (udp.dim - len(chromosome)) // 21
    for _ in range(pad):
        chromosome.extend([-1] + [0.0] * 20)

    f_total = udp.fitness(chromosome)[0]
    print(f"\nUDP verify: total = {-f_total:.0f} kg from {len(final_rows)} transfers",
          flush=True)

    # Compare and commit
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
              f"(+{-f_total - old_mass:.0f})", flush=True)
    else:
        print(f"  existing bank {old_mass:.0f} >= new {-f_total:.0f}", flush=True)


if __name__ == "__main__":
    extra = sys.argv[1:] if len(sys.argv) > 1 else None
    main(extra_jsons=extra)
