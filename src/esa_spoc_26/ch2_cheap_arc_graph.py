"""Ch2 KTTSP — Perspective 1: precompute the static "cheap-arc" graph.

For each ordered pair (i, j), test whether there EXISTS some (td, tof)
with Δv(i, j, td, tof) ≤ kt.dv_thr. If yes, (i, j) is a cheap arc in
the static graph G_cheap. Time-respecting greedy IGNORES this graph
(it commits to a single t at each step); a Hamilton path FINDER on
G_cheap explores the full space.

For Ch2 large (n=1051): 1051 × 1050 = 1.1 M ordered pairs. With 8
(td, tof) samples per pair = 8.8 M Lambert evals. At ~1 ms each
(pykep + overhead), single-thread = 2.4 h. With 8 workers = 18 min.

Pruning: many node-pairs are obviously expensive (very different a,
e, i, Ω). Pre-filter by orbital-element distance: keep only the
K_NN nearest neighbours per node. For K_NN = 100, sample only
105 K pairs.

Output: edge list (i, j) with cheap arc + min Δv found across the
sampled (td, tof) grid. Saved as pickle for downstream use.

Downstream: classical Hamilton path heuristics (Christofides / LKH /
OR-tools VRP) on this graph; then lift back to time-respecting via
constraint-satisfaction.
"""

from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_kttsp import KTTSP


_KT = [None]
_GRID = [None]


def _init_worker(inst, td_grid, tof_grid):
    _KT[0] = KTTSP(inst)
    _GRID[0] = (td_grid, tof_grid)


def _scan_pair(args):
    """Return (i, j, min_dv, best_td, best_tof) — None if no
    (td, tof) achieves Δv ≤ dv_thr."""
    i, j = args
    kt = _KT[0]
    td_grid, tof_grid = _GRID[0]
    min_dv = float("inf")
    best_td = None
    best_tof = None
    for td in td_grid:
        for tof in tof_grid:
            if td + tof > kt.max_time:
                continue
            dv = kt.compute_transfer(i, j, float(td), float(tof))
            if dv < min_dv:
                min_dv = dv
                best_td = float(td)
                best_tof = float(tof)
            if dv <= kt.dv_thr:
                return (i, j, dv, float(td), float(tof), True)
    cheap = min_dv <= kt.dv_thr
    return (i, j, min_dv, best_td, best_tof, cheap)


def k_nearest_neighbors(kt, k):
    """Return adjacency dict {i: [j1, j2, ..., jk]} of orbital-element
    nearest neighbours using (a_norm, sin(i)cos(Ω), sin(i)sin(Ω))."""
    n = kt.n
    feats = np.zeros((n, 3))
    for i in range(n):
        a, e, inc, raan, w, M = kt.tom[i].orbital_elements
        feats[i] = [a, np.sin(inc) * np.cos(raan), np.sin(inc) * np.sin(raan)]
    # Normalise
    for c in range(feats.shape[1]):
        col = feats[:, c]
        if col.max() - col.min() > 1e-9:
            feats[:, c] = (col - col.min()) / (col.max() - col.min())
    # Pairwise distances (vectorised)
    from scipy.spatial.distance import cdist
    D = cdist(feats, feats, metric="euclidean")
    adj = {}
    for i in range(n):
        order = np.argsort(D[i])
        adj[i] = [int(j) for j in order[1:k + 1]]  # skip self
    return adj


def main(problem="large", k_nn=80, n_td=4, n_tof=4, n_workers=8,
         cache_path=None):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    print(f"Cheap-arc graph: n={kt.n}, k_nn={k_nn}, "
          f"td_grid={n_td}, tof_grid={n_tof}", flush=True)

    # k-NN adjacency (orbital-element proximity)
    t0 = time.time()
    adj_nn = k_nearest_neighbors(kt, k_nn)
    print(f"k-NN: {time.time()-t0:.1f}s", flush=True)
    # Build pair list (ordered, since transfers are directional)
    pairs = []
    for i in range(kt.n):
        for j in adj_nn[i]:
            pairs.append((i, j))
    print(f"Candidate pairs (k_nn × n): {len(pairs)}", flush=True)

    # Sample grid
    td_grid = np.linspace(0, kt.max_time * 0.95, n_td)
    tof_grid = np.linspace(max(kt.min_tof, 0.05), 30.0, n_tof)
    print(f"td: {td_grid}", flush=True)
    print(f"tof: {tof_grid}", flush=True)

    # Parallel scan
    t0 = time.time()
    import multiprocessing as mp
    cheap_edges = {}
    min_dv_edges = {}
    with mp.Pool(n_workers, initializer=_init_worker,
                 initargs=(inst, td_grid, tof_grid)) as pool:
        for k, result in enumerate(pool.imap_unordered(_scan_pair, pairs,
                                                         chunksize=200)):
            i, j, dv, td, tof, cheap = result
            min_dv_edges[(i, j)] = (dv, td, tof)
            if cheap:
                cheap_edges[(i, j)] = (dv, td, tof)
            if (k + 1) % 50000 == 0:
                wall = time.time() - t0
                rate = (k + 1) / wall
                eta = (len(pairs) - k - 1) / rate
                print(f"  scanned {k+1}/{len(pairs)}, "
                      f"cheap_edges={len(cheap_edges)}, "
                      f"rate={rate:.0f}/s, ETA={eta:.0f}s", flush=True)
    wall = time.time() - t0
    print(f"\nScan done in {wall:.0f}s "
          f"({len(cheap_edges)} cheap of {len(pairs)} candidates)",
          flush=True)

    # Density statistics
    out_degree = {i: 0 for i in range(kt.n)}
    in_degree = {i: 0 for i in range(kt.n)}
    for (i, j) in cheap_edges:
        out_degree[i] += 1
        in_degree[j] += 1
    out_deg_arr = np.array(list(out_degree.values()))
    in_deg_arr = np.array(list(in_degree.values()))
    print(f"Out-degree: min={out_deg_arr.min()}, "
          f"mean={out_deg_arr.mean():.1f}, max={out_deg_arr.max()}",
          flush=True)
    print(f"In-degree: min={in_deg_arr.min()}, "
          f"mean={in_deg_arr.mean():.1f}, max={in_deg_arr.max()}",
          flush=True)
    n_isolated_out = (out_deg_arr == 0).sum()
    n_isolated_in = (in_deg_arr == 0).sum()
    print(f"Isolated nodes (out=0): {n_isolated_out}, "
          f"(in=0): {n_isolated_in}", flush=True)

    # Save
    if cache_path is None:
        cache_path = f"/tmp/large_cheap_arc_graph_knn{k_nn}.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump({
            "n": kt.n,
            "cheap_edges": cheap_edges,
            "min_dv_edges": min_dv_edges,
            "adj_nn": adj_nn,
            "td_grid": td_grid.tolist(),
            "tof_grid": tof_grid.tolist(),
        }, f)
    print(f"Saved to {cache_path}", flush=True)
    return {
        "n_pairs_scanned": len(pairs),
        "n_cheap_edges": len(cheap_edges),
        "out_deg_mean": float(out_deg_arr.mean()),
        "in_deg_mean": float(in_deg_arr.mean()),
        "n_isolated_out": int(n_isolated_out),
        "n_isolated_in": int(n_isolated_in),
        "wall_s": wall,
        "cache": cache_path,
    }


if __name__ == "__main__":
    knn = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    n_td = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    n_tof = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    nw = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    print(json.dumps(main(k_nn=knn, n_td=n_td, n_tof=n_tof,
                          n_workers=nw), indent=2))
