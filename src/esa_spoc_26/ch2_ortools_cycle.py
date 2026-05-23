"""Ch2 KTTSP large — Hamilton CYCLE per component (rotatable).

OR-tools Hamilton path has fixed start/end nodes; we found all 4
intra paths but no inter-component stitch worked because the END
nodes don't admit bridges to next-component START.

If a Hamilton CYCLE exists in each component, we have flexible
endpoints: for any node X on the cycle, the Hamilton path can
start at X and end at X's cycle-predecessor.

Solve TSP-with-return per component. Then for stitching:
1. Find inter-component bridges: pair (a ∈ c_k, b ∈ c_{k+1}) with
   feasible Lambert transfer.
2. Make a Hamilton path of c_k that ends at a, and Hamilton path
   of c_{k+1} that starts at b.
3. Stitch.
"""

from __future__ import annotations

import itertools
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_component_aware import find_components
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_ortools_hamilton import build_distance_matrix


INF = int(1e6)
SCALE = 100


def ortools_hamilton_cycle(distance_matrix, time_limit_s=60):
    """TSP with return: standard OR-tools routing. Returns ordered
    cycle (last == first implicit)."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    n = len(distance_matrix)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(from_idx, to_idx):
        f = manager.IndexToNode(from_idx)
        t = manager.IndexToNode(to_idx)
        return int(distance_matrix[f, t])
    transit_idx = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    sp.time_limit.seconds = int(time_limit_s)

    sol = routing.SolveWithParameters(sp)
    if sol is None:
        return None, None
    index = routing.Start(0)
    cycle = []
    total = 0
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        cycle.append(node)
        prev = index
        index = sol.Value(routing.NextVar(index))
        if not routing.IsEnd(index):
            total += int(distance_matrix[
                manager.IndexToNode(prev), manager.IndexToNode(index)])
    return cycle, total / SCALE


def find_bridge(kt, src, candidates):
    """Find cheapest exc-or-cheap transfer from src to any in candidates.
    Returns (dst, dv, td, tof) or None."""
    best = None
    for dst in candidates:
        for td in np.linspace(0, kt.max_time * 0.9, 8):
            for tof in np.linspace(0.1, 30, 8):
                if td + tof > kt.max_time:
                    continue
                dv = kt.compute_transfer(src, dst, float(td), float(tof))
                if dv <= kt.dv_exc:
                    if best is None or dv < best[1]:
                        best = (int(dst), float(dv), float(td), float(tof))
                    break
    return best


def rotate_cycle_to_endpoints(cycle, start_node, end_node):
    """Given a Hamilton cycle [n_0, n_1, ..., n_{L-1}] (n_L == n_0
    implicit), return a Hamilton PATH starting at start_node and
    ending at end_node. Possible only if (end_node, start_node) is
    an edge of the cycle. Returns None if not possible."""
    L = len(cycle)
    if start_node not in cycle or end_node not in cycle:
        return None
    si = cycle.index(start_node)
    ei = cycle.index(end_node)
    # We want path = cycle with edge (end, start) removed.
    # cycle is n_0 → n_1 → ... → n_{L-1} → n_0
    # We need an edge end_node → start_node in cycle, i.e.,
    # (cycle[ei] → cycle[(ei+1) % L]) where cycle[(ei+1) % L] == start_node
    if cycle[(ei + 1) % L] != start_node:
        return None
    # Path starts at start_node and ends at end_node, going through
    # the cycle in order
    path = []
    i = si
    for _ in range(L):
        path.append(cycle[i])
        i = (i + 1) % L
    # path[0] == start_node, path[-1] == end_node
    assert path[0] == start_node
    assert path[-1] == end_node
    return path


def main(problem="large", graph_path=None, intra_time_s=120,
         cycle_cache_path=None):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    if graph_path is None:
        graph_path = "/tmp/large_cheap_arc_graph_knn200.pkl"
    with open(graph_path, "rb") as f:
        g = pickle.load(f)
    cheap_edges = g["cheap_edges"]
    comps = find_components(cheap_edges, kt.n)
    comps = {int(k): v for k, v in comps.items()}
    comp_ids = sorted(comps.keys(), key=lambda c: -len(comps[c]))
    print(f"Components: {[len(comps[c]) for c in comp_ids]}",
          flush=True)

    if cycle_cache_path is None:
        cycle_cache_path = f"/tmp/{problem}_ortools_cycles.pkl"

    cycles = {}
    if Path(cycle_cache_path).exists():
        with open(cycle_cache_path, "rb") as f:
            cycles = pickle.load(f)
        print(f"Loaded {len(cycles)} cached cycles", flush=True)

    for ci in comp_ids:
        if ci in cycles:
            print(f"  comp {ci}: cycle cached", flush=True)
            continue
        nodes = comps[ci]
        t0 = time.time()
        D, node_map = build_distance_matrix(nodes, cheap_edges, kt.dv_thr)
        cycle_idx, total_dv = ortools_hamilton_cycle(D, time_limit_s=intra_time_s)
        if cycle_idx is None or len(cycle_idx) != len(nodes):
            print(f"  comp {ci} ({len(nodes)}): cycle FAILED", flush=True)
            cycles[ci] = None
            continue
        # Map back, check INF
        cycle = [node_map[k] for k in cycle_idx]
        inf_arcs = sum(1 for i in range(len(cycle_idx))
                       if D[cycle_idx[i], cycle_idx[(i + 1) % len(cycle_idx)]] >= INF)
        if inf_arcs > 2:
            print(f"  comp {ci} ({len(nodes)}): cycle has {inf_arcs} INF "
                  f"arcs (too many)", flush=True)
            cycles[ci] = None
            continue
        print(f"  comp {ci} ({len(nodes)}): cycle in {time.time()-t0:.0f}s, "
              f"dv={total_dv:.0f}, INF arcs={inf_arcs}",
              flush=True)
        cycles[int(ci)] = [int(v) for v in cycle]
        with open(cycle_cache_path, "wb") as f:
            pickle.dump(cycles, f)

    if any(cycles[c] is None for c in comp_ids):
        return {"status": "cycle_failed"}

    # Now find a feasible stitch: for each ordering, find bridges
    # between consecutive components AT SPECIFIC node pairs that
    # admit (end_in_c_k, start_in_c_{k+1}) endpoint constraints.
    print(f"\nSearching feasible stitches across orderings...",
          flush=True)
    best = None
    t0 = time.time()
    for ordering in itertools.permutations(comp_ids):
        # For each pair of consecutive components, find the best
        # (end_node, start_node) such that:
        # - end_node ∈ c_k cycle
        # - start_node ∈ c_{k+1} cycle
        # - (end_node, start_node) bridges feasibly
        # - end_node's cycle-successor in c_k cycle is the
        #   "skipped" edge, which lets us form a path
        # For ALL nodes in c_k, check if any bridges to any in c_{k+1}
        # (we accept ANY end_node; the cycle->path conversion uses
        # end_node's cycle-successor as the path start)
        path_chain = []
        ok = True
        for k in range(len(ordering)):
            cycle = cycles[ordering[k]]
            if k == 0:
                # First component: any start. Pick end_node such that
                # it bridges to NEXT component
                if k + 1 < len(ordering):
                    next_cycle = cycles[ordering[k + 1]]
                    # Sample nodes (try a few to keep search bounded)
                    best_bridge = None
                    for end_node in cycle:
                        br = find_bridge(kt, end_node, next_cycle)
                        if br is None:
                            continue
                        if best_bridge is None or br[1] < best_bridge[1]:
                            start_in_next = br[0]
                            start_node = cycle[(cycle.index(end_node) + 1) % len(cycle)]
                            path_k = rotate_cycle_to_endpoints(
                                cycle, start_node, end_node)
                            if path_k is None:
                                continue
                            best_bridge = (start_in_next, br[1], br[2], br[3],
                                            path_k, end_node)
                    if best_bridge is None:
                        ok = False
                        break
                    start_in_next, br_dv, br_td, br_tof, path_k, end_node = best_bridge
                    path_chain.append((path_k, ordering[k]))
                    next_start = start_in_next
                else:
                    # only one component
                    path_chain.append((cycle, ordering[k]))
            else:
                cycle = cycles[ordering[k]]
                if next_start not in cycle:
                    ok = False
                    break
                if k + 1 < len(ordering):
                    # Find end_node in cycle that bridges to NEXT
                    next_cycle = cycles[ordering[k + 1]]
                    best_bridge = None
                    for end_node in cycle:
                        # Skip cases where end == start (cycle of 1 not valid)
                        if end_node == next_start:
                            continue
                        # Cycle path needs (end_node + 1) % L == start_node
                        # → start_node is fixed at next_start, so
                        # end_node = next_start's cycle predecessor
                        # (only ONE valid end_node given start_node)
                        idx_ns = cycle.index(next_start)
                        candidate_end = cycle[(idx_ns - 1) % len(cycle)]
                        if end_node != candidate_end:
                            continue
                        # That's the only valid end. Check bridge.
                        br = find_bridge(kt, end_node, next_cycle)
                        if br is None:
                            ok = False
                        else:
                            best_bridge = (br[0], br[1], br[2], br[3],
                                            candidate_end)
                        break
                    if not best_bridge:
                        ok = False
                        break
                    new_next_start, br_dv, br_td, br_tof, end_node = best_bridge
                    path_k = rotate_cycle_to_endpoints(cycle, next_start,
                                                         end_node)
                    if path_k is None:
                        ok = False
                        break
                    path_chain.append((path_k, ordering[k]))
                    next_start = new_next_start
                else:
                    # Last component: any end. Use cycle starting at next_start
                    idx_ns = cycle.index(next_start)
                    end_node = cycle[(idx_ns - 1) % len(cycle)]
                    path_k = rotate_cycle_to_endpoints(cycle, next_start,
                                                         end_node)
                    if path_k is None:
                        ok = False
                        break
                    path_chain.append((path_k, ordering[k]))
        if not ok:
            continue
        # Stitch
        full_perm = []
        for p, _ in path_chain:
            full_perm.extend(p)
        if len(full_perm) != kt.n:
            continue
        # Walk
        times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
            kt, full_perm, tof_window=30.0, n_steps=200)
        if not walk_ok or not times:
            continue
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        if not kt.is_feasible(f):
            continue
        mk = float(f[0])
        if best is None or mk < best[0]:
            print(f"  ordering {ordering}: FEASIBLE mk={mk:.4f}",
                  flush=True)
            best = (mk, full_perm, list(times), list(tofs), list(f),
                     ordering)
    wall = time.time() - t0
    print(f"\nStitch search wall: {wall:.0f}s", flush=True)
    if best is None:
        return {"status": "no_feasible_stitch"}
    mk, perm, times, tofs, f, ordering = best
    x = times + tofs + [float(v) for v in perm]
    print(f"BEST FEASIBLE: mk={mk:.4f}, ordering={ordering}", flush=True)
    p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
    p.write_text(json.dumps([{"decisionVector": list(x),
                              "problem": problem,
                              "challenge": CHALLENGE}]))
    print(f"BANKED: {p}", flush=True)
    return {"problem": problem, "n": kt.n, "mk": float(mk),
            "feasible": True, "banked": str(p)}


if __name__ == "__main__":
    its = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    print(json.dumps(main(intra_time_s=its), indent=2))
