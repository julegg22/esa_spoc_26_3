"""Ch2 KTTSP — 2-opt restricted to big-cluster-only segments.

The 142.92 perm has cluster blocks at fixed positions (start 0-2,
mid 25-27, end 46-48). Big-cluster nodes occupy [3-24] and [28-45] —
two independent segments. Standard 2-opt over the full perm is
slow because most reversals break cluster feasibility.

This variant: enumerate ALL 2-opt reversals that stay WITHIN one of
the big-cluster segments. Many fewer moves, all preserving cluster
structure, faster convergence.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


SMALL_NODES = {4, 11, 17, 18, 23, 34, 16, 27, 32}


def big_segments(perm):
    """Return list of (start_idx, end_idx) for contiguous big-cluster
    runs in perm. Big = not in SMALL_NODES."""
    segments = []
    in_seg = False
    s = 0
    for i, v in enumerate(perm):
        big = v not in SMALL_NODES
        if big and not in_seg:
            s = i
            in_seg = True
        elif not big and in_seg:
            segments.append((s, i - 1))
            in_seg = False
    if in_seg:
        segments.append((s, len(perm) - 1))
    return segments


def restricted_2opt(kt, perm0, time_budget=900.0, verbose=True):
    """First-improvement 2-opt restricted to big-cluster segments."""
    perm = list(perm0)
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, perm)
    if not ok:
        return None, None
    best_mk = times[-1] + tofs[-1]
    t0 = time.time()
    improved = True
    n_iter = 0
    while improved and time.time() - t0 < time_budget:
        improved = False
        segs = big_segments(perm)
        for s, e in segs:
            if e - s < 2:
                continue
            for i in range(s, e):
                if time.time() - t0 > time_budget:
                    break
                for j in range(i + 2, e + 1):
                    cand = perm[:i + 1] + perm[i + 1:j + 1][::-1] + \
                        perm[j + 1:]
                    t2, tf2, _, ok2, _, _ = walk_perm_chrono(kt, cand)
                    if not ok2 or not t2:
                        continue
                    mk2 = t2[-1] + tf2[-1]
                    x = t2 + tf2 + [float(v) for v in cand]
                    f = kt.fitness(x)
                    if kt.is_feasible(f) and mk2 < best_mk - 0.01:
                        if verbose:
                            print(f"  iter {n_iter}: ({i},{j}) "
                                  f"mk {best_mk:.3f}→{mk2:.3f} "
                                  f"(Δ={best_mk - mk2:.3f})",
                                  flush=True)
                        perm = cand
                        best_mk = mk2
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        n_iter += 1
        if verbose and n_iter % 5 == 0:
            wall = time.time() - t0
            print(f"  iter {n_iter}: best={best_mk:.3f}, "
                  f"wall={wall:.1f}s", flush=True)
    return perm, best_mk


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", time_budget=900.0):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm0 = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    segs = big_segments(perm0)
    print(f"Initial mk={initial_mk:.4f}", flush=True)
    print(f"big segments: {segs} "
          f"(lengths {[e - s + 1 for s, e in segs]})",
          flush=True)
    t0 = time.time()
    perm, best_mk = restricted_2opt(kt, perm0, time_budget=time_budget)
    wall = time.time() - t0
    if perm is None:
        return {"feasible": False, "wall_s": wall}
    times, tofs, _, _, _, _ = walk_perm_chrono(kt, perm)
    x_new = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x_new)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "final_mk": float(f[0]),
            "delta_d": float(initial_mk - f[0]),
            "feasible": feas,
            "rank3_small_d": 111.76}
    if feas and f[0] < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x_new),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    tb = float(sys.argv[1]) if len(sys.argv) > 1 else 900.0
    print(json.dumps(main(time_budget=tb), indent=2))
