"""Ch2 KTTSP large — intra-component Hamilton via OR-tools TSP.

Component-aware analysis (O-011) found the cheap-arc graph has 4
strongly-connected components: [601, 150, 150, 150]. NN-greedy +
backtracking can only find partial Hamilton paths (558/601, 128/150,
etc.) — needs a gold-standard TSP heuristic.

OR-tools' guided local search + savings handles 1000-node TSPs in
seconds. Here:

1. For each component, build directed-graph distance matrix:
   - cheap arc (i, j): dist = dv (≤ kt.dv_thr, ≤ 100)
   - missing or > dv_thr: dist = INT_MAX_PROXY (1e6) → never chosen
2. Solve asymmetric TSP per component (Hamilton path = TSP-without-
   return).
3. Stitch components via exc-bridges (3 inter-bridges + 2 buffer).
4. Walk via walk_perm_chrono; bank if feasible.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_cheap_arc_hamilton import build_cheap_adj
from esa_spoc_26.ch2_component_aware import find_components
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


INF = int(1e6)
SCALE = 100  # dv float → integer scale


def ortools_hamilton_path(distance_matrix, time_limit_s=30):
    """Solve ASYMMETRIC TSP without return (Hamilton path) via
    OR-tools routing. Returns ordered list of node indices."""
    from ortools.constraint_solver import pywrapcp
    from ortools.constraint_solver import routing_enums_pb2

    n = len(distance_matrix)
    # Hamilton path = TSP where last node has 0-cost return to start
    # OR-tools natively does TSP-with-return. To get Hamilton path,
    # add a dummy depot connected to all with 0 cost both ways.
    # Then remove the dummy from the result.
    n_with_dummy = n + 1
    dist_with_dummy = np.zeros((n_with_dummy, n_with_dummy), dtype=int)
    dist_with_dummy[:n, :n] = distance_matrix
    # Dummy depot (index n): 0 cost from any node, 0 cost to any node
    # → the tour starts and ends at the dummy without cost penalty
    dist_with_dummy[n, :] = 0
    dist_with_dummy[:, n] = 0

    manager = pywrapcp.RoutingIndexManager(n_with_dummy, 1, n)
    routing = pywrapcp.RoutingModel(manager)

    def dist_cb(from_idx, to_idx):
        f = manager.IndexToNode(from_idx)
        t = manager.IndexToNode(to_idx)
        return int(dist_with_dummy[f, t])
    transit_idx = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_params.time_limit.seconds = int(time_limit_s)

    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return None
    # Extract route (skip dummy depot)
    index = routing.Start(0)
    path = []
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != n:  # skip dummy
            path.append(node)
        index = solution.Value(routing.NextVar(index))
    return path


def build_distance_matrix(comp_nodes, cheap_edges, dv_thr):
    """Directed distance matrix for nodes in comp_nodes.
    cheap_edges[(i,j)] = (dv, td, tof). Returns (dist_matrix,
    node_map) where node_map[k] = original_node_id."""
    node_map = list(comp_nodes)
    idx_of = {v: k for k, v in enumerate(node_map)}
    n = len(node_map)
    D = np.full((n, n), INF, dtype=int)
    for k in range(n):
        D[k, k] = 0
    for (i, j), (dv, td, tof) in cheap_edges.items():
        if i in idx_of and j in idx_of and dv <= dv_thr:
            D[idx_of[i], idx_of[j]] = int(round(dv * SCALE))
    return D, node_map


def find_exc_bridge(kt, src_node, dst_comp_nodes):
    """Cheapest exc-or-cheap arc from src to any node in
    dst_comp_nodes. Sample (td, tof) grid. Returns (dst, dv, td, tof)."""
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


def main(problem="large", graph_path=None, intra_time_s=30,
         intra_cache_path=None):
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
    print(f"Loaded: n={kt.n}, {len(cheap_edges)} cheap edges",
          flush=True)
    comps = find_components(cheap_edges, kt.n)
    # Convert comp ids to plain int for JSON
    comps = {int(k): v for k, v in comps.items()}
    comp_ids = sorted(comps.keys(), key=lambda c: -len(comps[c]))
    print(f"Components: {[len(comps[c]) for c in comp_ids]}",
          flush=True)

    if intra_cache_path is None:
        intra_cache_path = f"/tmp/{problem}_ortools_intra_paths.pkl"

    # Try to load cached intra-paths
    intra_paths = {}
    if Path(intra_cache_path).exists():
        with open(intra_cache_path, "rb") as f:
            intra_paths = pickle.load(f)
        print(f"Loaded {len(intra_paths)} cached intra-paths from "
              f"{intra_cache_path}", flush=True)

    # Intra-component Hamilton via OR-tools
    for ci in comp_ids:
        if ci in intra_paths:
            print(f"  comp {ci}: cached", flush=True)
            continue
        nodes = comps[ci]
        t0 = time.time()
        D, node_map = build_distance_matrix(nodes, cheap_edges, kt.dv_thr)
        path_idx = ortools_hamilton_path(D, time_limit_s=intra_time_s)
        if path_idx is None:
            print(f"  comp {ci} ({len(nodes)}): OR-tools failed",
                  flush=True)
            intra_paths[ci] = None
            continue
        # Verify path covers ALL nodes in comp
        if len(path_idx) != len(nodes):
            print(f"  comp {ci}: OR-tools returned {len(path_idx)}/{len(nodes)}",
                  flush=True)
            intra_paths[ci] = None
            continue
        # Map back to original node IDs
        path = [node_map[k] for k in path_idx]
        # Compute total cost
        total_dv = sum(D[path_idx[i], path_idx[i + 1]]
                       for i in range(len(path_idx) - 1)) / SCALE
        # Check no INF-cost arcs (would mean fake-edge path)
        inf_count = sum(1 for i in range(len(path_idx) - 1)
                        if D[path_idx[i], path_idx[i + 1]] >= INF)
        if inf_count > 2:
            print(f"  comp {ci} ({len(nodes)}): "
                  f"OR-tools path uses {inf_count} INF arcs (too many)",
                  flush=True)
            intra_paths[ci] = None
            continue
        elif inf_count > 0:
            print(f"  comp {ci} ({len(nodes)}): OR-tools used "
                  f"{inf_count} INF arcs (will need {inf_count} exc bridges)",
                  flush=True)
        print(f"  comp {ci} ({len(nodes)}): Hamilton FOUND in "
              f"{time.time()-t0:.0f}s, total intra dv={total_dv:.0f}",
              flush=True)
        intra_paths[int(ci)] = [int(v) for v in path]
        # Save cache incrementally
        with open(intra_cache_path, "wb") as f:
            pickle.dump(intra_paths, f)

    failed = [c for c in comp_ids if intra_paths.get(c) is None]
    if failed:
        return {"status": "or_tools_incomplete",
                "failed_components": [int(c) for c in failed]}

    # Stitch: try all orderings + both directions per component
    print(f"\nStitching {len(comp_ids)} components with exc bridges "
          f"(trying orderings and reversals)", flush=True)
    import itertools as _it
    best_stitch = None
    best_total_bridge_dv = None
    for ordering in _it.permutations(comp_ids):
        for dir_mask in range(2 ** len(comp_ids)):
            dirs = [bool((dir_mask >> i) & 1)
                    for i in range(len(comp_ids))]
            # dirs[i]=True means reverse intra_paths[ordering[i]]
            paths = []
            for i, ci in enumerate(ordering):
                p = list(intra_paths[int(ci)])
                if dirs[i]:
                    p = p[::-1]
                paths.append(p)
            # Try to find bridges between consecutive components
            full = list(paths[0])
            ok = True
            total_bridge_dv = 0
            bridges_used = []
            for k in range(len(ordering) - 1):
                src = int(full[-1])
                next_start = int(paths[k + 1][0])
                # Try direct bridge to the FIRST node of next path
                # (since we're committed to its direction)
                br_dv = None
                for td in np.linspace(0, kt.max_time * 0.9, 8):
                    for tof in np.linspace(0.1, 30, 8):
                        if td + tof > kt.max_time:
                            continue
                        dv = kt.compute_transfer(src, next_start,
                                                   float(td), float(tof))
                        if dv <= kt.dv_exc:
                            if br_dv is None or dv < br_dv:
                                br_dv = dv
                                br_td, br_tof = float(td), float(tof)
                            break  # break tof, try next td
                if br_dv is None:
                    ok = False
                    break
                bridges_used.append((src, next_start, br_dv, br_td, br_tof))
                full.extend(paths[k + 1])
                total_bridge_dv += br_dv
            if ok:
                if best_stitch is None or total_bridge_dv < best_total_bridge_dv:
                    best_stitch = (full, ordering, dirs, bridges_used)
                    best_total_bridge_dv = total_bridge_dv
                    print(f"  ordering {ordering}, dirs {dirs}: "
                          f"all bridges OK, total_bridge_dv={total_bridge_dv:.0f}",
                          flush=True)
    if best_stitch is None:
        return {"status": "no_stitch"}
    full_perm, ordering, dirs, bridges_used = best_stitch
    print(f"\nBEST STITCH: ordering={ordering}, dirs={dirs}, "
          f"total_bridge_dv={best_total_bridge_dv:.0f}", flush=True)
    for src, dst, dv, td, tof in bridges_used:
        print(f"  {src} → {dst} bridge dv={dv:.0f}", flush=True)

    if len(full_perm) != kt.n:
        return {"status": "stitched_wrong_length",
                "got": len(full_perm), "want": kt.n}

    # Walk
    t0 = time.time()
    times, tofs, _, walk_ok, _, _ = walk_perm_chrono(
        kt, full_perm, tof_window=30.0, n_steps=200)
    print(f"Walked in {time.time()-t0:.0f}s", flush=True)
    if not walk_ok or not times:
        return {"status": "walk_failed"}

    x = times + tofs + [float(v) for v in full_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    mk = float(f[0])
    print(f"FINAL: mk={mk:.4f}, feas={feas}, fitness={list(f)}",
          flush=True)
    info = {"problem": problem, "n": kt.n, "mk": mk, "feasible": feas}
    if feas:
        p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
        print(f"BANKED: {p}", flush=True)
    return info


if __name__ == "__main__":
    its = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    print(json.dumps(main(intra_time_s=its), indent=2))
