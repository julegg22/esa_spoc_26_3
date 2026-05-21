"""Ch2 KTTSP — Iterated Local Search with double-bridge kicks.

Classic ILS scheme for TSP-like problems (Lin-Kernighan inspired):
1. Local search converges to a local optimum (we use 2-opt restricted
   to big-cluster segments, which preserves cluster structure)
2. Apply a "kick" perturbation that local search alone cannot undo
   (double-bridge: cut at 4 random points, swap middle two segments)
3. Re-local-search from the kicked solution
4. Accept the new local optimum if better than the running best
5. Repeat

Per O-010, untried family. SA had similar acceptance dynamics but
without explicit kicks; here we force structural escape via the
double-bridge.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_bigcluster_2opt import (
    SMALL_NODES, big_segments, restricted_2opt,
)
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def double_bridge_kick(perm, rng, segments):
    """Pick a single big-cluster segment with length ≥ 8; cut it at
    4 points inside, swap the middle two pieces. Returns kicked perm
    or original if can't kick."""
    candidates = [(s, e) for s, e in segments if e - s + 1 >= 8]
    if not candidates:
        return list(perm)
    s, e = candidates[rng.integers(len(candidates))]
    L = e - s + 1
    # Pick 3 distinct cut indices in [s+1, e]
    cuts = sorted(rng.choice(range(s + 1, e + 1), size=3, replace=False))
    a, b, c = cuts
    new_segment = (perm[s:a] + perm[b:c] + perm[a:b] + perm[c:e + 1])
    return list(perm[:s]) + list(new_segment) + list(perm[e + 1:])


def evaluate_with_polish(kt, perm):
    """Evaluate perm via walk_perm_chrono → fitness; returns
    (makespan, x, feasible). No NLP polish in this hot loop."""
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, perm)
    if not ok or not times:
        return None, None, False
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    if not kt.is_feasible(f):
        return None, None, False
    return float(f[0]), x, True


def ils(kt, perm0, n_kicks=15, opt_budget=120.0, seed=0, verbose=True):
    """Main ILS loop."""
    rng = np.random.default_rng(seed)
    cur_perm = list(perm0)
    cur_mk, cur_x, ok = evaluate_with_polish(kt, cur_perm)
    if not ok:
        return None, None, None
    best_perm = list(cur_perm)
    best_mk = cur_mk
    best_x = cur_x
    if verbose:
        print(f"ILS start: mk={best_mk:.4f}", flush=True)
    t0 = time.time()
    for k in range(n_kicks):
        segments = big_segments(cur_perm)
        kicked = double_bridge_kick(cur_perm, rng, segments)
        kicked_mk, _, kicked_ok = evaluate_with_polish(kt, kicked)
        if not kicked_ok:
            if verbose:
                print(f"  kick {k}: infeasible", flush=True)
            continue
        # 2-opt restricted local search
        polished_perm, polished_mk = restricted_2opt(
            kt, kicked, time_budget=opt_budget, verbose=False)
        if polished_perm is None:
            continue
        polished_mk2, polished_x, polished_ok = evaluate_with_polish(
            kt, polished_perm)
        if not polished_ok:
            continue
        if verbose:
            wall = time.time() - t0
            print(f"  kick {k}: kicked_mk={kicked_mk:.3f}, "
                  f"after_2opt={polished_mk2:.3f}, "
                  f"wall={wall:.0f}s", flush=True)
        if polished_mk2 < best_mk - 0.001:
            best_perm = polished_perm
            best_mk = polished_mk2
            best_x = polished_x
            cur_perm = polished_perm
            if verbose:
                print(f"  ✓ NEW BEST: {best_mk:.4f}", flush=True)
        # Don't always accept worse — stay near best
        elif polished_mk2 < best_mk + 5.0:
            cur_perm = polished_perm
    return best_perm, best_x, best_mk


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", n_kicks=10, opt_budget=120.0, seed=0):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm0 = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.4f}", flush=True)
    t0 = time.time()
    best_perm, best_x, best_mk = ils(kt, perm0, n_kicks=n_kicks,
                                      opt_budget=opt_budget, seed=seed)
    wall = time.time() - t0
    if best_perm is None:
        return {"feasible": False, "wall_s": wall}
    f = kt.fitness(best_x)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "best_mk": float(best_mk), "feasible": feas,
            "delta_d": float(initial_mk - best_mk),
            "n_kicks": n_kicks, "seed": seed,
            "rank3_small_d": 111.76}
    if feas and best_mk < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    nk = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    ob = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    print(json.dumps(main(n_kicks=nk, opt_budget=ob, seed=sd), indent=2))
