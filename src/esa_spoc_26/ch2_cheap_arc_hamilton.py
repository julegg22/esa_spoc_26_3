"""Ch2 KTTSP — Perspective 2: Hamilton path on cheap-arc graph.

P1 built the static cheap-arc graph (`/tmp/large_cheap_arc_graph_knn80.pkl`):
25493 cheap edges, mean degree 24.3, 23 isolated nodes (out-degree 0).

Strategy:
1. Load the cheap-arc graph (precomputed).
2. Multi-start nearest-neighbor Hamilton path on the graph:
   For each start node (sweep), greedy choose next unvisited node
   with a CHEAP outgoing edge.
3. When stuck (no cheap out-edge to unvisited), allow ONE exception
   arc (use compute_transfer with dv_exc). Budget: 5 total.
4. Walk the resulting perm via walk_perm_chrono to verify time-
   respecting feasibility.
5. Keep the longest feasible-prefix; bank if 1051/1051.

This is fundamentally different from greedy_findxfer:
- find_earliest_transfer commits to t_ready time → finds best NEXT
  by EARLIEST tof. Misses cheap windows at OTHER times.
- Cheap-arc graph says: ∃ (td, tof) with cheap arc. The
  `best_td, best_tof` hint lets us PICK that window.

Even if the Hamilton path doesn't fully bank, the longest feasible
prefix is informative.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def load_graph(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def greedy_hamilton(kt, cheap_adj, min_dv_edges, start, n_exc_budget=5,
                     verbose=False):
    """NN-greedy Hamilton path on the cheap-arc graph.

    cheap_adj: {i: [(j, dv, td, tof), ...]} sorted by dv ascending.
    min_dv_edges: {(i,j): (dv, td, tof)} for ALL evaluated pairs
    (not just cheap; used for fallback exception lookups).
    """
    n = kt.n
    visited = {start}
    perm = [start]
    n_exc = 0
    bridges = []  # (i, j, dv, td_hint, tof_hint)
    cur = start
    while len(visited) < n:
        # Try cheap out-edges first
        next_node = None
        next_dv = None
        next_td = None
        next_tof = None
        is_exc = False
        for (j, dv, td, tof) in cheap_adj.get(cur, []):
            if j not in visited:
                next_node = j
                next_dv = dv
                next_td = td
                next_tof = tof
                break
        # If no cheap out-edge, try exception (need to evaluate fresh)
        if next_node is None and n_exc < n_exc_budget:
            # Find any unvisited j such that compute_transfer can be
            # ≤ dv_exc at some (td, tof). Use k-NN extrapolation.
            best_exc = None
            unvisited = list(set(range(n)) - visited)
            for j in unvisited[:200]:  # cap to avoid quadratic
                # Sample a few (td, tof) at dv_exc cap
                for td in np.linspace(0, kt.max_time * 0.9, 4):
                    for tof in np.linspace(0.1, 30, 4):
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
            if best_exc is not None:
                next_node, next_dv, next_td, next_tof = best_exc
                is_exc = True
        if next_node is None:
            # Stuck — abandon
            if verbose:
                print(f"  stuck at {cur} (visited {len(visited)})",
                      flush=True)
            return perm, bridges, n_exc, False
        perm.append(next_node)
        visited.add(next_node)
        bridges.append((cur, next_node, next_dv, next_td, next_tof,
                         is_exc))
        if is_exc:
            n_exc += 1
        cur = next_node
    return perm, bridges, n_exc, True


def build_cheap_adj(cheap_edges):
    """Convert {(i,j): (dv, td, tof)} to {i: [(j, dv, td, tof), ...]}
    sorted by dv ascending."""
    adj = {}
    for (i, j), (dv, td, tof) in cheap_edges.items():
        adj.setdefault(i, []).append((j, dv, td, tof))
    for i in adj:
        adj[i].sort(key=lambda t: t[1])
    return adj


def walk_perm_with_hints(kt, perm, bridges):
    """Walk the perm using the cheap-arc (td, tof) hints as a seed
    for find_earliest_transfer. Returns (times, tofs, ok)."""
    times = []
    tofs = []
    t_ready = 0.0
    for k in range(len(perm) - 1):
        i, j = perm[k], perm[k + 1]
        # Use the hint as the FIRST guess; fall back to scan if hint
        # infeasible at t_ready
        _, _, _, td_hint, tof_hint, is_exc = bridges[k]
        # If td_hint < t_ready, must use t_ready
        td_use = max(td_hint, t_ready)
        if td_use + tof_hint > kt.max_time:
            return times, tofs, False
        cap = kt.dv_exc if is_exc else kt.dv_thr
        dv = kt.compute_transfer(i, j, float(td_use), float(tof_hint))
        if dv > cap:
            # Hint failed at adjusted td; scan via find_earliest_transfer
            tof_actual, dv_actual = find_earliest_transfer(
                kt, i, j, t_ready, cap, tof_window=30.0, n_steps=200)
            if tof_actual is None:
                return times, tofs, False
            times.append(t_ready)
            tofs.append(tof_actual)
            t_ready = t_ready + tof_actual
        else:
            times.append(td_use)
            tofs.append(tof_hint)
            t_ready = td_use + tof_hint
    return times, tofs, True


def main(problem="large", graph_path=None, n_start_scan=20,
         exc_budget=5, verbose=False):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    if graph_path is None:
        graph_path = "/tmp/large_cheap_arc_graph_knn80.pkl"
    print(f"Loading cheap-arc graph from {graph_path}", flush=True)
    g = load_graph(graph_path)
    cheap_edges = g["cheap_edges"]
    min_dv_edges = g["min_dv_edges"]
    cheap_adj = build_cheap_adj(cheap_edges)
    print(f"Loaded: {len(cheap_edges)} cheap edges, "
          f"avg out-degree {sum(len(v) for v in cheap_adj.values()) / kt.n:.1f}",
          flush=True)

    # Pick start candidates: nodes with high out-degree
    starts = sorted(cheap_adj.keys(),
                    key=lambda i: -len(cheap_adj[i]))[:n_start_scan]
    print(f"Trying {len(starts)} starts with highest out-degree",
          flush=True)
    best_result = None  # (n_visited, start, perm, bridges, n_exc)
    t0 = time.time()
    for si, start in enumerate(starts):
        perm, bridges, n_exc, ok = greedy_hamilton(
            kt, cheap_adj, min_dv_edges, start,
            n_exc_budget=exc_budget, verbose=verbose)
        n_visited = len(perm)
        if best_result is None or n_visited > best_result[0]:
            print(f"  start={start}: visited={n_visited}/{kt.n}, "
                  f"n_exc={n_exc}, complete={ok}", flush=True)
            best_result = (n_visited, start, perm, bridges, n_exc)
    wall = time.time() - t0
    print(f"\nHamilton search done in {wall:.0f}s", flush=True)
    n_visited, start, perm, bridges, n_exc = best_result
    print(f"BEST: start={start}, visited={n_visited}/{kt.n}, n_exc={n_exc}",
          flush=True)
    if n_visited < kt.n:
        return {"status": "incomplete", "best_n": n_visited,
                "best_start": start}
    # Walk it
    print(f"Walking perm with hints...", flush=True)
    times, tofs, walk_ok = walk_perm_with_hints(kt, perm, bridges)
    if not walk_ok:
        print("  walk failed", flush=True)
        return {"status": "walk_failed"}
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    print(f"FINAL: mk={f[0]:.4f}, feas={feas}, fitness={list(f)}",
          flush=True)
    info = {"problem": problem, "n": kt.n,
            "mk": float(f[0]), "feasible": feas}
    if feas:
        p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
        print(f"BANKED: {p}", flush=True)
    return info


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    gp = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(main(n_start_scan=ns, graph_path=gp), indent=2))
