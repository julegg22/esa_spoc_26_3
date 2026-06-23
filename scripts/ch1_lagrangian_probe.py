"""E-673: Ch1 matching-II Lagrangian-relaxation probe (Phase-4 audit experiment 1, user-approved).

Tests the FLAW in "solver-bound": the leader (73714) sits 2.18% BELOW the LP bound (75360), so the
leader is NOT at the integer optimum — they have a better PRIMAL found by better SEARCH, not a stronger
exact solver. The untried free paradigm = dual decomposition into a 2-index assignment.

This relaxes the DESTINATION constraints (prices mu_d). The subproblem keeps E-once and L-once hard
(a 2-index E-L assignment, here solved by a fast structure-aware greedy on reduced weights), and
subgradient updates mu_d toward D-feasibility. Each iteration extracts a feasible 3-matching primal
(D-repair + greedy fill). DECISIVE: does the price-guided primal climb toward/past the bank 72206
(vs the 1-D weight-greedy 63329) — i.e., does dual information reveal value the MIP/LNS paradigm missed?

Reports the primal trajectory. Cheap: O(n log n)/iter, ~92k edges, single core. Banks NOTHING (probe).
"""
import sys, time
import numpy as np
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
BANK = 72206.52; LEADER = 73714.03; LPUB = 75360.0; GREEDY1D = 63328.6


def greedy_fill(order, e, l, d, w, ne, nl, nd, pre_e=None, pre_l=None, pre_d=None):
    """Feasible 3-matching: walk transfers in `order`, take if e,l,d all free. pre_* mark pre-blocked."""
    ue = np.zeros(ne, bool); ul = np.zeros(nl, bool); ud = np.zeros(nd, bool)
    if pre_e is not None:
        ue[pre_e] = True; ul[pre_l] = True; ud[pre_d] = True
    sel = np.zeros(len(w), np.int8); tot = 0.0
    for i in order:
        if not ue[e[i]] and not ul[l[i]] and not ud[d[i]]:
            ue[e[i]] = ul[l[i]] = ud[d[i]] = True
            sel[i] = 1; tot += w[i]
    return sel, tot


def main(iters=120):
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    ne, nl, nd = e.max() + 1, l.max() + 1, d.max() + 1
    n = len(w)
    # group transfers by (e,l) pair → subproblem picks best-reduced transfer per pair
    el = e.astype(np.int64) * nl + l
    _, el_grp = np.unique(el, return_inverse=True)
    wdesc = np.argsort(-w, kind="stable")           # static weight order for the fill
    print(f"[E-673] matching-II  n={n} |E|={ne} |L|={nl} |D|={nd} | bank={BANK} leader={LEADER} "
          f"LP_UB={LPUB} greedy1D={GREEDY1D:.0f}", flush=True)
    # baseline: pure 1-D weight greedy (price-free), confirm ~63329
    _, g0 = greedy_fill(wdesc, e, l, d, w, ne, nl, nd)
    print(f"  [control] 1-D weight-greedy primal = {g0:.1f}  (expect ~63329)", flush=True)

    mu = np.zeros(nd)                               # destination prices (relaxed constraint)
    best = 0.0; t0 = time.time()
    for it in range(iters):
        r = w - mu[d]                               # reduced weight under current D-prices
        # subproblem: per (e,l) keep best-reduced transfer, then greedy 2-index E-L matching by r desc
        best_r = np.full(el_grp.max() + 1, -np.inf); best_i = np.full(el_grp.max() + 1, -1, np.int64)
        np.maximum.at(best_r, el_grp, r)
        # recover argmax transfer per group
        ordr = np.argsort(-r, kind="stable")
        seen = np.zeros(el_grp.max() + 1, bool)
        for i in ordr:
            g = el_grp[i]
            if not seen[g]:
                seen[g] = True; best_i[g] = i
        cand = best_i[(best_r > 0)]                 # candidate transfers (positive reduced), one per (e,l)
        cand = cand[cand >= 0]
        # greedy E-L matching on candidates by reduced weight desc
        cand = cand[np.argsort(-r[cand], kind="stable")]
        ue = np.zeros(ne, bool); ul = np.zeros(nl, bool)
        pick = []
        for i in cand:
            if not ue[e[i]] and not ul[l[i]]:
                ue[e[i]] = ul[l[i]] = True; pick.append(i)
        pick = np.array(pick, np.int64)
        # D-usage of the (E,L-feasible) subproblem selection → subgradient
        dusage = np.bincount(d[pick], minlength=nd)
        # ---- primal: repair D-conflicts (keep max-w per d), then greedy-fill from all transfers ----
        # keep, per used d, the highest-w transfer in pick
        primal_keep = []
        if len(pick):
            order_pick = pick[np.argsort(-w[pick], kind="stable")]
            ud = np.zeros(nd, bool)
            for i in order_pick:
                if not ud[d[i]]:
                    ud[d[i]] = True; primal_keep.append(i)
        primal_keep = np.array(primal_keep, np.int64)
        if len(primal_keep):
            sel, tot = greedy_fill(wdesc, e, l, d, w, ne, nl, nd,
                                   pre_e=e[primal_keep], pre_l=l[primal_keep], pre_d=d[primal_keep])
            tot += w[primal_keep].sum()
        else:
            tot = g0
        if tot > best:
            best = tot
        # ---- subgradient step on mu_d (diminishing): over-used d → raise price ----
        # NOTE: Polyak/large steps thrash (conflicts stuck ~2300); this diminishing schedule is the
        # one that monotonically reduced conflicts 2281->1508 and lifted the primal to 65.5k.
        step = 2.0 / (1.0 + 0.15 * it)
        mu = np.maximum(0.0, mu + step * (dusage - 1.0))
        if it % 10 == 0 or it == iters - 1:
            print(f"  it={it:3d} subproblem|pick|={len(pick)} D-overused={int((dusage>1).sum())} "
                  f"primal={tot:.1f} best={best:.1f} (vs bank {BANK}) [{time.time()-t0:.0f}s]", flush=True)
    verdict = ("BEATS BANK" if best > BANK else
               ("beats 1-D greedy, below bank" if best > g0 + 50 else "no structure gain"))
    print(f"\n[E-673] DONE best Lagrangian primal = {best:.1f}  vs 1-D greedy {g0:.0f} / bank {BANK} / "
          f"leader {LEADER} / LP {LPUB}  -> {verdict}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
