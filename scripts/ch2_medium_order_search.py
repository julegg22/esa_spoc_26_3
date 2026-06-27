"""E-731 — Ch2-MEDIUM order search to RECLAIM RANK-1 (target <186.27; bank 189.10 is a frozen-order artifact).

Faithful beam-retimer over the full-edge window table (cache/ch2_medium_windows.npz, no 0.025 tof floor) with the
<=5 exception budget, wrapped in or-opt/LNS over the visit ORDER (the frozen variable per E-731). Every accepted
candidate is FINAL-gated by the official kt.fitness. Positive control first: retime the bank order, confirm it is
~189.10 (the retimer must track the official DP, else the proxy is untrustworthy).
Usage: python ch2_medium_order_search.py [iters=200000] [K=6] [W=40] [maxwait=8]"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/medium.kttsp")
kt = KTTSP(INST); OPAR = kt.opar.astype(np.float64)
THR = kt.dv_thr; EXC_THR = kt.dv_exc; NEXC = kt.n_exc; MAXREV = kt.max_revs
NEXC_PROXY = NEXC + 2                                           # relaxed proxy budget (grid rounding over-counts);
#                                                                official kt.fitness still enforces the real NEXC=5
MINTOF = max(kt.min_tof, 0.01); MAXT = kt.max_time; DAY = 86400.0; N = kt.n
print(f"[E-731] medium n={N} dv_thr={THR} exc_thr={EXC_THR} n_exc={NEXC}; lazy fine-scan evaluator", flush=True)


def cheap_arr(i, j, t, maxwait):
    """earliest cheap arrival on i->j departing in [t, t+maxwait] (lookup), else None."""
    w = WIN.get((i, j))
    if w is None:
        return None
    deps, tofs = w
    q = np.searchsorted(deps, t)
    if q < len(deps) and deps[q] <= t + maxwait:
        return float(deps[q] + tofs[q])
    return None


# ---- EXACT forward DP scheduler (E-568) over the coarse 0.5d window grid (reproduces the bank's optimum) -------
from numba import njit
# LAZY FINE evaluator: scan each edge's cheap/exception windows on demand at fine resolution (catches narrow
# windows the coarse precompute misses), cached. Avoids a multi-hour full precompute.
TQ = 0.05; HORIZON = 250.0                                      # any sub-189d tour fits in 250d; halves scan+DP cost
T = int(round(HORIZON / TQ)); INF_INT = 10 ** 9
_DEPS = np.arange(0.0, HORIZON, TQ); _DEPS_SEC = _DEPS * DAY
print(f"[E-731] lazy fine evaluator TQ={TQ}d horizon={HORIZON}d T={T}", flush=True)
_EDGE = {}


def _build_idx(et):
    arr = np.full(T, INF_INT, dtype=np.int32)
    m = et > 0
    if m.any():
        di = np.round(_DEPS[m] / TQ).astype(np.int64)
        ai = np.round((_DEPS[m] + et[m] / DAY) / TQ).astype(np.int64)
        ok = (ai < T) & (ai > di) & (di >= 0)
        np.minimum.at(arr, di[ok], ai[ok])                     # min arrival index per departure index
    return arr


def _edge_idx(i, j):
    """lazy fine per-edge (c_arr, e_arr) arrival-index arrays: cheap (dv<=100) and exception (dv<=600). Cached."""
    key = (i, j)
    if key in _EDGE:
        return _EDGE[key]
    cc = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, 0.02 * DAY, THR, MAXREV)
    ee = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, 0.02 * DAY, EXC_THR, MAXREV)
    out = (_build_idx(cc), _build_idx(ee))
    _EDGE[key] = out
    return out


@njit(cache=True)
def _fwd_dp(c_arr, e_arr, n_legs, T, nexc):
    reach = np.zeros((n_legs + 1, T, nexc + 1), dtype=np.bool_)
    pdep = np.full((n_legs + 1, T, nexc + 1), -1, dtype=np.int32)
    pe = np.full((n_legs + 1, T, nexc + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True
    for k in range(n_legs):
        for e in range(nexc + 1):
            tmin = -1
            for t in range(T):
                if reach[k, t, e]:
                    tmin = t; break
            if tmin < 0:
                continue
            for tp in range(tmin, T):
                a = c_arr[k, tp]
                if a < T and not reach[k + 1, a, e]:
                    reach[k + 1, a, e] = True; pdep[k + 1, a, e] = tp; pe[k + 1, a, e] = 0
                if e < nexc:
                    a2 = e_arr[k, tp]
                    if a2 < T and not reach[k + 1, a2, e + 1]:
                        reach[k + 1, a2, e + 1] = True; pdep[k + 1, a2, e + 1] = tp; pe[k + 1, a2, e + 1] = 1
    return reach, pdep, pe


def retime(order, K=0, W=0, maxwait=0):
    """EXACT forward-DP schedule for `order` on the coarse grid (<=NEXC exceptions). Returns
    (makespan_days, times, tofs, n_exc) or (inf, None, None, NEXC+1). times/tofs in days for kt.fitness."""
    nl = len(order) - 1
    c_arr = np.full((nl, T), INF_INT, dtype=np.int32)
    e_arr = np.full((nl, T), INF_INT, dtype=np.int32)
    for k in range(nl):
        c, e = _edge_idx(order[k], order[k + 1])
        c_arr[k] = c; e_arr[k] = e
    reach, pdep, pe = _fwd_dp(c_arr, e_arr, nl, T, NEXC_PROXY)  # relaxed: grid rounding over-counts exceptions;
    # the EXACT official kt.fitness gate enforces the real <=5 limit. best final arrival index over exc levels
    best_t = -1; best_e = -1
    for e in range(NEXC_PROXY + 1):
        for t in range(T):
            if reach[nl, t, e]:
                if best_t < 0 or t < best_t:
                    best_t = t; best_e = e
                break
    if best_t < 0:
        return float("inf"), None, None, NEXC + 1
    # backtrack
    times = [0.0] * nl; tofs = [0.0] * nl
    t, e = best_t, best_e
    for k in range(nl, 0, -1):
        tp = int(pdep[k, t, e])
        if tp < 0:                                            # no recorded predecessor -> can't backtrack
            return float("inf"), None, None, NEXC + 1
        used = max(0, int(pe[k, t, e]))
        times[k - 1] = tp * TQ; tofs[k - 1] = (t - tp) * TQ
        e = max(0, e - used); t = tp
    return best_t * TQ, times, tofs, best_e


def official(order, times, tofs):
    dv = list(times) + list(tofs) + [float(c) for c in order]
    fit = kt.fitness(dv)
    return float(fit[0]), [float(x) for x in fit[1:]]


def main(iters=200000, K=6, W=40, maxwait=8.0):
    bank = np.array(json.load(open(f"{ROOT}/solutions/upload/medium.json"))[0]["decisionVector"])
    border = bank[2 * (N - 1):].astype(int).tolist()
    # POSITIVE CONTROL: retime the bank order, compare to official 189.10
    t0 = time.time()
    mk, ti, tf, eu = retime(border, K, W, maxwait)
    print(f"[E-731] POS-CONTROL bank order: retimer makespan {mk:.2f}d (exc {eu}) vs official 189.10 "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if ti is not None:
        omk, ov = official(border, ti, tf)
        print(f"[E-731] bank order official re-score from retimer schedule: {omk:.2f}d viols {ov}", flush=True)
    # OR-OPT / LNS search
    rng = 20260627
    cur = border; cur_mk = mk; best = border; best_mk = mk; acc = 0
    ckpt = f"{ROOT}/cache/ch2_medium_ordersearch_best.json"
    for it in range(iters):
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        L = 1 + (rng % 3); a = 1 + (rng % (len(cur) - L - 1))
        seg = cur[a:a + L]; rest = cur[:a] + cur[a + L:]
        b = 1 + ((rng >> 8) % (len(rest) - 1))
        cand = rest[:b] + seg + rest[b:]
        cmk, cti, ctf, ceu = retime(cand, K, W, maxwait)
        if cmk < cur_mk or (rng % 25 == 0 and cmk < cur_mk + 1.0):
            cur, cur_mk = cand, cmk; acc += 1
        if cmk < best_mk - 1e-6 and cti is not None:
            omk, ov = official(cand, cti, ctf)               # FINAL gate
            if max(ov) <= 1e-6 and omk < 189.10:
                best, best_mk = cand, omk
                json.dump({"order": cand, "times": cti, "tofs": ctf, "makespan": omk},
                          open(ckpt, "w"))
                tag = "*** RANK-1 (<186.27)!" if omk < 186.27 else "better-than-bank"
                print(f"[E-731] it{it}: OFFICIAL {omk:.3f}d (retimer {cmk:.2f}) viols ok -> {tag} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
        if it % 500 == 0:
            print(f"[E-731] it{it}: cur {cur_mk:.2f} best {best_mk:.2f} acc {acc} [{time.time()-t0:.0f}s]",
                  flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 200000, int(a[2]) if len(a) > 2 else 6,
         int(a[3]) if len(a) > 3 else 40, float(a[4]) if len(a) > 4 else 8.0)
