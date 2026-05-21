"""Ch2 KTTSP — Or-2-opt (move 2 consecutive nodes) with post-move
joint NLP polish.

Standard Or-opt moves a sub-chain to a new position. Or-opt-with-
walk-baseline missed the polish gain (the walk re-greedies tof and
loses 0.067d per case). Here: after each candidate move that walks
feasibly with walked_mk < walk_baseline (142.9888), run a quick
joint NLP polish on the new perm and compare to polished baseline
(142.9183).

Only big-cluster source/target segments — keep small-cluster blocks
intact, since they're geometry-constrained.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_bigcluster_2opt import big_segments
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_joint_nlp_polish import joint_polish
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def or2_polished(kt, perm0, baseline_polished, time_budget=900.0,
                  verbose=True):
    """Or-2-opt restricted to big-cluster: move 2 consecutive nodes
    from one big-cluster position to another. Evaluate via walk; only
    if walked_mk < walk_baseline + slack do we run polish to compare."""
    perm = list(perm0)
    times0, tofs0, _, ok, _, _ = walk_perm_chrono(kt, perm)
    if not ok:
        return None, None, None
    walk_baseline = times0[-1] + tofs0[-1]
    if verbose:
        print(f"Or-2 polished: walk_baseline={walk_baseline:.4f}, "
              f"polished_baseline={baseline_polished:.4f}", flush=True)
    best_perm = list(perm)
    best_x = times0 + tofs0 + [float(v) for v in perm]
    best_mk = baseline_polished
    t0 = time.time()
    n_eval = 0
    n_polish = 0
    improved = True
    while improved and time.time() - t0 < time_budget:
        improved = False
        segs = big_segments(perm)
        for s, e in segs:
            if e - s < 3:
                continue
            for src in range(s, e):  # source 2-node block start
                if time.time() - t0 > time_budget:
                    break
                # The 2-block is perm[src..src+1]
                for tgt in range(s, e):
                    if abs(tgt - src) <= 2:
                        continue
                    # Move perm[src..src+1] to position tgt
                    pair = [perm[src], perm[src + 1]]
                    rem = perm[:src] + perm[src + 2:]
                    # Insert at adjusted tgt
                    adj = tgt if tgt < src else tgt - 2
                    cand = rem[:adj] + pair + rem[adj:]
                    if len(cand) != len(perm):
                        continue
                    t2, tf2, _, ok2, _, _ = walk_perm_chrono(kt, cand)
                    n_eval += 1
                    if not ok2 or not t2:
                        continue
                    walked_mk = t2[-1] + tf2[-1]
                    # Only polish promising candidates (within
                    # walk_baseline + 0.1d): polish is expensive
                    if walked_mk > walk_baseline + 0.1:
                        continue
                    # Caps from the candidate's walked (td, tof)
                    caps = []
                    for k in range(len(cand) - 1):
                        dv = kt.compute_transfer(cand[k], cand[k + 1],
                                                   t2[k], tf2[k])
                        c = (kt.dv_exc if dv > kt.dv_thr
                              else kt.dv_thr) - 5e-4
                        caps.append(c)
                    times, tofs, mk = joint_polish(kt, cand, t2, tf2,
                                                    caps, maxiter=80,
                                                    verbose=False)
                    n_polish += 1
                    x_new = times + tofs + [float(v) for v in cand]
                    f = kt.fitness(x_new)
                    polished_mk = float(f[0])
                    if kt.is_feasible(f) and polished_mk < best_mk - 1e-3:
                        if verbose:
                            print(f"  ({src},{tgt}): walked={walked_mk:.3f}"
                                  f" → polished={polished_mk:.4f} "
                                  f"(Δ={best_mk - polished_mk:.4f})",
                                  flush=True)
                        perm = cand
                        best_perm = list(cand)
                        best_x = list(x_new)
                        best_mk = polished_mk
                        # Update walk baseline for new perm
                        t_b, tf_b, _, _, _, _ = walk_perm_chrono(kt, perm)
                        walk_baseline = t_b[-1] + tf_b[-1]
                        improved = True
                        break
                if improved:
                    break
            if improved:
                break
        if verbose:
            wall = time.time() - t0
            print(f"  pass: n_eval={n_eval}, n_polish={n_polish}, "
                  f"best={best_mk:.4f}, wall={wall:.1f}s", flush=True)
    return best_perm, best_x, best_mk


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
    print(f"Initial: mk={initial_mk:.4f} d", flush=True)
    t0 = time.time()
    best_perm, best_x, best_mk = or2_polished(
        kt, perm0, baseline_polished=float(initial_mk),
        time_budget=time_budget)
    wall = time.time() - t0
    if best_perm is None:
        return {"feasible": False, "wall_s": wall}
    f = kt.fitness(best_x)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "best_mk": float(f[0]),
            "feasible": feas,
            "delta_d": float(initial_mk - f[0]),
            "rank3_small_d": 111.76}
    if feas and f[0] < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    tb = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    print(json.dumps(main(time_budget=tb), indent=2))
