"""Hungarian re-assignment from saved sweep results.

Inputs:
- runs/ch1/extended_results.json — sweep result dict
- (optionally) existing trajectory.json bank — add to candidate pool

Performs Hungarian on (mass) matrix, picks unique-idD greedy by cld, banks.

Usage:
  python ch1_hungarian_rebank.py [extra_results_jsons...]
"""
import sys
import json
import numpy as np
from pathlib import Path
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch1_trajectory import LtlTrajectory
import pykep as pk

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"


def main(extra_jsons=None):
    udp = LtlTrajectory(ROOT)
    bank_path = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")

    # Collect (idE, idL) -> (mass, row, dv_ms) from all sources
    results = {}

    # 1. Current bank
    if bank_path.exists():
        bank = json.load(open(bank_path))
        dv = bank[0]["decisionVector"]
        for i in range(0, len(dv), 21):
            row = dv[i:i + 21]
            if row[0] >= 0:
                chr_padded = list(row)
                pad = (udp.dim - len(chr_padded)) // 21
                for _ in range(pad):
                    chr_padded.extend([-1.0] + [0.0] * 20)
                mass = -udp.fitness(chr_padded)[0]
                idE = int(row[0])
                idL = int(row[1])
                if mass > 0:
                    key = (idE, idL)
                    if key not in results or results[key][0] < mass:
                        results[key] = (mass, list(row), 0)
        print(f"From existing bank: {len(results)} (idE,idL) pairs", flush=True)

    # 2. Extra results JSONs
    if extra_jsons:
        for jpath in extra_jsons:
            extra = json.load(open(jpath))
            n_added = 0
            for k, v in extra.items():
                idE, idL = map(int, k.split(','))
                mass, row, dv_ms = v[0], v[1], v[2]
                key = (idE, idL)
                if key not in results or results[key][0] < mass:
                    results[key] = (mass, row, dv_ms)
                    n_added += 1
            print(f"From {jpath}: {n_added} new/better pairs (total now {len(results)})",
                  flush=True)

    if not results:
        print("No candidates found", flush=True)
        return

    # Hungarian on mass matrix
    print(f"\nHungarian on {len(results)} candidate pairs...", flush=True)
    M = np.zeros((400, 400))
    for (idE, idL), (mass, _, _) in results.items():
        M[idE, idL] = mass
    row_idx, col_idx = linear_sum_assignment(-M)
    selected = []
    for r, c in zip(row_idx, col_idx):
        if (r, c) in results:
            selected.append((r, c, results[(r, c)]))
    selected.sort(key=lambda s: -s[2][0])
    print(f"Selected {len(selected)} transfers, "
          f"sum mass = {sum(s[2][0] for s in selected):.0f} kg",
          flush=True)

    # idD assignment: greedy by best available cld per (idL)
    print("\nAssigning unique idD (greedy by cld * remaining_time)...", flush=True)
    used_d = set()
    final = []
    for idE, idL, (mass, row, _) in selected:
        T_unit_to_days = pk.SEC2DAY * 3.7567696752e5  # T in seconds
        dt_d = (row[19] + row[20]) * T_unit_to_days
        best_d, best_cap = None, 0
        for idd in range(400):
            if idd in used_d:
                continue
            if (idL, idd) not in udp.ltl_dict:
                continue
            cld = udp.ltl_dict[(idL, idd)]
            cap = cld * max(0, 200 - dt_d)
            if cap > best_cap:
                best_cap = cap
                best_d = idd
        if best_d is None:
            continue
        used_d.add(best_d)
        new_row = list(row)
        new_row[2] = best_d
        final.append((idE, idL, best_d, mass, new_row))

    # Build chromosome
    chromosome = []
    for _, _, _, _, row in final:
        chromosome.extend(row)
    pad = (udp.dim - len(chromosome)) // 21
    for _ in range(pad):
        chromosome.extend([-1] + [0.0] * 20)

    f_total = udp.fitness(chromosome)[0]
    print(f"\nUDP verify: total mass = {-f_total:.0f} kg from {len(final)} transfers",
          flush=True)

    # Compare to existing bank
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
              f"(+{-f_total - old_mass:.0f}, {len(final)} transfers)",
              flush=True)
    else:
        print(f"Existing bank {old_mass:.0f} kg >= new {-f_total:.0f}", flush=True)


if __name__ == "__main__":
    extra = sys.argv[1:] if len(sys.argv) > 1 else None
    main(extra_jsons=extra)
