"""Ch2 KTTSP large — precompute bridge feasibility tables.

For each node n in comp 2, and each small comp X ∈ {0, 1, 3},
precompute:
- bridges_to[n][X] = list of (dst_in_X, dv, td, tof) where (n→dst)
  feasible at dv_exc
- bridges_from[n][X] = list of (src_in_X, dv, td, tof) where
  (src→n) feasible at dv_exc

Stores result in /tmp/large_comp2_bridge_table.pkl
"""

from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_component_aware import find_components
from esa_spoc_26.ch2_kttsp import KTTSP


def _init_worker(inst):
    global _KT
    _KT = KTTSP(inst)


def _scan_node_to_smalls(args):
    """For (n_c2, list_of_(X, small_comp_nodes)), return all feasible
    bridges from n_c2 TO any node in each small comp."""
    n_c2, smalls = args
    kt = _KT
    result = {X: [] for X, _ in smalls}
    for X, nodes in smalls:
        for dst in nodes:
            best = None
            for td in np.linspace(0, kt.max_time * 0.9, 8):
                for tof in np.linspace(0.1, 30, 8):
                    if td + tof > kt.max_time:
                        continue
                    dv = kt.compute_transfer(n_c2, dst, float(td), float(tof))
                    if dv <= kt.dv_exc:
                        if best is None or dv < best[0]:
                            best = (dv, td, tof)
                        break
            if best is not None:
                result[X].append((int(dst), float(best[0]),
                                   float(best[1]), float(best[2])))
    return n_c2, result


def _scan_smalls_to_node(args):
    """For (n_c2, list_of_(X, small_comp_nodes)), return all feasible
    bridges FROM any node in each small comp TO n_c2."""
    n_c2, smalls = args
    kt = _KT
    result = {X: [] for X, _ in smalls}
    for X, nodes in smalls:
        for src in nodes:
            best = None
            for td in np.linspace(0, kt.max_time * 0.9, 8):
                for tof in np.linspace(0.1, 30, 8):
                    if td + tof > kt.max_time:
                        continue
                    dv = kt.compute_transfer(src, n_c2, float(td), float(tof))
                    if dv <= kt.dv_exc:
                        if best is None or dv < best[0]:
                            best = (dv, td, tof)
                        break
            if best is not None:
                result[X].append((int(src), float(best[0]),
                                   float(best[1]), float(best[2])))
    return n_c2, result


def main(problem="large", n_workers=8,
         out_path="/tmp/large_comp2_bridge_table.pkl"):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    g = pickle.load(open("/tmp/large_cheap_arc_graph_knn200.pkl", "rb"))
    comps = find_components(g["cheap_edges"], kt.n)
    comps = {int(k): v for k, v in comps.items()}
    comp2_nodes = comps[2]
    smalls = [(0, comps[0]), (1, comps[1]), (3, comps[3])]
    print(f"Building bridge table: {len(comp2_nodes)} comp 2 nodes × "
          f"3 small comps each × 2 directions", flush=True)

    import multiprocessing as mp
    args_list = [(int(n), smalls) for n in comp2_nodes]
    bridges_out = {}
    bridges_in = {}
    t0 = time.time()
    with mp.Pool(n_workers, initializer=_init_worker, initargs=(inst,)) as p:
        # First pass: comp 2 → small (outgoing)
        for k, (n_c2, result) in enumerate(p.imap_unordered(_scan_node_to_smalls,
                                                              args_list,
                                                              chunksize=10)):
            bridges_out[n_c2] = result
            if (k + 1) % 50 == 0:
                wall = time.time() - t0
                eta = (len(args_list) - k - 1) / (k + 1) * wall
                print(f"  out: {k+1}/{len(args_list)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
        print(f"Out scan done: {time.time()-t0:.0f}s", flush=True)
        # Second pass: small → comp 2 (incoming)
        t1 = time.time()
        for k, (n_c2, result) in enumerate(p.imap_unordered(_scan_smalls_to_node,
                                                              args_list,
                                                              chunksize=10)):
            bridges_in[n_c2] = result
            if (k + 1) % 50 == 0:
                wall = time.time() - t1
                eta = (len(args_list) - k - 1) / (k + 1) * wall
                print(f"  in: {k+1}/{len(args_list)}, "
                      f"wall={wall:.0f}s, ETA={eta:.0f}s", flush=True)
        print(f"In scan done: {time.time()-t1:.0f}s", flush=True)
    # Summary
    out_counts = [sum(len(v) for v in bridges_out[n].values())
                  for n in comp2_nodes]
    in_counts = [sum(len(v) for v in bridges_in[n].values())
                 for n in comp2_nodes]
    print(f"Out bridges per comp 2 node: min={min(out_counts)}, "
          f"mean={np.mean(out_counts):.1f}, max={max(out_counts)}",
          flush=True)
    print(f"In bridges per comp 2 node: min={min(in_counts)}, "
          f"mean={np.mean(in_counts):.1f}, max={max(in_counts)}",
          flush=True)
    n_with_out = sum(1 for c in out_counts if c > 0)
    n_with_in = sum(1 for c in in_counts if c > 0)
    print(f"Comp 2 nodes with ANY out-bridge: {n_with_out}/{len(comp2_nodes)}",
          flush=True)
    print(f"Comp 2 nodes with ANY in-bridge: {n_with_in}/{len(comp2_nodes)}",
          flush=True)
    pickle.dump({"bridges_out": bridges_out, "bridges_in": bridges_in},
                open(out_path, "wb"))
    print(f"Saved to {out_path}", flush=True)


if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_workers=nw)
