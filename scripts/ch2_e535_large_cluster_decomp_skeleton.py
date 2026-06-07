"""E-535 — Ch2 large: cluster-decomposition pipeline skeleton.

Per O-015, large has 4 cheap-edge components [601, 150, 150, 150] with
the 3 small components nearly complete (in/out deg ≈ 149/150) and
comp0 (601 nodes) sparser. This is the structural sweet spot for
cluster-decomposition + per-cluster TSP solver (the TGMA strategy
inferred from O-014).

Architecture:
  1. Load cheap-edge adjacency from E-533 output (/tmp/ch2_e533_large_adj.npz).
  2. For each of 4 components, build the intra-component cheap-graph
     and compute an open Hamilton path (LKH-3 via solver wrapper, or
     greedy fallback).
  3. Enumerate inter-component bridge candidates: K-1 = 3 inter-comp
     transitions for a contiguous 4-comp tour.
  4. For each candidate (endpoint choice per comp + comp ordering +
     bridge node selection), assemble the full perm and walk_perm_chrono.
  5. SLSQP polish (times, tofs) on each assembly that's Lambert-feasible.
  6. Pick the best polished mk.

This SKELETON file establishes the pipeline structure and provides
TODO stubs for the heavy lifting (LKH-3 integration, bridge enumeration).
NOT EXECUTED yet — meant as preparation for when we attack large.

Dependencies (TODO):
  - LKH-3 binary (https://akira.ruc.dk/~keld/research/LKH-3/) — needs install
  - Or: install elkai (Python wrapper for LKH-3)
  - Or: pure-Python ATSP solver for small sub-problems
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/hard.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/large.json"
ADJ_FILE = '/tmp/ch2_e533_large_adj.npz'

DV_CHEAP = 100.0
DV_EXC = 600.0


def load_structure(adj_file: str):
    """Load E-533 output: cheap_adj, exc_adj, labels, out_deg, in_deg."""
    d = np.load(adj_file)
    return {
        'cheap': d['cheap'], 'exc': d['exc'],
        'labels': d['labels'],
        'out_deg': d['out_deg'], 'in_deg': d['in_deg'],
    }


def get_components(labels) -> List[List[int]]:
    """Return list of node-id lists, one per component."""
    n_comps = int(labels.max()) + 1
    comps = [[] for _ in range(n_comps)]
    for i, c in enumerate(labels):
        comps[int(c)].append(i)
    # Sort by size desc
    comps.sort(key=len, reverse=True)
    return comps


def intra_cheap_cost(struct, comp: List[int], edge_metric='min_tof') -> np.ndarray:
    """Build cost matrix for intra-comp Hamilton path solver.

    edge_metric ∈ {'min_tof', 'binary', 'lambert_min_dv'}.
    'binary' uses 1 for cheap-feasible, INF otherwise.
    'min_tof' would need the ultrafine table on these pairs (TODO).
    'lambert_min_dv' requires Lambert calls (slow).
    """
    n = len(comp)
    cost = np.full((n, n), 1e9, dtype=np.float64)
    cheap = struct['cheap']
    for ii, i in enumerate(comp):
        for jj, j in enumerate(comp):
            if i == j:
                cost[ii, jj] = 0.0
                continue
            if cheap[i, j]:
                cost[ii, jj] = 1.0  # binary; refine later
    return cost


def solve_open_hamilton_path(cost: np.ndarray, start: int, end: int,
                               time_limit_s: int = 60) -> Optional[List[int]]:
    """Solve OPEN Hamilton path from start to end on a dense cost matrix.

    TODO options:
      1. elkai (LKH-3 wrapper): pip install elkai; works for ATSP up to
         ~3000 nodes in minutes.
      2. OR-Tools routing solver with fixed start/end depots.
      3. Greedy nearest-neighbor fallback for time-constrained debug.

    Returns the path as a list of node indices (into the comp's local
    indexing), or None if infeasible.
    """
    # ── greedy fallback (will be replaced with LKH-3) ──
    n = cost.shape[0]
    unvisited = set(range(n)) - {start}
    path = [start]
    cur = start
    while unvisited:
        # Nearest cheap neighbor
        nbrs = [(cost[cur, v], v) for v in unvisited if cost[cur, v] < 1e8]
        if not nbrs:
            return None
        nbrs.sort()
        nxt = nbrs[0][1]
        path.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    if path[-1] != end:
        # Greedy didn't land on the requested end; try 2-opt to fix
        # TODO: proper open-Hamilton-path with fixed endpoints
        return None
    return path


def candidate_bridges(struct, comp_a: List[int], comp_b: List[int],
                       top_k: int = 5) -> List[Tuple[int, int]]:
    """Pick top-K (a_out, b_in) pairs as candidate inter-comp bridges.

    Ranked by out_deg(a) + in_deg(b) for diversity.
    """
    out_deg = struct['out_deg']
    in_deg = struct['in_deg']
    pairs = []
    for a in comp_a:
        for b in comp_b:
            score = int(out_deg[a]) + int(in_deg[b])
            pairs.append((a, b, score))
    pairs.sort(key=lambda x: -x[2])
    return [(p[0], p[1]) for p in pairs[:top_k]]


def assemble_tour(comps: List[List[int]], ordering: List[int],
                  paths: List[List[int]], bridges: List[Tuple[int, int]]
                  ) -> List[int]:
    """Stitch per-comp paths with inter-comp bridges into full tour."""
    out: List[int] = []
    for idx, c_idx in enumerate(ordering):
        out.extend(paths[c_idx])
        if idx < len(bridges):
            # Bridge is implicit in the assembly (last node of this comp,
            # first node of next comp); no extra append needed.
            pass
    return out


def main():
    if not Path(ADJ_FILE).exists():
        print(f"ERR adjacency missing: {ADJ_FILE} (run E-533 first)",
              file=sys.stderr)
        return

    print("Loading large structure from E-533...", flush=True)
    struct = load_structure(ADJ_FILE)
    comps = get_components(struct['labels'])
    print(f"Components: {len(comps)}, sizes={[len(c) for c in comps]}",
          flush=True)
    # Expected: [601, 150, 150, 150]

    kt = KTTSP(INST)
    print(f"Large UDP: n={kt.n}, n_exc={kt.n_exc}, max_time={kt.max_time}d",
          flush=True)

    # ── Phase 1: per-comp Hamilton path (TODO: LKH-3 integration) ──
    print("\nPhase 1: per-comp Hamilton path skeleton (greedy fallback)",
          flush=True)
    for i, comp in enumerate(comps):
        cost = intra_cheap_cost(struct, comp)
        # Greedy fallback with arbitrary start/end
        path = solve_open_hamilton_path(cost, start=0, end=len(comp)-1,
                                          time_limit_s=10)
        print(f"  comp{i} (size {len(comp)}): path found = {path is not None}",
              flush=True)

    # ── Phase 2: bridge candidate enumeration ──
    print("\nPhase 2: bridge candidates between adjacent comps (top-5 each)",
          flush=True)
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            bridges = candidate_bridges(struct, comps[i], comps[j], top_k=5)
            print(f"  comp{i}→comp{j}: top-5 = {bridges[:3]}...", flush=True)

    # ── Phase 3: full pipeline (TODO) ──
    print("\nPhase 3: full pipeline NOT IMPLEMENTED in skeleton.",
          flush=True)
    print("  Steps:", flush=True)
    print("    a) Install LKH-3 binary or `pip install elkai`", flush=True)
    print("    b) Replace solve_open_hamilton_path() greedy with LKH-3 call",
          flush=True)
    print("    c) Enumerate comp orderings (4! = 24 if all distinct)",
          flush=True)
    print("    d) Per ordering × per (start, end) per comp: assemble + "
          "walk_perm_chrono check", flush=True)
    print("    e) SLSQP polish each Lambert-feasible candidate", flush=True)
    print("    f) Bank if any beats current rank-3 large (1238.52 d)",
          flush=True)


if __name__ == '__main__':
    main()
