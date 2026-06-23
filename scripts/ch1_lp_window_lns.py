"""E-677: Ch1 matching-II LP-targeted SMALL-WINDOW exact LNS — the tractable RINS×LNS synthesis.

RINS on the full ~22k disagreement stalls (E-676); E-048's exact-LNS on connected <=680 blocks was null.
This combines the working parts: SMALL destination-windows (free transfers <= ~700 → HiGHS solves to
OPTIMALITY fast ⇒ result GUARANTEED >= bank on the window) targeted by LP DISAGREEMENT (seed windows on
destinations where the bank's selected transfer has LOW LP value = where the bank compromised, the spots
E-048's connected-block destroy never specifically hit). Destination windows span blocks (the cross-block
move E-615 said was missing). Accept strictly-improving region re-opts; guard-bank global improvements.
Usage: python ch1_lp_window_lns.py [iters=4000] [win_dest=80] [seed=0]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_matching import _solve_sub
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
BANKJSON = f"{ROOT}/solutions/upload/matching-ii.json"
LPCACHE = f"{ROOT}/cache/ch1_m2_lp_solution.npz"
BANK = 72206.52; LEADER = 73714.03


def load():
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    return e, l, d, w, int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)


def main(iters=4000, win_dest=80, seed=0):
    e, l, d, w, ne, nl, nd = load()
    bank = np.asarray(json.load(open(BANKJSON))[0]["decisionVector"], dtype=np.int8)
    xlp = np.load(LPCACHE)["x"]
    cur = (bank == 1)
    sel0 = np.flatnonzero(cur); cur_val = float(w[sel0].sum())
    assert np.unique(e[sel0]).size == sel0.size and np.unique(l[sel0]).size == sel0.size and \
           np.unique(d[sel0]).size == sel0.size, "bank infeasible"
    log = lambda s: print(f"[E-677 s{seed} w{win_dest}] {s}", flush=True)
    # per-destination LP value of the bank's selected transfer (low = compromised → target)
    dwt_lp = np.full(nd, 2.0)                          # unused d → neutral-high
    seld = d[sel0]; dwt_lp[seld] = xlp[sel0]
    improv = 1.0 / (dwt_lp + 0.1)                      # low LP → high target prob
    probs = improv / improv.sum()
    rng = np.random.default_rng(seed)
    log(f"bank={cur_val:.2f} sel={sel0.size} | leader={LEADER} | window={win_dest} dests, exact HiGHS repair")
    t0 = time.time(); accepts = 0; best = cur_val; solves = 0
    for it in range(iters):
        D_sub = rng.choice(nd, size=win_dest, replace=False, p=probs)
        in_sub = np.zeros(nd, bool); in_sub[D_sub] = True
        kept = cur & ~in_sub[d]
        be = np.zeros(ne, bool); be[e[kept]] = True
        bl = np.zeros(nl, bool); bl[l[kept]] = True
        elig = in_sub[d] & ~be[e] & ~bl[l]
        idx = np.flatnonzero(elig)
        if idx.size == 0:
            continue
        old_region = float(w[cur & in_sub[d]].sum())
        sub = _solve_sub(e[idx], l[idx], d[idx], w[idx], time_limit=8.0, threads=1)
        solves += 1
        new_idx = idx[sub == 1]
        new_region = float(w[new_idx].sum())
        if new_region > old_region + 1e-7:
            cur[cur & in_sub[d]] = False
            cur[new_idx] = True
            cur_val = cur_val - old_region + new_region
            accepts += 1
            if cur_val > best + 1e-6:
                best = cur_val
                ss = np.flatnonzero(cur)
                feas = (np.unique(e[ss]).size == ss.size and np.unique(l[ss]).size == ss.size
                        and np.unique(d[ss]).size == ss.size)
                tag = " *** BEATS LEADER" if cur_val > LEADER else ""
                log(f"NEW BEST {cur_val:.2f} (+{cur_val-BANK:.2f} vs bank) feas={feas} it={it} acc={accepts}{tag} [{time.time()-t0:.0f}s]")
                if not feas:
                    log("INFEASIBLE — abort"); return
                x_out = np.zeros(len(w), np.int8); x_out[ss] = 1
                json.dump({"decisionVector": x_out.tolist(), "problem": "matching-ii",
                           "challenge": "spoc-4-luna-tomato-logistics"},
                          open(f"{ROOT}/cache/ch1_m2_lpwin_best.json", "w"))
        if it % 200 == 0 and it > 0:
            log(f"it={it} solves={solves} cur={cur_val:.2f} best={best:.2f} acc={accepts} [{time.time()-t0:.0f}s]")
    log(f"DONE best={best:.2f} (+{best-BANK:.2f} vs bank) accepts={accepts} solves={solves} [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    wd = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    main(it, wd, sd)
