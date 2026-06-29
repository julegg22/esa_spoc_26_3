"""E-673b: Ch1 matching-II Lagrangian with EXACT 2-index subproblem (auction) — the decisive probe.

Relax the DESTINATION constraints (prices mu_d). Subproblem = EXACT max-weight (E,L) assignment under
reduced weights r_i = w_i - mu_{d_i}, solved by the validated sparse auction (exact vs scipy, 4.7s at
scale). Subgradient on mu toward D-feasibility. Each iter: (i) DUAL bound = mu.sum() + auction_value
(valid UB on the optimum, since the subproblem is now exact) — track the MIN; (ii) PRIMAL = D-repair the
E-L-optimal selection + greedy fill — track the MAX. DECISIVE: does the exact-subproblem Lagrangian
primal CROSS the bank 72206 / approach leader 73714, and does the dual bound fall from LP 75360 toward
the leader (proving the integer gap is small and the gap is primal-search, not solver-bound)?

Banks NOTHING (probe). Usage: python ch1_lagrangian_auction.py [iters=60]
"""
import sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from ch1_auction import auction_assignment
ROOT = "/home/julian/Projects/esa_spoc_26_3"
_DIR = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics"
# E-756 exp#3: same machinery on matching-i (dual-guided primal repair = a DIFFERENT primal generator
# than local search). matching-i targets measured in E-756 (LP=34120.53 IPM).
_INST = {"ii": (f"{_DIR}/matching-ii.txt", 72206.52, 73714.03, 75360.0, 63328.6),
         "i":  (f"{_DIR}/matching-i.txt", 33490.458, 33555.0, 34120.53, 0.0)}


def main(iters=60, inst="ii"):
    F, BANK, LEADER, LPUB, GREEDY1D = _INST[inst]
    print(f"[E-673b/E-756] instance matching-{inst}", flush=True)
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    ne, nl, nd = int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)
    n = len(w)
    # edges sorted by person e (CSR) for the auction
    oe = np.argsort(e, kind="stable")
    e_s, l_s, d_s, w_s = e[oe], l[oe], d[oe], w[oe]
    seg = np.zeros(ne + 1, np.int64); seg[1:] = np.cumsum(np.bincount(e_s, minlength=ne))
    edge_person = e_s                                  # person per edge (sorted)
    wdesc = np.argsort(-w_s, kind="stable")            # static weight order for primal fill
    print(f"[E-673b] matching-II n={n} |E|={ne}|L|={nl}|D|={nd} | bank={BANK} leader={LEADER} "
          f"LP={LPUB} | EXACT-auction subproblem", flush=True)

    def primal_from_selection(sel_idx):
        """sel_idx: edge indices (in sorted arrays) of the E-L-optimal selection. D-repair + greedy fill."""
        if sel_idx.size:
            keep_order = sel_idx[np.argsort(-w_s[sel_idx], kind="stable")]
            ud = np.zeros(nd, bool); kept = []
            for i in keep_order:
                if not ud[d_s[i]]:
                    ud[d_s[i]] = True; kept.append(i)
            kept = np.array(kept, np.int64)
        else:
            kept = np.array([], np.int64)
        ue = np.zeros(ne, bool); ul = np.zeros(nl, bool); ud = np.zeros(nd, bool)
        tot = 0.0
        if kept.size:
            ue[e_s[kept]] = ul[l_s[kept]] = ud[d_s[kept]] = True; tot = float(w_s[kept].sum())
        for i in wdesc:                                 # greedy fill remaining free
            if not ue[e_s[i]] and not ul[l_s[i]] and not ud[d_s[i]]:
                ue[e_s[i]] = ul[l_s[i]] = ud[d_s[i]] = True; tot += w_s[i]
        return tot

    mu = np.zeros(nd); best_primal = 0.0; best_dual = 1e18; t0 = time.time()
    for it in range(iters):
        r = w_s - mu[d_s]                               # reduced weight per edge (sorted)
        assigned = auction_assignment(seg, l_s, r, ne, nl)   # exact E-L matching, object per person
        # recover selected edges: per matched person, the edge to its assigned object with max r
        matched = assigned >= 0
        good = matched[edge_person] & (l_s == assigned[np.minimum(edge_person, ne - 1)])
        cand = np.flatnonzero(good)
        # one edge per person (max r) among its edges to the assigned object
        rr = r[cand]
        bestr = np.full(ne, -1e18); np.maximum.at(bestr, edge_person[cand], rr)
        keepmask = rr >= bestr[edge_person[cand]] - 1e-12
        cand = cand[keepmask]
        up, fi = np.unique(edge_person[cand], return_index=True)
        sel = cand[fi]                                  # one selected edge per matched person
        auction_val = float(r[sel].sum())
        dual = float(mu.sum()) + auction_val            # valid UB
        if dual < best_dual:
            best_dual = dual
        dusage = np.bincount(d_s[sel], minlength=nd)
        primal = primal_from_selection(sel)
        if primal > best_primal:
            best_primal = primal
        step = 2.0 / (1.0 + 0.15 * it)
        mu = np.maximum(0.0, mu + step * (dusage - 1.0))
        if it % 5 == 0 or it == iters - 1:
            print(f"  it={it:3d} |sel|={sel.size} D-over={int((dusage>1).sum())} dual={dual:.0f} "
                  f"best_dual={best_dual:.0f} primal={primal:.1f} best={best_primal:.1f} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-673b] DONE best_primal={best_primal:.1f} best_dual(UB)={best_dual:.1f} | "
          f"greedy1D={GREEDY1D:.0f} bank={BANK} leader={LEADER} LP={LPUB}", flush=True)
    print(f"  PRIMAL vs bank: {best_primal-BANK:+.1f}  ({'BEATS BANK' if best_primal>BANK else 'below bank'})"
          f"  | vs leader: {best_primal-LEADER:+.1f}", flush=True)
    print(f"  DUAL UB {best_dual:.0f} vs LP {LPUB:.0f}: {'tighter' if best_dual<LPUB-1 else 'not tighter'}"
          f" | leader is {'BELOW' if LEADER<best_dual else 'ABOVE'} this UB", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60,
         sys.argv[2] if len(sys.argv) > 2 else "ii")
