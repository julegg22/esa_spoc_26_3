"""E-678: polish the LP-ROUNDED solution (different basin) with random-transfer-destroy exact LNS.

Bank 72,206 is robust to every exact-repair neighborhood from the BANK start (E-048/615/677). But the
LP-rounded solution (69,503, E-675) lives in a DIFFERENT basin (bank & LP disagree on most selections).
Does proper LNS (random transfer destroy + exact HiGHS repair) launched from the LP basin climb ABOVE
the bank? If yes → the LP-guided start escapes the bank's basin = a free win. Usage: python ... [iters] [seed]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_matching import _solve_sub
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
LPCACHE = f"{ROOT}/cache/ch1_m2_lp_solution.npz"
BANK = 73253.48; LEADER = 73714.03
START = "lp"
DMODE = "random"
KICK_AFTER = 400


def load():
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    return e, l, d, w, int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)


def greedy_sel(order, e, l, d, w, ne, nl, nd):
    ue = np.zeros(ne, bool); ul = np.zeros(nl, bool); ud = np.zeros(nd, bool); sel = []
    for i in order:
        if not ue[e[i]] and not ul[l[i]] and not ud[d[i]]:
            ue[e[i]] = ul[l[i]] = ud[d[i]] = True; sel.append(i)
    return np.array(sel, np.int64)


def main(iters=600, seed=0, drop=0.25):
    e, l, d, w, ne, nl, nd = load()
    if START == "bank":                              # continue climbing from the current banked best
        bx = np.asarray(json.load(open(f"{ROOT}/solutions/upload/matching-ii.json"))[0]["decisionVector"], np.int8)
        start = np.flatnonzero(bx == 1); src = "current-bank"
    else:                                            # LP-rounded start (x*w desc greedy, ~69,503)
        xlp = np.load(LPCACHE)["x"]
        start = greedy_sel(np.argsort(-(xlp * w), kind="stable"), e, l, d, w, ne, nl, nd); src = "LP-rounded"
    cur = np.zeros(len(w), bool); cur[start] = True
    cur_val = float(w[start].sum())
    log = lambda s: print(f"[E-678 s{seed}] {s}", flush=True)
    log(f"{src} start={cur_val:.2f} sel={start.size} | bank={BANK} leader={LEADER} | random-destroy {drop}")
    rng = np.random.default_rng(seed)
    t0 = time.time(); best = cur_val; accepts = 0
    best_x = cur.copy(); last_improve = 0
    def wfill():                                       # greedy weight-desc fill of free nodes into cur
        ue = np.zeros(ne, bool); ul = np.zeros(nl, bool); ud = np.zeros(nd, bool)
        ss = np.flatnonzero(cur); ue[e[ss]] = ul[l[ss]] = ud[d[ss]] = True
        for i in np.argsort(-w, kind="stable"):
            if not cur[i] and not ue[e[i]] and not ul[l[i]] and not ud[d[i]]:
                cur[i] = True; ue[e[i]] = ul[l[i]] = ud[d[i]] = True
    for it in range(iters):
        # ILS kick: when stuck (no new best for KICK_AFTER), perturb cur to escape the plateau
        if it - last_improve > KICK_AFTER:
            cur[:] = best_x                            # restart from best, then kick
            sel = np.flatnonzero(cur)
            cur[rng.choice(sel, size=int(0.6 * sel.size), replace=False)] = False
            wfill()                                    # greedy re-fill (a different, worse config)
            cur_val = float(w[np.flatnonzero(cur)].sum()); last_improve = it
        sel = np.flatnonzero(cur)
        if sel.size < 2:                              # guard: recover if selection collapsed
            cur[:] = False; cur[start] = True; sel = np.flatnonzero(cur)
        drop_n = min(max(1, int(drop * sel.size)), sel.size - 1)
        if DMODE == "worst":                          # bias destroy toward low-weight selections
            sw = sel[np.argsort(w[sel], kind="stable")]   # ascending weight
            nw = drop_n // 2
            rest = sw[nw:]
            rnd = rng.choice(rest, size=min(drop_n - nw, rest.size), replace=False) if rest.size else np.array([], int)
            dropped = np.concatenate([sw[:nw], rnd])
        else:
            dropped = rng.choice(sel, size=drop_n, replace=False)
        cur[dropped] = False
        kept = np.flatnonzero(cur)
        be = np.zeros(ne, bool); be[e[kept]] = True
        bl = np.zeros(nl, bool); bl[l[kept]] = True
        bd = np.zeros(nd, bool); bd[d[kept]] = True
        free = (~cur) & ~be[e] & ~bl[l] & ~bd[d]
        idx = np.flatnonzero(free)
        sub = _solve_sub(e[idx], l[idx], d[idx], w[idx], time_limit=10.0, threads=1)
        cur[idx[sub == 1]] = True
        cur_val = float(w[np.flatnonzero(cur)].sum())
        if cur_val > best + 1e-6:
            best = cur_val; best_x = cur.copy(); last_improve = it
            tag = " *** BEATS BANK" if cur_val > BANK else ""
            if cur_val > BANK:
                ss = np.flatnonzero(cur)
                feas = (np.unique(e[ss]).size == ss.size and np.unique(l[ss]).size == ss.size
                        and np.unique(d[ss]).size == ss.size)
                tag += f" feas={feas}"
                if feas:
                    x_out = np.zeros(len(w), np.int8); x_out[ss] = 1
                    json.dump({"decisionVector": x_out.tolist(), "problem": "matching-ii",
                               "challenge": "spoc-4-luna-tomato-logistics"},
                              open(f"{ROOT}/cache/ch1_m2_lpbasin_best_s{seed}.json", "w"))
            log(f"best={best:.2f} (+{best-BANK:.2f} vs bank) it={it} acc={accepts}{tag} [{time.time()-t0:.0f}s]")
        accepts += 1
        if it % 100 == 0 and it > 0:
            log(f"it={it} cur={cur_val:.2f} best={best:.2f} [{time.time()-t0:.0f}s]")
    log(f"DONE best={best:.2f} (+{best-BANK:.2f} vs bank) [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    START = sys.argv[3] if len(sys.argv) > 3 else "lp"   # 'lp' (LP-rounded) | 'bank' (current best)
    drop = float(sys.argv[4]) if len(sys.argv) > 4 else 0.25
    DMODE = sys.argv[5] if len(sys.argv) > 5 else "random"
    KICK_AFTER = int(sys.argv[6]) if len(sys.argv) > 6 else 400
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 600, int(sys.argv[2]) if len(sys.argv) > 2 else 0, drop)
