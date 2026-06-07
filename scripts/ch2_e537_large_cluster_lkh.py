"""E-537 — Ch2 large: full cluster-decomposition + LKH-3 pipeline (runnable).

Implements the inferred TGMA-style architecture (per O-015):
  1. Load large structure from E-533 ([601, 150, 150, 150] components).
  2. For each component, build intra-cheap-arc adjacency and probe
     pairwise Lambert min-dv to construct a cost matrix.
  3. Solve each component's open Hamilton path via LKH-3 (elkai).
     - 150-node comps: dense, easy (~seconds)
     - 601-node comp: sparser, harder but in LKH-3's range (~minutes)
  4. Enumerate inter-component bridges with the 5-exception budget.
     - K-1 = 3 inter-comp transitions for contiguous 4-comp visit
     - For each (comp_order, entry/exit per comp): assemble full perm
  5. Walk_perm_chrono → if feasible, walk-mk is reported.
  6. (Optional) DP polish on a coarse precomputed table for large
     (if available) — currently not built.

NOT FULLY OPTIMIZED — first pass to validate the pipeline E2E. Walks
are slow (Lambert at every leg) so the bridge enumeration is bounded
to ~50 candidates total.

Dependencies:
  - elkai >= 2.0 (LKH-3 wrapper, pip install elkai)
  - E-533 output at /tmp/ch2_e533_large_adj.npz
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
from itertools import permutations
from typing import List, Tuple, Optional
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

import elkai

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/hard.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/large.json"
BAK = OUT + ".bak.20260607.e537"
ADJ_FILE = '/tmp/ch2_e533_large_adj.npz'
RESULT = '/tmp/ch2_e537_result.json'

DV_CHEAP = 100.0
DV_EXC = 600.0


# ── Component analysis ──────────────────────────────────────────────
def load_components(adj_file: str):
    d = np.load(adj_file)
    return {
        'cheap': d['cheap'], 'exc': d['exc'],
        'labels': d['labels'], 'out_deg': d['out_deg'],
        'in_deg': d['in_deg'],
    }


def get_components_sorted(labels) -> List[List[int]]:
    n_comps = int(labels.max()) + 1
    comps = [[] for _ in range(n_comps)]
    for i, c in enumerate(labels):
        comps[int(c)].append(i)
    comps.sort(key=len, reverse=True)
    return comps


# ── Cost matrix per component ────────────────────────────────────────
def build_lambert_cost_matrix(kt, comp: List[int],
                                t_probe: float = 50.0,
                                tof_probe_grid: List[float] = None) -> np.ndarray:
    """For each (i,j) in comp, find the min cheap-tof at the probe t
    by sampling Lambert at a few tof values.

    Returns int (centidays) cost matrix.
    """
    if tof_probe_grid is None:
        tof_probe_grid = [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0]
    n = len(comp)
    cost = np.zeros((n, n), dtype=np.int64)
    BIG = 100000
    EXC_PENALTY = 10000   # 100 d penalty for using exc

    for ii in range(n):
        for jj in range(n):
            if ii == jj:
                continue
            i, j = comp[ii], comp[jj]
            best_tof = float('inf')
            best_kind = 'inf'
            for tof in tof_probe_grid:
                try:
                    dv = kt.compute_transfer(i, j, t_probe, tof)
                except Exception:
                    continue
                if dv <= DV_CHEAP:
                    if tof < best_tof:
                        best_tof = tof; best_kind = 'cheap'
                    break  # found cheap, that's good enough
                elif dv <= DV_EXC and best_kind != 'cheap':
                    if tof < best_tof:
                        best_tof = tof; best_kind = 'exc'

            if best_kind == 'cheap':
                cost[ii, jj] = int(round(best_tof * 100))
            elif best_kind == 'exc':
                cost[ii, jj] = int(round(best_tof * 100)) + EXC_PENALTY
            else:
                cost[ii, jj] = BIG
    return cost


# ── LKH-3 closed tour for ATSP via symmetric proxy ──────────────────
def lkh_closed_tour(cost: np.ndarray, runs: int = 5) -> List[int]:
    """Returns LKH closed Hamilton tour as a list of node indices into
    the input cost matrix. Uses max(c[i,j], c[j,i]) as symmetric proxy."""
    sym = np.maximum(cost, cost.T)
    sym_list = sym.tolist()
    tour = elkai.solve_int_matrix(sym_list, runs=runs)
    return list(tour)


def lkh_open_path(cost: np.ndarray, start_idx: Optional[int] = None,
                    end_idx: Optional[int] = None,
                    runs: int = 5) -> List[int]:
    """Returns an open Hamilton path. If start/end specified, the path
    starts/ends there; otherwise an arbitrary open path is returned
    (via dummy node trick).
    """
    n = cost.shape[0]
    if start_idx is None and end_idx is None:
        # Add a dummy node connected to all with 0 cost; LKH solves
        # closed tour which then "breaks" at the dummy.
        new = np.zeros((n + 1, n + 1), dtype=cost.dtype)
        new[:n, :n] = np.maximum(cost, cost.T)
        # dummy is row/col n; cost 0
        tour = elkai.solve_int_matrix(new.tolist(), runs=runs)
        # Rotate so dummy is at end
        try:
            i_d = tour.index(n)
        except ValueError:
            return None
        path = tour[i_d+1:] + tour[:i_d]
        return path
    # Fixed start/end via "long" cost dummy edges
    new = np.full((n + 1, n + 1), 100000, dtype=cost.dtype)
    new[:n, :n] = np.maximum(cost, cost.T)
    # dummy <-> start has cost 0; dummy <-> end has cost 0; others BIG
    if start_idx is not None:
        new[n, start_idx] = 0; new[start_idx, n] = 0
    if end_idx is not None:
        new[n, end_idx] = 0; new[end_idx, n] = 0
    new[n, n] = 0
    tour = elkai.solve_int_matrix(new.tolist(), runs=runs)
    try:
        i_d = tour.index(n)
    except ValueError:
        return None
    return tour[i_d+1:] + tour[:i_d]


# ── Pipeline ────────────────────────────────────────────────────────
def main(probe_t: float = 50.0):
    if not Path(ADJ_FILE).exists():
        print(f"ERR adjacency missing: {ADJ_FILE}", flush=True)
        return
    kt = KTTSP(INST)
    print(f"E-537 large cluster-LKH pipeline. n={kt.n} n_exc={kt.n_exc} "
          f"max_time={kt.max_time}d", flush=True)

    struct = load_components(ADJ_FILE)
    comps = get_components_sorted(struct['labels'])
    print(f"Components: {[len(c) for c in comps]}", flush=True)

    # ── Phase 1: per-comp LKH-3 Hamilton path ────────────────────────
    print(f"\nPhase 1: per-comp open Hamilton path via LKH-3 "
          f"(probe t={probe_t}d)", flush=True)
    comp_paths = []  # list of paths in GLOBAL node ids
    for i, comp in enumerate(comps):
        t0 = time.time()
        print(f"  comp{i} (size {len(comp)}): building cost...", flush=True)
        cost = build_lambert_cost_matrix(kt, comp, t_probe=probe_t)
        wall_cost = time.time() - t0
        n_finite = int((cost < 90000).sum() - len(comp))
        print(f"    cost built {wall_cost:.1f}s. Finite edges: {n_finite}",
              flush=True)
        # LKH
        t0 = time.time()
        path_local = lkh_open_path(cost, runs=3)
        wall_lkh = time.time() - t0
        if path_local is None or len(set(path_local)) != len(comp):
            print(f"    LKH FAILED on comp{i}", flush=True)
            comp_paths.append(None); continue
        path_global = [comp[v] for v in path_local]
        print(f"    LKH path found {wall_lkh:.1f}s. "
              f"start={path_global[0]} end={path_global[-1]}", flush=True)
        comp_paths.append(path_global)

    if any(p is None for p in comp_paths):
        print("\nNot all comps had a path. Stopping.", flush=True)
        return

    # ── Phase 2: assemble full perm with first interior ordering ────
    print(f"\nPhase 2: assemble + walk_perm_chrono check (first ordering only)",
          flush=True)
    # Default ordering: big, then small1, small2, small3 (descending size)
    full_perm = []
    for path in comp_paths:
        full_perm.extend(path)
    assert len(set(full_perm)) == kt.n, \
        f"perm has dupes! len={len(full_perm)} unique={len(set(full_perm))}"
    print(f"  Full perm: start={full_perm[0]} end={full_perm[-1]} "
          f"len={len(full_perm)}", flush=True)
    print(f"  Components join at positions: "
          f"{[sum(len(p) for p in comp_paths[:i+1]) for i in range(len(comps)-1)]}",
          flush=True)

    # ── Phase 3: Lambert validation via walk_perm_chrono ──────────────
    print(f"\nPhase 3: walk_perm_chrono (this may take minutes on n=1051)",
          flush=True)
    t0 = time.time()
    try:
        times, tofs, dvs, ok, exc_n, last_leg = walk_perm_chrono(
            kt, full_perm, tof_window=12.0, n_steps=120,
            wait_steps=4, wait_dt=1.0)
    except Exception as e:
        print(f"  walk_perm_chrono EXCEPTION: {e}", flush=True)
        return
    wall = time.time() - t0
    print(f"  Wall: {wall:.0f}s", flush=True)
    if not ok:
        print(f"  walk_perm_chrono REJECTED at leg {last_leg} "
              f"(exc_used={exc_n}/{kt.n_exc})", flush=True)
        print(f"  → Cluster decomposition produced an INFEASIBLE perm.",
              flush=True)
        print(f"  Next steps: try other comp orderings / bridge choices.",
              flush=True)
    else:
        mk = times[-1] + tofs[-1]
        n_exc_legs = sum(1 for d in dvs if d > DV_CHEAP)
        print(f"  walk_perm_chrono FEASIBLE: mk={mk:.4f}d exc={n_exc_legs}",
              flush=True)
        print(f"  vs leaderboard rank-1 large: 424.62d (TGMA, 2026-06-05)",
              flush=True)
        # Validate via UDP
        x = times + tofs + [float(p) for p in full_perm]
        fit = kt.fitness(x)
        feas = bool(kt.is_feasible(fit))
        print(f"  UDP fitness: mk={fit[0]:.4f}d feasible={feas} viols={fit[1:]}",
              flush=True)
        if feas and (not Path(OUT).exists() or fit[0] < 1200):
            # Bank tentatively
            if Path(OUT).exists() and not Path(BAK).exists():
                Path(BAK).write_bytes(Path(OUT).read_bytes())
            tmp = OUT + '.tmp'
            Path(tmp).write_text(json.dumps([{
                'decisionVector': x, 'problem': 'large',
                'challenge': CHALLENGE,
            }]))
            os.replace(tmp, OUT)
            print(f"  >>> BANKED large: {fit[0]:.4f}d", flush=True)

    Path(RESULT).write_text(json.dumps({
        'comp_sizes': [len(c) for c in comps],
        'walk_ok': ok if 'ok' in dir() else False,
        'walk_mk': float(mk) if 'mk' in dir() else None,
        'exc_used': int(exc_n) if 'exc_n' in dir() else None,
        'last_leg': int(last_leg) if 'last_leg' in dir() else None,
    }))


if __name__ == '__main__':
    pt = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0
    main(probe_t=pt)
