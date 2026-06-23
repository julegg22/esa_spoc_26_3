"""E-675: Ch1 matching-II LP-guided rounding (open lever after solver-bound refuted, E-673).

The LP relaxation (UB 75,360, 26.8% fractional) was solved as a BOUND but never USED as a primal guide.
The LP "knows" the good structure: ~73% of vars are integral at the optimum, and the fractional support
encodes the contested choices. LP-guided rounding (greedy by LP value / weight, respecting constraints)
often lands within a few % of the bound — a strong free primal our search (greedy/LNS/MIP-LNS) never
tried. Caches the LP solution to cache/ (survives reboot) for reuse by later levers (volume, metaheuristic).

Tests several rounding orders + a weight-greedy fill, reports best vs bank 72,206 / leader 73,714.
Usage: python ch1_lp_round.py
"""
import os, time
import numpy as np
import scipy.sparse as sp
import highspy
ROOT = "/home/julian/Projects/esa_spoc_26_3"
F = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"
LPCACHE = f"{ROOT}/cache/ch1_m2_lp_solution.npz"
BANK = 72206.52; LEADER = 73714.03; LPUB = 75360.0


def load():
    rows = np.loadtxt(F)
    e = rows[:, 0].astype(np.int64); l = rows[:, 1].astype(np.int64)
    d = rows[:, 2].astype(np.int64); w = rows[:, 3].astype(np.float64)
    _, e = np.unique(e, return_inverse=True); _, l = np.unique(l, return_inverse=True)
    _, d = np.unique(d, return_inverse=True)
    return e, l, d, w, int(e.max() + 1), int(l.max() + 1), int(d.max() + 1)


def solve_lp(e, l, d, w, ne, nl, nd):
    if os.path.exists(LPCACHE):
        z = np.load(LPCACHE); print(f"[E-675] LP solution loaded from cache (val={float(z['val']):.1f})", flush=True)
        return z["x"], float(z["val"])
    n = len(w)
    rows = np.concatenate([e, l + ne, d + ne + nl]); cols = np.tile(np.arange(n), 3)
    csr = sp.csr_matrix((np.ones(3 * n), (rows, cols)), shape=(ne + nl + nd, n))
    mod = highspy.HighsModel(); lp = mod.lp_
    lp.num_col_ = n; lp.num_row_ = ne + nl + nd; lp.sense_ = highspy.ObjSense.kMaximize
    lp.col_cost_ = w; lp.col_lower_ = np.zeros(n); lp.col_upper_ = np.ones(n)
    lp.row_lower_ = np.zeros(ne + nl + nd); lp.row_upper_ = np.ones(ne + nl + nd)
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = csr.indptr.astype(np.int32); lp.a_matrix_.index_ = csr.indices.astype(np.int32)
    lp.a_matrix_.value_ = csr.data
    h = highspy.Highs(); h.setOptionValue("output_flag", False); h.setOptionValue("threads", 2)
    h.setOptionValue("solver", "ipm")
    t0 = time.time(); h.passModel(mod); h.run()
    x = np.asarray(h.getSolution().col_value); val = float(w @ x)
    print(f"[E-675] LP solved val={val:.1f} [{time.time()-t0:.0f}s] frac={np.mean((x>1e-6)&(x<1-1e-6))*100:.1f}%", flush=True)
    os.makedirs(f"{ROOT}/cache", exist_ok=True)
    np.savez_compressed(LPCACHE, x=x, val=val)
    return x, val


def greedy(order, e, l, d, w, ne, nl, nd):
    ue = np.zeros(ne, bool); ul = np.zeros(nl, bool); ud = np.zeros(nd, bool); tot = 0.0; cnt = 0
    for i in order:
        if not ue[e[i]] and not ul[l[i]] and not ud[d[i]]:
            ue[e[i]] = ul[l[i]] = ud[d[i]] = True; tot += w[i]; cnt += 1
    return tot, cnt


def main():
    e, l, d, w, ne, nl, nd = load()
    x, lpval = solve_lp(e, l, d, w, ne, nl, nd)
    print(f"[E-675] matching-II | bank={BANK} leader={LEADER} LP={LPUB} (solved {lpval:.0f})", flush=True)
    # rounding orders
    orders = {
        "weight-only (baseline)":      np.argsort(-w, kind="stable"),
        "LP-value desc":               np.argsort(-x, kind="stable"),
        "LP-value then weight":        np.lexsort((-w, -x)),
        "x*w desc":                    np.argsort(-(x * w), kind="stable"),
        "weight among x>0.5":          np.argsort(-np.where(x > 0.5, w, -1), kind="stable"),
        "x desc then w (x>1e-6 first)": np.lexsort((-w, -(x > 1e-6).astype(float), -x)),
    }
    best = 0.0; bestname = ""
    for name, od in orders.items():
        tot, cnt = greedy(od, e, l, d, w, ne, nl, nd)
        flag = "  <<< BEATS BANK" if tot > BANK else ("  (>greedy)" if tot > 63400 else "")
        print(f"  {name:32s}: {tot:10.1f}  card={cnt}{flag}", flush=True)
        if tot > best:
            best = tot; bestname = name
    print(f"\n[E-675] BEST rounding = {best:.1f} ({bestname}) vs bank {BANK} ({best-BANK:+.1f}) / "
          f"leader {LEADER} ({best-LEADER:+.1f})", flush=True)


if __name__ == "__main__":
    main()
