"""Ch2 KTTSP — Adaptive Large Neighborhood Search (ALNS).

Multi-operator metaheuristic with destroy/repair pairs. Tracks each
operator's success and adaptively biases selection. Per O-010 family
inventory: untried family that complements 2-opt/Or-opt/SA. ALNS
is the standard for routing-with-side-constraints (Pisinger & Ropke
2010).

Destroy operators:
- random-k removal (k ∈ {3, 5, 7})
- segment removal (contiguous, len 3-7)
- exception-arc removal (rip out exception bridges)
- worst-Δv removal (remove arcs with highest Δv)

Repair operators:
- greedy insertion (find_earliest_transfer, cheap-first)
- best-position insertion (try all positions, keep best chronological)

Acceptance: Metropolis (SA-like) or threshold accept.

State: current best feasible perm + makespan; pool of operators
with weights updated by success.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def evaluate(kt, perm):
    """Walk + fitness. Returns (mk, x, feasible)."""
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, perm)
    if not ok or not times:
        return None, None, False
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    if not kt.is_feasible(f):
        return None, None, False
    return float(f[0]), x, True


def destroy_random(perm, rng, k=4):
    """Remove k random non-start/end nodes."""
    n = len(perm)
    idx = rng.choice(np.arange(1, n - 1), size=min(k, n - 2),
                     replace=False)
    removed = [perm[i] for i in idx]
    keep = [v for i, v in enumerate(perm) if i not in set(idx)]
    return keep, removed


def destroy_segment(perm, rng, seg_len=5):
    """Remove a contiguous segment of length seg_len."""
    n = len(perm)
    L = min(seg_len, n - 2)
    s = int(rng.integers(1, n - L))
    removed = perm[s:s + L]
    keep = perm[:s] + perm[s + L:]
    return keep, removed


def destroy_worst_dv(kt, perm, times, tofs, k=3):
    """Remove the k nodes whose incoming arc has highest Δv."""
    n = len(perm)
    dvs = []
    for i in range(n - 1):
        dv = kt.compute_transfer(perm[i], perm[i + 1], times[i], tofs[i])
        dvs.append((dv, i + 1, perm[i + 1]))
    dvs.sort(reverse=True)
    rm_positions = sorted({d[1] for d in dvs[:k]}, reverse=True)
    keep = list(perm)
    removed = []
    for pos in rm_positions:
        if pos == 0 or pos >= n:
            continue
        removed.append(keep.pop(pos))
    return keep, removed


def repair_greedy_insert(kt, partial, removed, rng):
    """Greedy-insert removed nodes one at a time at the position
    minimising arrival time."""
    cur_perm = list(partial)
    rng.shuffle(removed)
    for v in removed:
        best = None  # (mk, perm_with_v)
        for pos in range(1, len(cur_perm) + 1):
            cand = [*cur_perm[:pos], v, *cur_perm[pos:]]
            times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
            if not ok or not times:
                continue
            mk = times[-1] + tofs[-1]
            if best is None or mk < best[0]:
                best = (mk, cand)
        if best is None:
            return None
        cur_perm = best[1]
    return cur_perm


def alns(kt, perm0, n_iters=200, T_start=10.0, T_end=0.1,
         seed=0, verbose=True):
    """ALNS main loop with adaptive operator weights (roulette wheel)."""
    rng = np.random.default_rng(seed)
    cur_perm = list(perm0)
    cur_mk, cur_x, ok = evaluate(kt, cur_perm)
    if not ok:
        return None, None, None
    best_perm = list(cur_perm)
    best_mk = cur_mk
    best_x = cur_x
    # Operator weights (destroy: random-k, segment, worst-dv)
    destroy_ops = ["random", "segment", "worst_dv"]
    weights = {op: 1.0 for op in destroy_ops}
    scores = {op: [] for op in destroy_ops}
    cooling = (T_end / T_start) ** (1.0 / n_iters)
    T = T_start
    t0 = time.time()
    n_acc = 0
    n_imp = 0
    for it in range(n_iters):
        # Pick destroy operator by roulette wheel
        total_w = sum(weights.values())
        r = rng.random() * total_w
        cum = 0.0
        op = destroy_ops[0]
        for o in destroy_ops:
            cum += weights[o]
            if r <= cum:
                op = o
                break
        # Apply destroy
        if op == "random":
            keep, removed = destroy_random(cur_perm, rng, k=4)
        elif op == "segment":
            keep, removed = destroy_segment(cur_perm, rng, seg_len=5)
        else:
            times, tofs, _, ok2, _, _ = walk_perm_chrono(kt, cur_perm)
            if not ok2:
                T *= cooling
                continue
            keep, removed = destroy_worst_dv(kt, cur_perm, times, tofs, k=3)
        # Apply repair (greedy)
        new_perm = repair_greedy_insert(kt, keep, removed, rng)
        if new_perm is None:
            T *= cooling
            continue
        new_mk, new_x, new_ok = evaluate(kt, new_perm)
        if not new_ok:
            T *= cooling
            continue
        d = new_mk - cur_mk
        accepted = d < 0 or rng.random() < np.exp(-d / T)
        score = 0
        if accepted:
            n_acc += 1
            cur_perm = new_perm
            cur_mk = new_mk
            cur_x = new_x
            score = 1
            if new_mk < best_mk - 0.001:
                best_perm = list(new_perm)
                best_mk = new_mk
                best_x = new_x
                n_imp += 1
                score = 5
                if verbose:
                    print(f"  iter {it}: {op} → mk={new_mk:.3f} "
                          f"(T={T:.2f}, n_acc={n_acc}, n_imp={n_imp})",
                          flush=True)
        scores[op].append(score)
        # Update weights via exponential decay + score moving avg
        if len(scores[op]) % 20 == 0 and len(scores[op]) > 0:
            avg = sum(scores[op][-20:]) / 20
            weights[op] = max(0.2, 0.5 * weights[op] + 0.5 * (1.0 + avg))
        T *= cooling
    if verbose:
        wall = time.time() - t0
        print(f"ALNS done: best={best_mk:.3f}, accepted={n_acc}/{n_iters}, "
              f"improvements={n_imp}, wall={wall:.1f}s", flush=True)
        print(f"Final operator weights: {weights}", flush=True)
    return best_perm, best_x, best_mk


def main(inst="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
              "Salesperson Problem/problems/easy.kttsp",
         in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", n_iters=200, seed=0):
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm0 = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.4f}", flush=True)
    t0 = time.time()
    best_perm, best_x, best_mk = alns(kt, perm0, n_iters=n_iters,
                                       seed=seed)
    wall = time.time() - t0
    if best_perm is None:
        return {"feasible": False, "wall_s": wall}
    f = kt.fitness(best_x)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "best_mk": float(best_mk), "feasible": feas,
            "delta_d": float(initial_mk - best_mk),
            "n_iters": n_iters, "seed": seed,
            "rank3_small_d": 111.76}
    if feas and best_mk < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    ni = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(main(n_iters=ni, seed=sd), indent=2))
