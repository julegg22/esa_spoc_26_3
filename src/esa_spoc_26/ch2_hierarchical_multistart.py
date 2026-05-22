"""Ch2 large hierarchical — multi-start meta-route from cached sub-tours.

v2 (single start cluster) reached 84/1051 nodes meta-routed feasibly
before exception budget saturated. With 50 clusters and 5 exc budget,
the meta-route's reach depends critically on WHICH cluster it starts
from — different starts admit different cheap-bridge chains.

This wrapper:
1. Builds sub-tours once (2 h) and caches them to disk.
2. On subsequent runs (--load-cache), skips the build.
3. Tries meta_route from EACH cluster as start, picks the longest
   feasible meta-route.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_hierarchical_large import (
    build_cluster_subtours, cluster_nodes, extract_features,
    meta_route,
)
from esa_spoc_26.ch2_kttsp import KTTSP


def main(problem="large", k_clusters=50, cache_path=None,
         load_cache=False):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    print(f"Multi-start hierarchical: n={kt.n}, k={k_clusters}",
          flush=True)
    if cache_path is None:
        cache_path = f"/tmp/large_subtours_k{k_clusters}.pkl"

    if load_cache and Path(cache_path).exists():
        with open(cache_path, "rb") as f:
            subtours = pickle.load(f)
        print(f"Loaded {len(subtours)} sub-tours from {cache_path}",
              flush=True)
    else:
        # Build sub-tours
        t0 = time.time()
        feats = extract_features(kt)
        labels = cluster_nodes(feats, k_clusters)
        subtours = build_cluster_subtours(
            kt, labels, k_clusters, max_starts=4, n_time_scans=8,
            max_exc_internal=1)
        print(f"Built {len(subtours)} sub-tours in "
              f"{time.time()-t0:.0f}s; caching to {cache_path}",
              flush=True)
        with open(cache_path, "wb") as f:
            pickle.dump(subtours, f)

    # Try meta_route from each cluster as start
    cluster_ids = sorted(subtours.keys())
    print(f"\nTrying meta_route from each of {len(cluster_ids)} clusters",
          flush=True)
    best_result = None  # (n_perm, start_k, perm, times, tofs)
    for start_k in cluster_ids:
        # Rebuild subtours dict with start_k first
        reordered = {start_k: subtours[start_k]}
        for k in cluster_ids:
            if k != start_k:
                reordered[k] = subtours[k]
        result = meta_route(kt, reordered)
        if result is None:
            continue
        full_perm, full_times, full_tofs = result
        n_perm = len(full_perm)
        if best_result is None or n_perm > best_result[0]:
            print(f"  start={start_k}: perm={n_perm}/{kt.n}", flush=True)
            best_result = (n_perm, start_k, full_perm, full_times,
                            full_tofs)

    if best_result is None:
        print("ALL starts failed meta_route", flush=True)
        return {"status": "all_fail"}
    n_perm, start_k, full_perm, full_times, full_tofs = best_result
    print(f"\nBEST: start={start_k}, perm={n_perm}/{kt.n}",
          flush=True)
    # Check if feasible-full
    if n_perm == kt.n:
        x = full_times + full_tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        print(f"FULL: mk={f[0]:.4f}, feas={feas}, fitness={list(f)}",
              flush=True)
        if feas:
            p = Path(f"/home/julian/Projects/esa_spoc_26_3/solutions/upload/{problem}.json")
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": 2}]))
            print(f"BANKED: {p}", flush=True)
            return {"status": "banked", "mk": float(f[0])}
    return {"status": "best_partial",
            "best_n": n_perm, "best_start": start_k}


if __name__ == "__main__":
    kc = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    load = bool(int(sys.argv[2])) if len(sys.argv) > 2 else False
    print(json.dumps(main(k_clusters=kc, load_cache=load), indent=2))
