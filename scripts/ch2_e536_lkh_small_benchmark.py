"""E-536 — Ch2 small: LKH-3 benchmark via elkai.

Validates whether LKH-3 (Lin-Kernighan-Helsgaun) is competitive for our
problem at the small scale before committing to the large attack. If
LKH-3 on small produces a perm whose DP-polished makespan ≤ 110 d
(current external R3), the cluster-decomposition + LKH-3 approach for
large becomes high-confidence.

Pipeline:
  1. Build edge-cost matrix from the small ultrafine table:
     edge_cost[i, j] = min over t,tof of Lambert tof at (i, j, t, tof)
     such that dv ≤ DV_CHEAP.
     For pairs without cheap arc, use exc arc cost.
     Diagonal = 0; infeasible pairs = BIG.
  2. Apply the asymmetric → symmetric "Jonker-Volgenant" transform
     (double the n; each ATSP node → two-node block).
  3. Add a dummy node with 0-cost to/from all others (turns closed
     tour into open path).
  4. Solve via elkai.solve_int_matrix.
  5. Recover the resulting perm (drop dummy, undo JV trick).
  6. Evaluate via DP on ultrafine table (the same evaluator we trust
     for bank assessment).
  7. Compare DP-mk to current bank (116.37 d).

Compute: ~seconds for LKH-3, ~3 s for DP eval = ~10 s total.
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ch2_dp_numba import evaluate_perm_dp_numba

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
ULTRAFINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
RESULT = '/tmp/ch2_e536_result.json'

DV_CHEAP = 100.0


def build_cost_matrix_from_ultrafine(cheap_tab, exc_tab, t_starts) -> np.ndarray:
    """For each (i,j), cost = min over t of cheap_tof[i,j,t].
    Falls back to exc_tof if no cheap. Returns int matrix (centidays)."""
    n = cheap_tab.shape[0]
    cost = np.zeros((n, n), dtype=np.int64)
    BIG = 100000   # 1000 d penalty, much bigger than any real cost
    for i in range(n):
        for j in range(n):
            if i == j:
                cost[i, j] = 0; continue
            c_min = float(np.nanmin(cheap_tab[i, j]))
            if np.isfinite(c_min):
                cost[i, j] = int(round(c_min * 100))  # centidays
            else:
                e_min = float(np.nanmin(exc_tab[i, j]))
                if np.isfinite(e_min):
                    cost[i, j] = int(round(e_min * 100)) + 10000  # exc penalty
                else:
                    cost[i, j] = BIG
    return cost


def atsp_to_stsp_jv(cost: np.ndarray) -> np.ndarray:
    """Jonker-Volgenant asymmetric→symmetric transform.

    Each ATSP node i → two STSP nodes (2i, 2i+1).
    STSP edges:
      between blocks: stsp[2i+1, 2j]   = cost[i, j]  (others within block infeasible)
      within block:   stsp[2i, 2i+1]   = -L (force in-block edge used)
    Returns 2n × 2n int matrix.
    """
    n = cost.shape[0]
    BIG = 1000000   # 10 000 d penalty, no overflow risk
    L = 1000        # small magnitude penalty within block
    stsp = np.full((2*n, 2*n), BIG, dtype=np.int64)
    for i in range(n):
        for j in range(n):
            if i == j:
                stsp[2*i, 2*i+1] = -L  # force in-block edge
                stsp[2*i+1, 2*i] = -L
            else:
                stsp[2*i+1, 2*j] = int(cost[i, j])
                stsp[2*j, 2*i+1] = int(cost[i, j])  # symmetric copy
    return stsp


def add_dummy_for_open_path(matrix: np.ndarray) -> np.ndarray:
    """Add dummy node (id = N) with cost 0 to all, turning closed
    Hamilton tour into open Hamilton path."""
    N = matrix.shape[0]
    new = np.zeros((N + 1, N + 1), dtype=matrix.dtype)
    new[:N, :N] = matrix
    new[N, :] = 0; new[:, N] = 0; new[N, N] = 0
    return new


def recover_perm(lkh_tour: list, n: int, has_dummy: bool, has_jv: bool) -> list:
    """Convert LKH closed tour into our perm.

    lkh_tour is a closed tour over (2n + 1) nodes if jv+dummy, or (n+1)
    if dummy only. We:
      - Rotate so dummy is at end.
      - Drop dummy.
      - If JV: keep only the in-block start nodes (2*i), recovering n.
    """
    tour = list(lkh_tour)
    N = 2 * n + 1 if has_jv else n + 1
    if has_dummy:
        # Find dummy id (N-1)
        dummy_id = N - 1
        i_d = tour.index(dummy_id)
        tour = tour[i_d+1:] + tour[:i_d]  # drop dummy, keep order
    if has_jv:
        # Each ATSP node i is represented by 2i and 2i+1. The block
        # (2i, 2i+1) or (2i+1, 2i) means "visiting node i". The order
        # of i along the tour is what we want.
        perm = []
        seen = set()
        for v in tour:
            i_orig = v // 2
            if i_orig not in seen:
                seen.add(i_orig); perm.append(i_orig)
        return perm
    return tour


def main():
    # Load instance + ultrafine table
    print("Loading instance + ultrafine table...", flush=True)
    kt = KTTSP(INST); n = kt.n
    d = np.load(ULTRAFINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    print(f"  n={n} q={q}d T={T}", flush=True)

    # Build ATSP cost matrix
    print("Building ATSP cost matrix from ultrafine...", flush=True)
    t0 = time.time()
    cost = build_cost_matrix_from_ultrafine(cheap_tab, exc_tab, t_starts)
    print(f"  built in {time.time()-t0:.1f}s, "
          f"cheap-only finite count: "
          f"{int((cost < 10**8).sum() - n)}", flush=True)

    # Test direct STSP (assume symmetric) for speed comparison
    import elkai
    print("\nDirect elkai on raw ATSP (treated as STSP)...", flush=True)
    t0 = time.time()
    # Use larger of (i,j),(j,i) cost as symmetric proxy
    sym_cost = np.maximum(cost, cost.T)
    sym_with_dummy = add_dummy_for_open_path(sym_cost)
    tour_sym = elkai.solve_int_matrix(sym_with_dummy.tolist(), runs=10)
    print(f"  LKH wall: {time.time()-t0:.1f}s, tour_len={len(tour_sym)}",
          flush=True)
    perm_sym = recover_perm(tour_sym, n, has_dummy=True, has_jv=False)
    print(f"  Recovered perm len={len(perm_sym)} unique={len(set(perm_sym))}",
          flush=True)
    print(f"  perm[:5]={perm_sym[:5]} perm[-5:]={perm_sym[-5:]}",
          flush=True)

    # DP-evaluate the LKH perm
    print("\nDP-evaluating LKH perm...", flush=True)
    t0 = time.time()
    res = evaluate_perm_dp_numba(kt, perm_sym, cheap_tab, exc_tab, q, T)
    print(f"  DP wall: {time.time()-t0:.1f}s", flush=True)
    if res:
        print(f"  LKH-perm DP-mk = {res['mk']:.4f}d (vs bank 116.37d, "
              f"rank-3 ext 110.88d, rank-1 ext 101.65d)", flush=True)
    else:
        print(f"  LKH perm is DP-INFEASIBLE", flush=True)

    # Now try proper ATSP via Jonker-Volgenant
    print("\nNow ATSP via JV transform + dummy...", flush=True)
    t0 = time.time()
    stsp = atsp_to_stsp_jv(cost)
    stsp_d = add_dummy_for_open_path(stsp)
    tour_atsp = elkai.solve_int_matrix(stsp_d.tolist(), runs=10)
    print(f"  LKH wall: {time.time()-t0:.1f}s, tour_len={len(tour_atsp)}",
          flush=True)
    perm_atsp = recover_perm(tour_atsp, n, has_dummy=True, has_jv=True)
    print(f"  Recovered perm len={len(perm_atsp)} unique={len(set(perm_atsp))}",
          flush=True)
    print(f"  perm[:5]={perm_atsp[:5]} perm[-5:]={perm_atsp[-5:]}",
          flush=True)

    if len(set(perm_atsp)) == n:
        res_a = evaluate_perm_dp_numba(kt, perm_atsp, cheap_tab, exc_tab, q, T)
        if res_a:
            print(f"  ATSP-perm DP-mk = {res_a['mk']:.4f}d", flush=True)
        else:
            print(f"  ATSP perm is DP-INFEASIBLE", flush=True)

    Path(RESULT).write_text(json.dumps({
        'lkh_sym_mk': float(res['mk']) if res else None,
        'lkh_sym_perm': perm_sym,
        'lkh_atsp_mk': (float(res_a['mk']) if 'res_a' in dir()
                        and res_a else None),
        'bank_was': 116.37,
        'rank3_external': 110.88,
        'rank1_external': 101.65,
    }))
    print("\nResult saved.", flush=True)


if __name__ == '__main__':
    main()
