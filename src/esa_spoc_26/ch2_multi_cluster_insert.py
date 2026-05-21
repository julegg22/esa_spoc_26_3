"""Ch2 KTTSP — multi-cluster insertion LNS for larger missing-node sets.

Small instance (n=49) had 3 missing nodes forming one tight cluster.
Medium (n=181) and large (n=1051) likely have multiple disjoint
small clusters in the missing set (per O-007 structural pattern).

Strategy:
1. Take a partial perm + missing nodes M.
2. Cluster M by orbital proximity (cheap-arc reachability among M).
3. For each cluster C ⊆ M with |C| ≤ 4: enumerate insertion positions
   × orderings; pick best feasible insertion.
4. For singletons or after cluster insertion: greedy node-by-node
   reinsertion via find_earliest_transfer.
5. Polish: 2-opt + or-opt on the completed perm.
"""

from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def cluster_missing_nodes(kt, missing, thr_cheap=100.0):
    """Group missing nodes by cheap-arc connectivity (graph components).
    Two missing nodes are in the same cluster if they have a transfer
    with Δv ≤ thr_cheap at some (td, tof).
    """
    n_m = len(missing)
    if n_m <= 1:
        return [[v] for v in missing]
    # Build proximity graph: edge if any (td, tof) gives Δv ≤ thr_cheap
    # Use minimum-Δv over a coarse (td, tof) grid for speed
    tds = np.linspace(0, kt.max_time, 20)
    tofs = np.linspace(0.5, 30, 15)
    adj = {v: set() for v in missing}
    for i, vi in enumerate(missing):
        for vj in missing[i + 1:]:
            min_dv_ij = float("inf")
            min_dv_ji = float("inf")
            for td in tds:
                for tof in tofs:
                    if td + tof > kt.max_time:
                        continue
                    dv = kt.compute_transfer(vi, vj, float(td), float(tof))
                    if dv < min_dv_ij:
                        min_dv_ij = dv
                    dv2 = kt.compute_transfer(vj, vi, float(td), float(tof))
                    if dv2 < min_dv_ji:
                        min_dv_ji = dv2
            if min(min_dv_ij, min_dv_ji) <= thr_cheap:
                adj[vi].add(vj)
                adj[vj].add(vi)
    # Connected components
    visited = set()
    clusters = []
    for v in missing:
        if v in visited:
            continue
        comp = []
        stack = [v]
        while stack:
            u = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            comp.append(u)
            for w in adj.get(u, []):
                if w not in visited:
                    stack.append(w)
        clusters.append(comp)
    return clusters


def insert_cluster(kt, partial_perm, cluster):
    """Enumerate all positions × all orderings of `cluster` in
    `partial_perm`; return the best feasible insertion or None.
    Skips combinatorial explosions (k > 5)."""
    if len(cluster) > 5:
        return None
    L = len(partial_perm)
    orderings = list(itertools.permutations(cluster))
    best = None  # (mk, perm, times, tofs)
    for p in range(L):
        for chain in orderings:
            cand = list(partial_perm[:p + 1]) + list(chain) + \
                list(partial_perm[p + 1:])
            times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
            if not ok:
                continue
            mk = times[-1] + tofs[-1]
            x = times + tofs + [float(v) for v in cand]
            f = kt.fitness(x)
            if kt.is_feasible(f) and (best is None or mk < best[0]):
                best = (mk, cand, times, tofs)
    return best


def greedy_insert_node(kt, perm, node, tof_window=18.0, n_steps=180):
    """Re-insert a single node into perm at the best position by
    chronological walk + makespan minimisation."""
    best = None
    for pos in range(1, len(perm) + 1):
        cand = [*perm[:pos], node, *perm[pos:]]
        times, tofs, _, ok, _, _ = walk_perm_chrono(
            kt, cand, tof_window=tof_window, n_steps=n_steps)
        if not ok:
            continue
        mk = times[-1] + tofs[-1] if times else 0.0
        x = times + tofs + [float(v) for v in cand]
        f = kt.fitness(x)
        if kt.is_feasible(f) and (best is None or mk < best[0]):
            best = (mk, cand, times, tofs)
    return best


def multi_cluster_insert(kt, partial_perm, missing, verbose=True):
    """Top-level: cluster missing nodes, insert each cluster, then
    greedy-fill remaining singletons."""
    if verbose:
        print(f"Clustering {len(missing)} missing nodes...", flush=True)
    clusters = cluster_missing_nodes(kt, missing)
    if verbose:
        print(f"  found {len(clusters)} clusters: "
              f"{[len(c) for c in clusters]}", flush=True)
    # Sort clusters by size descending (insert big ones first)
    clusters.sort(key=len, reverse=True)
    cur_perm = list(partial_perm)
    times, tofs = None, None
    for ci, c in enumerate(clusters):
        if len(c) > 5:
            # split big cluster into singletons; will be handled in
            # the greedy fill pass
            if verbose:
                print(f"  cluster {ci} too big ({len(c)}); deferring",
                      flush=True)
            continue
        t0 = time.time()
        result = insert_cluster(kt, cur_perm, c)
        if result is None:
            if verbose:
                print(f"  cluster {ci} (size {len(c)}): NO feasible insertion",
                      flush=True)
            continue
        mk, new_perm, new_times, new_tofs = result
        cur_perm = new_perm
        times = new_times
        tofs = new_tofs
        if verbose:
            wall = time.time() - t0
            print(f"  cluster {ci} ({c}): mk={mk:.2f}, "
                  f"wall={wall:.1f}s", flush=True)
    # Greedy-fill any remaining unvisited nodes (singletons + dropped clusters)
    in_perm = set(cur_perm)
    remaining = [v for v in missing if v not in in_perm]
    if remaining and verbose:
        print(f"Greedy-fill {len(remaining)} remaining: {remaining}",
              flush=True)
    for v in remaining:
        result = greedy_insert_node(kt, cur_perm, v)
        if result is None:
            if verbose:
                print(f"  node {v}: NO feasible insertion", flush=True)
            continue
        mk, new_perm, new_times, new_tofs = result
        cur_perm = new_perm
        times = new_times
        tofs = new_tofs
        if verbose:
            print(f"  node {v}: mk={mk:.2f}", flush=True)
    return cur_perm, times, tofs


def main(inst_path, partial_perm_or_path,
         problem="medium",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst_path)
    # Resolve partial perm
    if isinstance(partial_perm_or_path, str):
        with open(partial_perm_or_path) as fh:
            data = json.load(fh)
        partial = data
    else:
        partial = list(partial_perm_or_path)
    missing = sorted(set(range(kt.n)) - set(partial))
    print(f"Partial: {len(partial)} nodes; missing: {len(missing)}",
          flush=True)
    if not missing:
        print("Nothing to insert; partial is already a tour.", flush=True)
        return
    full_perm, times, tofs = multi_cluster_insert(kt, partial, missing)
    if full_perm is None or len(full_perm) != kt.n:
        print(f"Failed: final perm length = {len(full_perm) if full_perm else 0}",
              flush=True)
        return
    x = times + tofs + [float(v) for v in full_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    print(f"Result: mk={f[0]:.3f}, feas={feas}, fitness={f}",
          flush=True)
    if feas:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        print(f"BANKED: {p}", flush=True)


if __name__ == "__main__":
    # Default usage from CLI is via Python import; placeholder run
    if len(sys.argv) > 1:
        problem = sys.argv[1]
        inst = (f"reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
                f"Salesperson Problem/problems/"
                f"{'easy' if problem == 'small' else problem}.kttsp")
        partial_path = sys.argv[2]
        main(inst, partial_path, problem=problem)
