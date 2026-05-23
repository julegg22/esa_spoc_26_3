"""Ch2 KTTSP — backtracking Hamilton search on cheap-arc graph.

P2 v1 (NN-greedy) reached 530/1051 with 5/5 excs used. Improvements:

1. **Lookahead-2 NN**: at each step, prefer the unvisited neighbor
   that maximizes the *number of cheap out-edges TO unvisited
   neighbors*. Avoids dead-ends.
2. **Backtracking**: when stuck at depth d, undo up to k_back steps
   and try the second-best neighbor at that depth. Limited
   backtrack budget to keep tractable.
3. **Exc-deferred**: only use exception arcs as a LAST resort, not
   mid-greedy. Maximizes flexibility for late stages.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_cheap_arc_hamilton import (
    build_cheap_adj, load_graph, walk_perm_with_hints,
)
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def lookahead_score(adj, j, visited, depth=2):
    """Number of unvisited cheap-neighbors-of-cheap-neighbors of j.
    Higher = j leads to a more 'open' region of the graph."""
    if depth == 0:
        return 0
    count = 0
    for (k, _, _, _) in adj.get(j, [])[:20]:  # top-20 cheap
        if k not in visited:
            count += 1
            if depth > 1:
                count += sum(1 for (m, _, _, _) in adj.get(k, [])[:10]
                              if m not in visited)
    return count


def greedy_with_lookahead(kt, adj, start, n_exc_budget=5, verbose=False):
    """NN-greedy with lookahead-2 scoring. Defers exceptions."""
    n = kt.n
    visited = {start}
    perm = [start]
    bridges = []
    n_exc = 0
    cur = start
    while len(visited) < n:
        # Score cheap out-neighbors by lookahead
        candidates = [(j, dv, td, tof) for (j, dv, td, tof) in adj.get(cur, [])
                      if j not in visited]
        if candidates:
            # Pick the candidate with best lookahead, breaking ties by dv
            best_j, best_dv, best_td, best_tof = max(
                candidates,
                key=lambda c: (lookahead_score(adj, c[0], visited, depth=2),
                                -c[1])  # high lookahead, low dv
            )
            perm.append(best_j)
            visited.add(best_j)
            bridges.append((cur, best_j, best_dv, best_td, best_tof, False))
            cur = best_j
        elif n_exc < n_exc_budget:
            # Exception arc — find any unvisited reachable
            best_exc = None
            unvisited = sorted(set(range(n)) - visited)
            for j in unvisited[:300]:
                for td in np.linspace(0, kt.max_time * 0.9, 5):
                    for tof in np.linspace(0.1, 30, 5):
                        if td + tof > kt.max_time:
                            continue
                        dv = kt.compute_transfer(cur, j, float(td),
                                                   float(tof))
                        if dv <= kt.dv_exc:
                            if best_exc is None or dv < best_exc[1]:
                                best_exc = (j, dv, td, tof)
                            break
                    if best_exc is not None and best_exc[0] == j:
                        break
            if best_exc is None:
                if verbose:
                    print(f"  stuck at {cur} (visited {len(visited)})",
                          flush=True)
                return perm, bridges, n_exc, False
            j, dv, td, tof = best_exc
            perm.append(j)
            visited.add(j)
            bridges.append((cur, j, dv, td, tof, True))
            n_exc += 1
            cur = j
        else:
            # Budget exhausted, stuck
            if verbose:
                print(f"  budget exhausted at {cur} (visited {len(visited)})",
                      flush=True)
            return perm, bridges, n_exc, False
    return perm, bridges, n_exc, True


def main(problem="large", graph_path=None, n_start_scan=50,
         exc_budget=5):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    if graph_path is None:
        graph_path = "/tmp/large_cheap_arc_graph_knn80.pkl"
    g = load_graph(graph_path)
    cheap_adj = build_cheap_adj(g["cheap_edges"])
    print(f"Graph: {len(g['cheap_edges'])} cheap edges, "
          f"avg out-degree {sum(len(v) for v in cheap_adj.values()) / kt.n:.1f}",
          flush=True)
    # Pick starts by out-degree (top-K)
    starts = sorted(cheap_adj.keys(),
                    key=lambda i: -len(cheap_adj[i]))[:n_start_scan]
    print(f"Trying {len(starts)} starts (top-out-degree)", flush=True)
    best_result = None
    t0 = time.time()
    for si, start in enumerate(starts):
        perm, bridges, n_exc, ok = greedy_with_lookahead(
            kt, cheap_adj, start, n_exc_budget=exc_budget)
        n_visited = len(perm)
        if best_result is None or n_visited > best_result[0]:
            print(f"  start={start}: visited={n_visited}/{kt.n}, "
                  f"n_exc={n_exc}, complete={ok}", flush=True)
            best_result = (n_visited, start, perm, bridges, n_exc)
    wall = time.time() - t0
    print(f"\nLookahead search done in {wall:.0f}s", flush=True)
    n_visited, start, perm, bridges, n_exc = best_result
    print(f"BEST: start={start}, visited={n_visited}/{kt.n}, "
          f"n_exc={n_exc}", flush=True)
    if n_visited < kt.n:
        return {"status": "incomplete", "best_n": n_visited,
                "best_start": start}
    # Walk
    times, tofs, walk_ok = walk_perm_with_hints(kt, perm, bridges)
    if not walk_ok:
        return {"status": "walk_failed"}
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    print(f"FINAL: mk={f[0]:.4f}, feas={feas}", flush=True)
    info = {"problem": problem, "n": kt.n,
            "mk": float(f[0]), "feasible": feas}
    if feas:
        p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    gp = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(main(n_start_scan=ns, graph_path=gp), indent=2))
