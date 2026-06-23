"""Sparse max-weight bipartite assignment via the forward (Jacobi) auction with epsilon-scaling.
Persons = E-nodes, objects = L-nodes, edges = (person, object, benefit). Each person assigned to <=1
object and vice-versa; a person may stay UNASSIGNED (the null object, value 0) if no positive net
benefit. Returns assigned object per person (-1 = unassigned).

Used as the exact 2-index subproblem inside the Ch1 matching-II Lagrangian (E-673b).
"""
import numpy as np


def auction_assignment(seg_start, obj, ben, n_persons, n_objects, eps0=None, max_rounds=100000):
    """Edges grouped by person in CSR form: person p owns edges [seg_start[p]:seg_start[p+1]].
    obj[edge] = object id, ben[edge] = benefit. Maximize total benefit, each person/object used <=1,
    persons may stay unassigned (null object value 0). Vectorized Jacobi auction + epsilon-scaling.
    Returns assigned[person] (object id or -1). Near-optimal: gap <= n_assigned * eps_min."""
    seg_start = np.ascontiguousarray(seg_start, np.int64)
    lengths = np.diff(seg_start)
    has_edge = lengths > 0
    edge_person = np.repeat(np.arange(n_persons, dtype=np.int64), lengths)
    starts = seg_start[:-1].copy()
    starts[~has_edge] = np.minimum(starts[~has_edge], max(len(obj) - 1, 0))  # safe reduceat index
    assigned = np.full(n_persons, -1, np.int64)
    owner = np.full(n_objects, -1, np.int64)
    price = np.zeros(n_objects, np.float64)
    bmax = float(ben.max()) if ben.size else 1.0
    # small starting eps avoids price overshoot (large eps0 leaves objects permanently overpriced
    # since forward-auction prices only rise); validated exact at eps0≈bmax*1e-3 on dense LAPs.
    eps = (bmax * 1e-3) if eps0 is None else eps0
    eps_min = max(1e-9, bmax * 1e-5)                  # tight → near-exact
    NEG = -1e18
    while True:
        optout = np.zeros(n_persons, bool)
        rounds = 0
        while rounds < max_rounds:
            rounds += 1
            active = (assigned < 0) & ~optout
            if not active.any():
                break
            net = ben - price[obj]                                  # all edges
            best = np.maximum.reduceat(net, starts)                 # per-person max (garbage if empty)
            best[~has_edge] = NEG
            best_per_edge = best[edge_person]
            is_best = net >= best_per_edge - 1e-15
            cand = np.flatnonzero(is_best)
            up, fi = np.unique(edge_person[cand], return_index=True)  # persons with edges, first best edge
            argbest = np.zeros(n_persons, np.int64)                 # safe dummy 0 for empty persons
            argbest[up] = cand[fi]
            net2 = net.copy(); net2[argbest[has_edge]] = NEG
            second = np.maximum(np.maximum.reduceat(net2, starts), 0.0)  # incl null=0
            best_obj = obj[argbest]                                 # dummy for empty (masked out below)
            bid_amt = price[best_obj] + (best - second) + eps
            # who bids: active with edges and best>=0; active with best<0 → optout
            wants = active & has_edge & (best >= 0.0)
            optout |= active & (~has_edge | (best < 0.0))
            bidders = np.flatnonzero(wants)
            if bidders.size == 0:
                break
            bo = best_obj[bidders]; ba = bid_amt[bidders]
            # winner per object = highest bid
            order = np.argsort(-ba, kind="stable")
            bidders_s, bo_s, ba_s = bidders[order], bo[order], ba[order]
            _, wfi = np.unique(bo_s, return_index=True)
            win_p = bidders_s[wfi]; win_o = bo_s[wfi]; win_amt = ba_s[wfi]
            prev = owner[win_o]
            disp = prev[prev >= 0]
            assigned[disp] = -1
            owner[win_o] = win_p; assigned[win_p] = win_o; price[win_o] = win_amt
        if eps <= eps_min:
            break
        eps = max(eps / 4.0, eps_min)
    return assigned


def _test():
    # Tiny 1: 2 persons, 2 objects, identity is optimal
    # edges: p0-o0=5, p0-o1=1, p1-o0=1, p1-o1=5  → optimal {p0:o0,p1:o1}=10
    seg = np.array([0, 2, 4]); obj = np.array([0, 1, 0, 1]); ben = np.array([5., 1, 1, 5.])
    a = auction_assignment(seg, obj, ben, 2, 2)
    val = sum(ben[seg[p] + np.flatnonzero(obj[seg[p]:seg[p+1]] == a[p])[0]] for p in range(2) if a[p] >= 0)
    print(f"test1 assigned={a.tolist()} value={val} (opt=10)", "OK" if val == 10 else "FAIL")
    # Tiny 2: greedy-trap — p0 prefers o0(9) but p1 ONLY connects o0(8); greedy takes p0-o0 then p1 stuck=9
    #   optimal: p0-o1(7)+p1-o0(8)=15 > greedy 9. edges p0-o0=9,p0-o1=7, p1-o0=8
    seg = np.array([0, 2, 3]); obj = np.array([0, 1, 0]); ben = np.array([9., 7, 8.])
    a = auction_assignment(seg, obj, ben, 2, 2)
    val = 0.0
    for p in range(2):
        if a[p] >= 0:
            ei = seg[p] + np.flatnonzero(obj[seg[p]:seg[p+1]] == a[p])[0]
            val += ben[ei]
    print(f"test2 assigned={a.tolist()} value={val} (opt=15, greedy-trap=9)", "OK" if abs(val-15) < 1e-6 else "FAIL")
    # Random vs scipy dense linear_sum_assignment (small, full)
    from scipy.optimize import linear_sum_assignment
    rng = np.random.default_rng(0)
    for trial in range(5):
        n = 30
        M = rng.random((n, n))
        ri, ci = linear_sum_assignment(M, maximize=True)
        opt = M[ri, ci].sum()
        # to CSR edges (all dense)
        seg = np.arange(0, n * n + 1, n)
        obj = np.tile(np.arange(n), n)
        ben = M.reshape(-1).copy()
        a = auction_assignment(seg, obj, ben, n, n)
        val = sum(M[p, a[p]] for p in range(n) if a[p] >= 0)
        print(f"test3.{trial} auction={val:.4f} scipy_opt={opt:.4f} diff={opt-val:.4f}",
              "OK" if abs(opt - val) < 1e-3 else "FAIL")


if __name__ == "__main__":
    _test()
