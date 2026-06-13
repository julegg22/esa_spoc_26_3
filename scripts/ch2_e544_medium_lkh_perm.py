"""E-544 — Ch2 medium: generate LKH-3 perm seed.

Mirrors E-536 (small LKH-3 benchmark) but for medium (n=181). Uses
the fine pair-set table from E-542 to build the LKH cost matrix.
Output: a LKH-3 perm seed that may be in a different basin than
bank's 228.97 d.
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP
from ch2_dp_numba import evaluate_perm_dp_numba

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
FINE = '/tmp/ch2_medium_fine_pair_set.npz'
RESULT = '/tmp/ch2_e544_lkh_perm.json'


def main():
    import elkai
    kt = KTTSP(INST); n = kt.n
    d = np.load(FINE)
    cheap = d['cheap']; exc = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    print(f"E-544 medium LKH-3 perm. n={n}, q={q}d T={T}", flush=True)

    # Build ATSP cost matrix from fine table
    # cost[i,j] = min over t of cheap_tof[i,j,t] (or exc_tof with penalty)
    BIG = 100000
    EXC_PEN = 10000
    cost = np.full((n, n), BIG, dtype=np.int64)
    for i in range(n):
        for j in range(n):
            if i == j:
                cost[i, j] = 0; continue
            c_min = float(np.nanmin(cheap[i, j]))
            if np.isfinite(c_min):
                cost[i, j] = int(round(c_min * 100))
            else:
                e_min = float(np.nanmin(exc[i, j]))
                if np.isfinite(e_min):
                    cost[i, j] = int(round(e_min * 100)) + EXC_PEN
    print(f"  cheap-only finite pairs: "
          f"{int((cost < 10**4).sum() - n)}", flush=True)

    # Solve with symmetric proxy (max of (i,j),(j,i))
    sym_cost = np.maximum(cost, cost.T)
    # Open path: add dummy node 0-cost to all
    n2 = n + 1
    sym_with_dummy = np.zeros((n2, n2), dtype=np.int64)
    sym_with_dummy[:n, :n] = sym_cost
    print(f"  Calling LKH-3 (runs=5)...", flush=True)
    t0 = time.time()
    tour = elkai.solve_int_matrix(sym_with_dummy.tolist(), runs=5)
    print(f"  LKH wall: {time.time()-t0:.1f}s", flush=True)
    print(f"  tour len: {len(tour)}", flush=True)

    # Remove dummy, get perm
    dummy_id = n
    i_d = tour.index(dummy_id)
    perm = tour[i_d+1:] + tour[:i_d]
    print(f"  perm len: {len(perm)} unique: {len(set(perm))}", flush=True)
    print(f"  start: {perm[0]}, end: {perm[-1]}", flush=True)

    # DP-evaluate
    print(f"  DP-evaluating LKH perm...", flush=True)
    t0 = time.time()
    res = evaluate_perm_dp_numba(kt, perm, cheap, exc, q, T)
    print(f"  DP wall: {time.time()-t0:.1f}s", flush=True)
    if res:
        print(f"  LKH-perm DP-mk = {res['mk']:.4f}d "
              f"(vs bank 228.97d, R3=216.95d, R1=199.74d)", flush=True)
    else:
        print(f"  LKH-perm DP-INFEASIBLE", flush=True)

    Path(RESULT).write_text(json.dumps({
        'lkh_perm': perm,
        'lkh_dp_mk': float(res['mk']) if res else None,
        'feasible': res is not None,
    }))


if __name__ == '__main__':
    main()
