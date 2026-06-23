"""E-676: Ch1 matching-II RINS (Relaxation-Induced Neighborhood Search) — strongest LP-based lever.

After solver-bound REFUTED (E-673) + LP-rounding reaching 69,503 (E-675, +6.2k over greedy but <bank),
RINS fixes the vars where the cached LP optimum and the bank AGREE (both ~selected or both ~unselected),
then solves the DISAGREEMENT region EXACTLY (HiGHS sub-MIP). The bank's selection is feasible in that
sub-problem ⇒ result is GUARANTEED >= bank, and the LP-disagreement neighborhood is a smarter, larger,
LP-informed region than the random/connected destroys the tree used (E-048/E-615). A move that can span
blocks. If the disagreement MIP is too big to solve, tighten thresholds (fix more).

Sweeps agreement thresholds; guard-banks any feasible improvement over 72,206 (never submit).
Usage: python ch1_rins.py [time_limit_s=120]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_matching import _solve_sub
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
BANKJSON = f"{ROOT}/solutions/upload/matching-ii.json"
LPCACHE = f"{ROOT}/cache/ch1_m2_lp_solution.npz"
BANK = 72206.52; LEADER = 73714.03; LPUB = 75360.0


def load():
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    return e, l, d, w, int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)


def feasible(e, l, d, sel):
    return (np.unique(e[sel]).size == sel.size and np.unique(l[sel]).size == sel.size
            and np.unique(d[sel]).size == sel.size)


def main(tl=120):
    e, l, d, w, ne, nl, nd = load()
    bank = np.asarray(json.load(open(BANKJSON))[0]["decisionVector"], dtype=np.int8)
    z = np.load(LPCACHE); xlp = z["x"]
    bsel = np.flatnonzero(bank == 1); bval = float(w[bsel].sum())
    assert feasible(e, l, d, bsel), "bank infeasible"
    print(f"[E-676] bank={bval:.2f} sel={bsel.size} | LP={float(z['val']):.0f} | leader={LEADER}", flush=True)

    best = bval
    for hi, lo in [(0.9, 0.1), (0.7, 0.05), (0.5, 0.02), (0.99, 0.2)]:
        t0 = time.time()
        fix1 = (bank == 1) & (xlp > hi)                 # confident selected
        fix0 = (bank == 0) & (xlp < lo)                 # confident unselected
        free = ~fix1 & ~fix0
        # free transfers blocked by a fix1 node can't be chosen → drop them
        f1 = np.flatnonzero(fix1)
        be = np.zeros(ne, bool); be[e[f1]] = True
        bl = np.zeros(nl, bool); bl[l[f1]] = True
        bd = np.zeros(nd, bool); bd[d[f1]] = True
        free &= ~be[e] & ~bl[l] & ~bd[d]
        fidx = np.flatnonzero(free)
        nfree = fidx.size
        # solve disagreement region exactly (HiGHS); bank's free part is feasible → opt >= it
        sub = _solve_sub(e[fidx], l[fidx], d[fidx], w[fidx], time_limit=tl, threads=2)
        new_sel = np.concatenate([f1, fidx[sub == 1]])
        feas = feasible(e, l, d, new_sel)
        val = float(w[new_sel].sum()) if feas else -1
        print(f"  fix1>{hi} fix0<{lo}: |fix1|={f1.size} |free|={nfree} -> val={val:.2f} "
              f"feas={feas} ({val-bval:+.2f} vs bank) [{time.time()-t0:.0f}s]", flush=True)
        if feas and val > best + 1e-3:
            best = val
            # round-trip official-style feasibility already checked; write candidate
            x_out = np.zeros(len(w), np.int8); x_out[new_sel] = 1
            json.dump({"decisionVector": x_out.tolist(), "problem": "matching-ii",
                       "challenge": "spoc-4-luna-tomato-logistics"},
                      open(f"{ROOT}/cache/ch1_m2_rins_best.json", "w"))
            tag = " *** BEATS LEADER" if val > LEADER else ""
            print(f"    NEW BEST {val:.2f} (+{val-BANK:.2f} vs bank){tag} → cached", flush=True)
    print(f"\n[E-676] DONE best={best:.2f} vs bank {BANK} ({best-BANK:+.2f}) / leader {LEADER} "
          f"({best-LEADER:+.2f})", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
