"""E-674: Ch1 matching-II auction-repair LNS (user-approved build) — the cross-block coordinated move.

The flaw audit (E-673) proved matching-II is NOT solver-bound: leader 73714 sits 2.18% below the LP
bound 75360, and a free Lagrangian dual (exact auction subproblem) converges to that bound. The bank
72206 is optimal within every connected <=680 block (E-048) and swap-local (E-615); improving requires
a coordinated change SPANNING blocks — the move the tree never had (its only repair was a 3-D sub-MIP
that stalls on large regions, and restricted Gurobi capped at <=680 nodes).

This LNS supplies that move: DESTROY a large set of destinations (frees their e,l,d across many blocks),
REPAIR the freed sub-instance with a mini-Lagrangian whose subproblem is the EXACT 2-index auction
(scales to the whole instance, 4.7s) + D-repair primal. ACCEPT only if the re-optimized region strictly
beats the bank's value there (monotonic — never worse than the bank). Guard-bank any global improvement
(official feasibility). Usage: python ch1_auction_repair_lns.py [iters] [destroy_frac] [seed] [selfcheck]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from ch1_auction import auction_assignment
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
BANKJSON = f"{ROOT}/solutions/upload/matching-ii.json"
BANK = 72206.52; LEADER = 73714.03; LPUB = 75360.0


def load():
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    return e, l, d, w, int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)


def repair_region(idx, e, l, d, w, sub_iters=40):
    """Mini-Lagrangian (relax D) on a sub-instance = transfer indices `idx`. EXACT auction E-L
    subproblem + D-repair primal + subgradient on D-prices. Returns (best_selection_idx, best_value)."""
    if idx.size == 0:
        return np.array([], np.int64), 0.0
    se, sl, sd, sw = e[idx], l[idx], d[idx], w[idx]
    _, se = np.unique(se, return_inverse=True); _, sl = np.unique(sl, return_inverse=True)
    _, sdc = np.unique(sd, return_inverse=True)
    nse, nsl, nsd = int(se.max() + 1), int(sl.max() + 1), int(sdc.max() + 1)
    oe = np.argsort(se, kind="stable")
    se_s, sl_s, sd_s, sw_s, idx_s = se[oe], sl[oe], sdc[oe], sw[oe], idx[oe]
    seg = np.zeros(nse + 1, np.int64); seg[1:] = np.cumsum(np.bincount(se_s, minlength=nse))
    wdesc = np.argsort(-sw_s, kind="stable")
    mu = np.zeros(nsd); best_val = 0.0; best_sel = np.array([], np.int64)
    for it in range(sub_iters):
        r = sw_s - mu[sd_s]
        asg = auction_assignment(seg, sl_s, r, nse, nsl)
        good = (asg[np.minimum(se_s, nse - 1)] == sl_s) & (asg[np.minimum(se_s, nse - 1)] >= 0)
        cand = np.flatnonzero(good)
        if cand.size:
            br = np.full(nse, -1e18); np.maximum.at(br, se_s[cand], r[cand])
            cand = cand[r[cand] >= br[se_s[cand]] - 1e-12]
            up, fi = np.unique(se_s[cand], return_index=True); sel = cand[fi]
        else:
            sel = np.array([], np.int64)
        dusage = np.bincount(sd_s[sel], minlength=nsd)
        # primal: D-repair (best-w per d) + greedy fill
        if sel.size:
            ko = sel[np.argsort(-sw_s[sel], kind="stable")]
            ud = np.zeros(nsd, bool); kept = [i for i in ko if not ud[sd_s[i]] and (ud.__setitem__(sd_s[i], True) or True)]
            kept = np.array(kept, np.int64)
        else:
            kept = np.array([], np.int64)
        ue = np.zeros(nse, bool); ul = np.zeros(nsl, bool); ud = np.zeros(nsd, bool); tot = 0.0
        pick = []
        if kept.size:
            ue[se_s[kept]] = ul[sl_s[kept]] = ud[sd_s[kept]] = True; tot = float(sw_s[kept].sum())
            pick = list(kept)
        for i in wdesc:
            if not ue[se_s[i]] and not ul[sl_s[i]] and not ud[sd_s[i]]:
                ue[se_s[i]] = ul[sl_s[i]] = ud[sd_s[i]] = True; tot += sw_s[i]; pick.append(i)
        if tot > best_val:
            best_val = tot; best_sel = idx_s[np.array(pick, np.int64)]
        step = 2.0 / (1.0 + 0.2 * it)
        mu = np.maximum(0.0, mu + step * (dusage - 1.0))
    return best_sel, best_val


def main(iters=200, destroy_frac=0.35, seed=0, selfcheck=False):
    e, l, d, w, ne, nl, nd = load()
    x = np.asarray(json.load(open(BANKJSON))[0]["decisionVector"], dtype=np.int8)
    assert x.size == w.size
    sel0 = np.flatnonzero(x == 1)
    # feasibility of bank
    assert (np.unique(e[sel0]).size == sel0.size and np.unique(l[sel0]).size == sel0.size
            and np.unique(d[sel0]).size == sel0.size), "bank infeasible"
    cur_val = float(w[sel0].sum())
    log = lambda s: print(f"[E-674 s{seed}] {s}", flush=True)
    log(f"bank={cur_val:.2f} (official {BANK}) sel={sel0.size} | LP={LPUB} leader={LEADER} "
        f"destroy_frac={destroy_frac}")
    rng = np.random.default_rng(seed)
    cur = x.copy().astype(bool)
    # per-destination bank weight (0 if unused) → target LOW-weight (compromised) destinations
    dwt = np.zeros(nd); dwt[d[sel0]] = w[sel0]
    used_d = np.zeros(nd, bool); used_d[d[sel0]] = True
    # improvability score: low bank weight (or unused) destinations are most improvable
    improv = np.where(used_d, 1.0 / (dwt + 0.5), 2.0)   # unused d weighted high too
    probs = improv / improv.sum()
    t0 = time.time(); accepts = 0; best_global = cur_val
    nsub = max(1, int(destroy_frac * nd))
    for it in range(iters):
        # 70% contention-targeted (low-weight destinations) + 30% uniform for diversity
        if rng.random() < 0.7:
            D_sub = rng.choice(nd, size=nsub, replace=False, p=probs)
        else:
            D_sub = rng.choice(nd, size=nsub, replace=False)
        in_sub = np.zeros(nd, bool); in_sub[D_sub] = True
        # kept = selected transfers with d NOT in D_sub  → block their e,l
        kept_mask = cur & ~in_sub[d]
        ke, kl = e[kept_mask], l[kept_mask]
        blocked_e = np.zeros(ne, bool); blocked_e[ke] = True
        blocked_l = np.zeros(nl, bool); blocked_l[kl] = True
        # eligible repair transfers: d in D_sub, e & l not blocked by kept
        elig = in_sub[d] & ~blocked_e[e] & ~blocked_l[l]
        idx = np.flatnonzero(elig)
        old_region = float(w[cur & in_sub[d]].sum())     # bank's value on the destroyed destinations
        new_sel, new_val = repair_region(idx, e, l, d, w)
        if new_val > old_region + 1e-6:
            # accept: remove old d∈D_sub selections, add new_sel
            cur[cur & in_sub[d]] = False
            cur[new_sel] = True
            cur_val = cur_val - old_region + new_val
            accepts += 1
            if cur_val > best_global + 1e-6:
                best_global = cur_val
                # verify global feasibility before any bank claim
                ss = np.flatnonzero(cur)
                feas = (np.unique(e[ss]).size == ss.size and np.unique(l[ss]).size == ss.size
                        and np.unique(d[ss]).size == ss.size)
                log(f"NEW BEST {cur_val:.2f} (+{cur_val-BANK:.2f} vs bank) feas={feas} it={it} "
                    f"acc={accepts} [{time.time()-t0:.0f}s]")
                if not feas:
                    log("INFEASIBLE — abort"); return
                if cur_val > BANK + 1e-3:
                    json.dump({"selection": ss.tolist(), "value": cur_val},
                              open(f"/tmp/ch1_m2_auctionlns_s{seed}.json", "w"))
        if it % 20 == 0:
            log(f"it={it} |elig|={idx.size} old_reg={old_region:.0f} new_reg={new_val:.0f} "
                f"cur={cur_val:.2f} best={best_global:.2f} acc={accepts} [{time.time()-t0:.0f}s]")
        if selfcheck and it == 3:
            ss = np.flatnonzero(cur)
            assert np.unique(e[ss]).size == ss.size and np.unique(l[ss]).size == ss.size and \
                   np.unique(d[ss]).size == ss.size, "SELFCHECK: infeasible!"
            assert abs(cur_val - w[ss].sum()) < 1e-3, f"SELFCHECK: value drift {cur_val} vs {w[ss].sum()}"
            log(f"SELFCHECK OK (feasible, value consistent {cur_val:.2f})")
    log(f"DONE best={best_global:.2f} (+{best_global-BANK:.2f} vs bank) accepts={accepts} "
        f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    df = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    sc = len(sys.argv) > 4
    main(it, df, sd, sc)
