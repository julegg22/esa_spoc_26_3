"""Ch2 KTTSP large — component-aware Hamilton path.

Analysis of the dense cheap-arc graph (k_nn=200, 6×6) revealed:

    4 strongly-connected components
    Sizes: [601, 150, 150, 150]

With 5 exception budget, we need 3 exc-bridges to traverse the 4
components, leaving 2 excs for in-component recovery.

Pipeline:
1. Find Hamilton path within each component (NN-greedy on the
   intra-component cheap edges).
2. For each ordering of components (e.g., big → small1 → small2
   → small3), find the cheapest exc-bridge between consecutive
   components.
3. Concatenate; walk via walk_perm_chrono; verify feasible.
4. Try multiple component orderings and intra-component start
   nodes; bank the best.
"""

from __future__ import annotations

import itertools
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_cheap_arc_hamilton import build_cheap_adj
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def find_components(cheap_edges, n):
    """Return component_id list for n nodes (using scipy SCC)."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    rows, cols = zip(*cheap_edges.keys())
    data = np.ones(len(rows), dtype=np.int8)
    adj = csr_matrix((data, (rows, cols)), shape=(n, n))
    n_comp, labels = connected_components(adj, directed=True,
                                            connection='strong')
    comps = {}
    for i, c in enumerate(labels):
        comps.setdefault(c, []).append(i)
    return comps


def intra_hamilton(kt, adj, comp_nodes, start, max_backtrack=5000,
                    rng=None):
    """NN-greedy Hamilton path WITHIN comp_nodes with backtracking.

    Each `options_stack` frame stores (cur_node, remaining_candidates).
    On dead-end, pop frames until one has remaining options.
    """
    comp_set = set(comp_nodes)
    n = len(comp_set)
    if rng is None:
        rng = np.random.default_rng(0)
    perm = [start]
    visited = {start}
    bridges = []
    # options_stack[k] = (node_at_depth_k, remaining_candidates_at_depth_k)
    options_stack = []
    cur = start
    n_bt = 0
    while len(visited) < n:
        candidates = [(j, dv, td, tof)
                      for (j, dv, td, tof) in adj.get(cur, [])
                      if j in comp_set and j not in visited]
        if candidates:
            # Randomize: with probability 0.3 pick a random one,
            # else cheapest — gives diversity across restarts
            rng.shuffle(candidates)
            options_stack.append((cur, candidates[1:]))
            j, dv, td, tof = candidates[0]
            perm.append(j)
            visited.add(j)
            bridges.append((cur, j, dv, td, tof))
            cur = j
            continue
        # Dead-end: backtrack until a frame has alternatives
        if n_bt >= max_backtrack:
            return perm, bridges, False
        while options_stack:
            n_bt += 1
            if n_bt > max_backtrack:
                return perm, bridges, False
            # Undo the last advance
            last_cur, alt = options_stack[-1]
            popped = perm.pop()
            visited.discard(popped)
            bridges.pop()
            cur = last_cur
            if alt:
                # Take next alternative at this frame
                j, dv, td, tof = alt[0]
                options_stack[-1] = (last_cur, alt[1:])
                perm.append(j)
                visited.add(j)
                bridges.append((last_cur, j, dv, td, tof))
                cur = j
                break
            else:
                # No more alternatives; pop frame and try deeper
                options_stack.pop()
        else:
            # options_stack empty — exhausted
            return perm, bridges, False
    return perm, bridges, True


def find_exc_bridge(kt, src_node, dst_comp_nodes):
    """Find the cheapest exc-or-cheap arc from src_node to any node
    in dst_comp_nodes. Returns (dst, dv, td, tof) or None."""
    best = None
    for dst in dst_comp_nodes:
        for td in np.linspace(0, kt.max_time * 0.9, 8):
            for tof in np.linspace(0.1, 30, 8):
                if td + tof > kt.max_time:
                    continue
                dv = kt.compute_transfer(src_node, dst, float(td),
                                           float(tof))
                if dv <= kt.dv_exc:
                    if best is None or dv < best[1]:
                        best = (dst, dv, float(td), float(tof))
    return best


def main(problem="large", graph_path=None, max_orderings=8,
          n_intra_starts=4):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    if graph_path is None:
        graph_path = "/tmp/large_cheap_arc_graph_knn200.pkl"
    with open(graph_path, "rb") as f:
        g = pickle.load(f)
    cheap_adj = build_cheap_adj(g["cheap_edges"])
    print(f"Graph: {len(g['cheap_edges'])} cheap edges, "
          f"avg out-degree {sum(len(v) for v in cheap_adj.values()) / kt.n:.1f}",
          flush=True)
    comps = find_components(g["cheap_edges"], kt.n)
    print(f"Components: {sorted([len(c) for c in comps.values()], reverse=True)}",
          flush=True)
    comp_ids = sorted(comps.keys(), key=lambda c: -len(comps[c]))
    print(f"Component IDs ordered by size: {comp_ids}", flush=True)

    # For each component, find ONE good Hamilton path
    intra = {}
    for ci in comp_ids:
        nodes = comps[ci]
        n_attempts = min(len(nodes), n_intra_starts)
        best = None
        best_n_visited = 0
        t_ci = time.time()
        for attempt in range(n_attempts):
            # Each attempt uses a DIFFERENT rng seed → different
            # shuffle order at every step
            rng_attempt = np.random.default_rng(attempt * 100 + 7)
            start = nodes[attempt % len(nodes)]
            perm, bridges, ok = intra_hamilton(
                kt, cheap_adj, nodes, start, max_backtrack=20000,
                rng=rng_attempt)
            n_v = len(perm)
            if ok:
                if best is None or sum(b[2] for b in bridges) \
                        < sum(b[2] for b in best[1]):
                    best = (perm, bridges)
                    print(f"  comp {ci}: FULL Hamilton from start={start} "
                          f"(attempt {attempt + 1}/{n_attempts}, "
                          f"intra dv={sum(b[2] for b in bridges):.0f})",
                          flush=True)
                    break
            elif n_v > best_n_visited:
                best_n_visited = n_v
                if attempt % 20 == 0:
                    print(f"  comp {ci} attempt {attempt}: best partial = "
                          f"{best_n_visited}/{len(nodes)}", flush=True)
        if best is None:
            print(f"  comp {ci} ({len(nodes)}): NO full Hamilton "
                  f"(best partial = {best_n_visited}/{len(nodes)}, "
                  f"wall={time.time()-t_ci:.0f}s)", flush=True)
        intra[ci] = best

    if any(intra[c] is None for c in comp_ids):
        return {"status": "intra_hamilton_failed"}

    # Try orderings of components (start with biggest first)
    print(f"\nTrying {min(max_orderings, 24)} orderings of "
          f"{len(comp_ids)} components", flush=True)
    best_result = None
    t0 = time.time()
    for ordering in itertools.permutations(comp_ids):
        if comp_ids.index(ordering[0]) != 0:
            # Always start with biggest comp
            continue
        # Stitch intra-Hamiltons with exc bridges
        full_perm = list(intra[ordering[0]][0])
        all_bridges = list(intra[ordering[0]][1])
        ok = True
        for k in range(len(ordering) - 1):
            src = full_perm[-1]
            next_comp_nodes = comps[ordering[k + 1]]
            # Find best exc-bridge from src to next component
            br = find_exc_bridge(kt, src, next_comp_nodes)
            if br is None:
                ok = False
                break
            dst, dv, td, tof = br
            # Re-orient the next intra-Hamilton to start at dst
            next_perm, next_bridges, intra_ok = intra_hamilton(
                kt, cheap_adj, comps[ordering[k + 1]], dst)
            if not intra_ok:
                ok = False
                break
            all_bridges.append((src, dst, dv, td, tof))  # exc bridge
            full_perm.extend(next_perm)
            all_bridges.extend(next_bridges)
        if not ok:
            continue
        # Verify perm size
        if len(full_perm) != kt.n:
            continue
        # Walk
        times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
            kt, full_perm, tof_window=30.0, n_steps=200)
        if not walk_ok or not times:
            continue
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        mk = float(f[0])
        if feas:
            if best_result is None or mk < best_result[0]:
                print(f"  ordering {ordering}: mk={mk:.2f}, FEASIBLE ✓",
                      flush=True)
                best_result = (mk, ordering, full_perm, list(times),
                                list(tofs), list(f))
        else:
            if best_result is None:
                print(f"  ordering {ordering}: walked but infeasible "
                      f"fitness={list(f)}", flush=True)
    wall = time.time() - t0
    print(f"\nOrderings search: {wall:.0f}s", flush=True)
    if best_result is None:
        return {"status": "no_feasible_ordering"}
    mk, ordering, full_perm, times, tofs, f = best_result
    x = times + tofs + [float(v) for v in full_perm]
    print(f"BEST FEASIBLE: mk={mk:.4f}, ordering={ordering}",
          flush=True)
    p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
    p.write_text(json.dumps([{"decisionVector": list(x),
                              "problem": problem,
                              "challenge": CHALLENGE}]))
    print(f"BANKED: {p}", flush=True)
    return {"problem": problem, "n": kt.n, "mk": float(mk),
            "feasible": True, "banked": str(p)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
