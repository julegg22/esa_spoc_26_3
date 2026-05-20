"""Ch2 KTTSP — Or-opt polish (single-node relocation).

For each source position k and each target position l (k != l, |k-l|>1),
remove perm[k] and insert it before/after position l. Re-walk
chronologically; keep if makespan improves and feasible.
First-improvement; time-budgeted.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def or_opt(kt, perm0, time_budget=600.0, verbose=True):
    perm = list(perm0)
    n = len(perm)
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, perm)
    if not ok:
        return None, None, False
    best_mk = times[-1] + tofs[-1]
    t0 = time.time()
    improved = True
    iter_n = 0
    while improved and time.time() - t0 < time_budget:
        improved = False
        for k in range(n):
            if time.time() - t0 > time_budget:
                break
            for ll in range(n):
                if time.time() - t0 > time_budget:
                    break
                if abs(k - ll) <= 1:
                    continue
                node = perm[k]
                remaining = perm[:k] + perm[k + 1:]
                # insert before position ll (in remaining)
                target = ll if ll < k else ll - 1
                cand = [*remaining[:target], node, *remaining[target:]]
                if len(cand) != n or len(set(cand)) != n:
                    continue
                t2, tf2, _, ok2, _, _ = walk_perm_chrono(kt, cand)
                if not ok2:
                    continue
                mk2 = t2[-1] + tf2[-1]
                x = t2 + tf2 + [float(v) for v in cand]
                f = kt.fitness(x)
                if not kt.is_feasible(f):
                    continue
                if mk2 < best_mk - 0.05:
                    delta = best_mk - mk2
                    if verbose:
                        print(f"  or-opt {k}→{ll}: mk {best_mk:.2f} → "
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
    initial_mk = kt.fitness(x)[0]
    print(f"Initial makespan: {initial_mk:.3f}", flush=True)
    t0 = time.time()
    perm, _, ok = or_opt(kt, perm0, time_budget=time_budget)
    wall = time.time() - t0
    if not ok:
        return {"feasible": False, "wall_s": wall}
    times, tofs, _, _, _, _ = walk_perm_chrono(kt, perm)
    x_new = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x_new)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": round(initial_mk, 3),
            "final_mk": round(f[0], 3), "feasible": feas,
            "improvement_d": round(initial_mk - f[0], 3),
            "rank3_small_d": 111.76}
    if feas and f[0] < initial_mk - 0.05:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x_new),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    tb = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    print(json.dumps(main(time_budget=tb), indent=2))
