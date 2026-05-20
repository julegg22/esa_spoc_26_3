"""Ch2 KTTSP — 2-opt polish on a feasible permutation.

For each pair of non-adjacent positions (i, j) with i < j, try
reversing the segment perm[i+1:j+1]. Re-walk chronologically; keep
if the resulting makespan improves and remains feasible. First-
improvement, time-budgeted.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def two_opt(kt, perm0, time_budget=600.0, tof_window=18.0, n_steps=180,
            verbose=True):
    perm = list(perm0)
    n = len(perm)
    # Establish baseline
    times, tofs, _dvs, ok, _exc, _ = walk_perm_chrono(
        kt, perm, tof_window=tof_window, n_steps=n_steps)
    if not ok:
        return None, None, False
    best_mk = times[-1] + tofs[-1]
    t0 = time.time()
    improved = True
    iter_n = 0
    while improved and time.time() - t0 < time_budget:
        improved = False
        for i in range(n - 1):
            if time.time() - t0 > time_budget:
                break
            for j in range(i + 2, n):
                if time.time() - t0 > time_budget:
                    break
                cand = perm[:i + 1] + perm[i + 1:j + 1][::-1] + perm[j + 1:]
                # Quick reject: if cand[0] == perm[0] (same start), the
                # makespan only differs if the reversed segment changes
                # something downstream. Always evaluate.
                t2, tf2, _dv2, ok2, _exc2, _ = walk_perm_chrono(
                    kt, cand, tof_window=tof_window, n_steps=n_steps)
                if not ok2:
                    continue
                mk2 = t2[-1] + tf2[-1]
                x = t2 + tf2 + [float(v) for v in cand]
                f = kt.fitness(x)
                if not kt.is_feasible(f):
                    continue
                if mk2 < best_mk - 0.05:  # require ≥ 0.05 d improvement
                    if verbose:
                        delta = best_mk - mk2
                        print(f"  2-opt ({i},{j}): mk {best_mk:.2f} → "
                              f"{mk2:.2f} (Δ={delta:.2f})", flush=True)
                    perm = cand
                    best_mk = mk2
                    improved = True
                    break
            if improved:
                break
        iter_n += 1
        if verbose:
            print(f"  iter {iter_n}: best mk={best_mk:.2f}, "
                  f"wall={time.time()-t0:.1f}s", flush=True)
    return perm, best_mk, True


def main(inst="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
              "Salesperson Problem/problems/easy.kttsp",
         problem="small",
         in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         time_budget=600.0):
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x = data[0]["decisionVector"]
    n = kt.n
    perm0 = [round(v) for v in x[2 * n - 2:]]
    print(f"Initial perm: {perm0[:5]}...{perm0[-5:]}", flush=True)
    print(f"Initial makespan: {kt.fitness(x)[0]:.3f}", flush=True)
    t0 = time.time()
    perm, _mk, ok = two_opt(kt, perm0, time_budget=time_budget)
    wall = time.time() - t0
    if not ok:
        return {"feasible": False, "wall_s": wall}
    # Re-build full decision vector
    times, tofs, _, _, _, _ = walk_perm_chrono(kt, perm)
    x_new = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x_new)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": round(kt.fitness(x)[0], 3),
            "final_mk": round(f[0], 3), "feasible": feas,
            "improvement_d": round(kt.fitness(x)[0] - f[0], 3),
            "rank3_small_d": 111.76}
    if feas and f[0] < kt.fitness(x)[0]:
        # Overwrite artifact only if better
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x_new),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    tb = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    print(json.dumps(main(time_budget=tb), indent=2))
