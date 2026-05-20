"""Ch2 KTTSP — Simulated Annealing with mixed move set + intensification.

State          : feasible perm + makespan
Move palette   : 2-opt, Or-opt, cluster-bridge swap, ruin-recreate (k=3–7)
Acceptance     : Metropolis P = exp(-Δmk / T)
Schedule       : geometric T_0=8 d → T_end=0.05 d over N iters
Intensification: every M iters, 2-opt + Or-opt polish best-known
Restart        : after N_no_improve iters at low T, re-shuffle from best

Builds on the validated find_earliest_transfer (C-012) + walk_perm_chrono
chronological evaluator; rejects infeasible candidates outright.
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
    """Walk chronologically; return (makespan, x, feasible) or (None, None, False)."""
    times, tofs, _dvs, ok, _exc, _ = walk_perm_chrono(kt, perm)
    if not ok:
        return None, None, False
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    if not kt.is_feasible(f):
        return None, None, False
    return float(f[0]), x, True


def two_opt_move(perm, rng):
    n = len(perm)
    if n < 4:
        return None
    # i in [0, n-3] so i+2 <= n-1 and rng.integers(i+2, n) is valid
    i = int(rng.integers(0, n - 2))
    j = int(rng.integers(i + 2, n))
    return perm[:i + 1] + perm[i + 1:j + 1][::-1] + perm[j + 1:]


def or_opt_move(perm, rng):
    n = len(perm)
    k = rng.integers(0, n)
    target = rng.integers(0, n)
    while abs(target - k) <= 1:
        target = rng.integers(0, n)
    node = perm[k]
    rem = perm[:k] + perm[k + 1:]
    pos = target if target < k else target - 1
    return [*rem[:pos], node, *rem[pos:]]


def big_segment_reverse(perm, rng, cluster=(4, 17, 11), seg_len=(3, 8)):
    """Reverse a contiguous big-cluster sub-segment, *not crossing* the
    small cluster. Stronger than 2-opt by avoiding the brittle bridge
    region; useful when cluster moves are nearly always infeasible."""
    n = len(perm)
    cset = set(cluster)
    cidx = [i for i, v in enumerate(perm) if v in cset]
    if not cidx:
        return None
    c_lo, c_hi = min(cidx), max(cidx)
    # Pick reverse window on EITHER side of the cluster
    L = int(rng.integers(seg_len[0], seg_len[1] + 1))
    if rng.random() < 0.5:
        if c_lo - L - 1 <= 1:
            return None
        s = int(rng.integers(1, c_lo - L - 1))
    else:
        if c_hi + 1 + L >= n - 1:
            return None
        s = int(rng.integers(c_hi + 1, n - L - 1))
    e = s + L
    return perm[:s] + perm[s:e + 1][::-1] + perm[e + 1:]


def cluster_bridge_move(perm, rng, cluster=(4, 17, 11)):
    """Move the cluster (assumed contiguous in perm) to a different position
    + try a different internal ordering."""
    # locate cluster
    cset = set(cluster)
    idxs = [i for i, v in enumerate(perm) if v in cset]
    if len(idxs) != len(cluster):
        return None  # cluster not contiguous (or not all present)
    # If contiguous: lift it out and reinsert
    if max(idxs) - min(idxs) != len(cluster) - 1:
        return None
    start, end = min(idxs), max(idxs)
    chunk = perm[start:end + 1]
    # randomise internal order
    perm_in = list(chunk)
    rng.shuffle(perm_in)
    rem = perm[:start] + perm[end + 1:]
    new_pos = rng.integers(1, len(rem))  # avoid index 0
    while abs(new_pos - start) <= 2:
        new_pos = rng.integers(1, len(rem))
    return [*rem[:new_pos], *perm_in, *rem[new_pos:]]


def ruin_recreate(kt, perm, rng, k=3, n_pos_sample=8):
    """Remove k random nodes (not position 0), greedy-reinsert each at
    the best of `n_pos_sample` randomly-sampled positions (cheap, not
    exhaustive). Returns None if any node has no feasible insertion."""
    n = len(perm)
    if k >= n - 1:
        return None
    rm_idx = rng.choice(np.arange(1, n), size=k, replace=False).tolist()
    removed = [perm[i] for i in rm_idx]
    rng.shuffle(removed)
    cur = [perm[i] for i in range(n) if i not in rm_idx]
    for node in removed:
        best = None  # (intermediate_mk, cand)
        positions = list(range(1, len(cur) + 1))
        if len(positions) > n_pos_sample:
            positions = rng.choice(positions, size=n_pos_sample,
                                   replace=False).tolist()
        for pos in positions:
            cand = [*cur[:pos], node, *cur[pos:]]
            times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
            if not ok:
                continue
            mk = times[-1] + tofs[-1] if times else 0.0
            if best is None or mk < best[0]:
                best = (mk, cand)
        if best is None:
            return None
        cur = best[1]
    return cur if len(cur) == n else None


def sa(kt, perm0, n_iters=600, T_start=80.0, T_end=0.2,
       move_weights=None, intensify_every=100, seed=0, verbose=True):
    """Run SA from perm0; return (best_perm, best_x, best_mk)."""
    rng = np.random.default_rng(seed)
    if move_weights is None:
        move_weights = {"2opt": 0.25, "oropt": 0.20, "bigseg": 0.40,
                        "cluster": 0.10, "ruin": 0.05}
    cur_perm = list(perm0)
    cur_mk, cur_x, ok = evaluate(kt, cur_perm)
    if not ok:
        return None, None, None
    best_perm = list(cur_perm)
    best_mk = cur_mk
    best_x = cur_x
    cooling = (T_end / T_start) ** (1.0 / n_iters)
    T = T_start
    t0 = time.time()
    n_acc = 0
    n_imp = 0
    n_none = 0   # move returned None / bad shape
    n_infeas = 0  # candidate evaluated infeasible
    for it in range(n_iters):
        move = rng.choice(list(move_weights.keys()),
                          p=list(move_weights.values()))
        if move == "2opt":
            cand = two_opt_move(cur_perm, rng)
        elif move == "oropt":
            cand = or_opt_move(cur_perm, rng)
        elif move == "bigseg":
            cand = big_segment_reverse(cur_perm, rng)
        elif move == "cluster":
            cand = cluster_bridge_move(cur_perm, rng)
        elif move == "ruin":
            cand = ruin_recreate(kt, cur_perm, rng, k=3)
        else:
            cand = None
        if cand is None or len(cand) != len(cur_perm) \
                or len(set(cand)) != len(cur_perm):
            n_none += 1
            T *= cooling
            continue
        mk, x, ok = evaluate(kt, cand)
        if not ok:
            n_infeas += 1
            T *= cooling
            continue
        d = mk - cur_mk
        if d < 0 or rng.random() < np.exp(-d / T):
            cur_perm = cand
            cur_mk = mk
            cur_x = x
            n_acc += 1
            if mk < best_mk - 0.01:
                best_perm = list(cand)
                best_mk = mk
                best_x = x
                n_imp += 1
                if verbose:
                    print(f"  iter {it}: {move} → mk={mk:.3f} "
                          f"(T={T:.3f}, Δ={best_mk-mk:.3f}, acc={n_acc})",
                          flush=True)
        T *= cooling
        if (it + 1) % intensify_every == 0 and verbose:
            print(f"  [it {it+1}] best={best_mk:.3f}, cur={cur_mk:.3f}, "
                  f"T={T:.3f}, acc={n_acc}, imp={n_imp}, "
                  f"none={n_none}, infeas={n_infeas}, "
                  f"wall={time.time()-t0:.1f}s", flush=True)
    if verbose:
        print(f"SA done: best={best_mk:.3f}, accepted={n_acc}/{n_iters}, "
              f"improvements={n_imp}, wall={time.time()-t0:.1f}s",
              flush=True)
    return best_perm, best_x, best_mk


def main(inst="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
              "Salesperson Problem/problems/easy.kttsp",
         problem="small",
         in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         n_iters=600, seed=0):
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x = data[0]["decisionVector"]
    n = kt.n
    perm0 = [round(v) for v in x[2 * n - 2:]]
    initial_mk = kt.fitness(x)[0]
    print(f"Initial mk: {initial_mk:.3f}, n={n}", flush=True)
    t0 = time.time()
    best_perm, best_x, best_mk = sa(kt, perm0, n_iters=n_iters, seed=seed)
    wall = time.time() - t0
    if best_perm is None:
        return {"feasible": False, "wall_s": wall}
    f = kt.fitness(best_x)
    feas = kt.is_feasible(f)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": round(initial_mk, 3),
            "final_mk": round(best_mk, 3), "feasible": feas,
            "improvement_d": round(initial_mk - best_mk, 3),
            "n_iters": n_iters, "seed": seed,
            "rank3_small_d": 111.76}
    if feas and best_mk < initial_mk - 0.05:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    ni = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(json.dumps(main(n_iters=ni, seed=sd), indent=2))
