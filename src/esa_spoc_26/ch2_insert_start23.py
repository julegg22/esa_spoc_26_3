"""Ch2 KTTSP — finish what the topk run started: complete the 4-missing
insertion for start=23, which had reached ~40 min of 24 orderings × 47
positions ≈ 1128 evaluations when killed. Run with a 90-min budget
this time."""

from __future__ import annotations

import json
import time

from esa_spoc_26.ch2_findtransfer_greedy import greedy_findxfer
from esa_spoc_26.ch2_insert_lns import insert_lns
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

INST = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")


def main():
    kt = KTTSP(INST)
    perm0, _, _, _, _ = greedy_findxfer(kt, start=23, tof_window=12.0,
                                         n_steps=120)
    missing = sorted(set(range(kt.n)) - set(perm0))
    print(f"start=23: legs={len(perm0)-1}, missing={missing}", flush=True)
    t0 = time.time()
    full_perm, parts, n_feas = insert_lns(kt, perm0, missing, verbose=True)
    wall = time.time() - t0
    info = {"start": 23, "legs_partial": len(perm0) - 1,
            "missing": missing, "n_feasible_insertions": n_feas,
            "wall_s": round(wall, 1)}
    if full_perm is None:
        info["feasible"] = False
        return info
    times, tofs, _ = parts
    x = times + tofs + [float(v) for v in full_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    info.update({"makespan_d": round(f[0], 3), "feasible": feas,
                 "perm": [int(p) for p in full_perm]})
    # Save with suffix (compare against banked 143.79)
    if feas and f[0] < 143.79:
        from pathlib import Path
        p = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json")
        # only overwrite if strictly better
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": "small",
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
        info["replaced_banked"] = True
    return info


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
