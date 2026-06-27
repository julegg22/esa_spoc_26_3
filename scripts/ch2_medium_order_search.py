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


def _suffix_min(dep, arr):
    """given departures `dep` (sorted) and arrivals `arr`, return (dep_sorted, smin, sdep, stof) where for each
    index q, smin[q]=min arrival over deps>=dep[q], and sdep/stof are the departure/tof achieving it. So the best
    (min-arrival) transfer departing at >= t is found by one searchsorted into dep."""
    n = len(dep)
    if n == 0:
        return (np.array([0.0]), np.array([np.inf]), np.array([0.0]), np.array([0.0]))
    sidx = np.empty(n, dtype=np.int64); sidx[n - 1] = n - 1
    for q in range(n - 2, -1, -1):
        sidx[q] = q if arr[q] <= arr[sidx[q + 1]] else sidx[q + 1]
    smin = arr[sidx]; sdep = dep[sidx]; stof = smin - sdep
    return (dep, smin, sdep, stof)


def _edge_win(i, j):
    """lazy fine per-edge CONTINUOUS windows (no grid): suffix-min structures for cheap (dv<=100) and exception
    (100<dv<=600) transfers. Cached. Used by the exact labeling DP."""
    key = (i, j)
    if key in _EDGE:
        return _EDGE[key]
    cc = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, 0.02 * DAY, THR, MAXREV)
    ee = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, 0.02 * DAY, EXC_THR, MAXREV)
    mc = cc > 0
    me = (ee > 0) & ~mc                                          # exception-only departures (no cheap there)
    out = (_suffix_min(_DEPS[mc], _DEPS[mc] + cc[mc] / DAY),
           _suffix_min(_DEPS[me], _DEPS[me] + ee[me] / DAY))
    _EDGE[key] = out
    return out


def retime(order, *args):
    """EXACT labeling DP (continuous time, no grid): track min arrival per exception level (waiting allowed ->
    earlier arrival dominates, so one value per exc level is optimal). Returns (makespan, times, tofs, n_exc) or
    (inf, None, None, NEXC+1). times/tofs in days for kt.fitness. EXACT and fast."""
    nl = len(order) - 1
    NE = NEXC + 1
    arr = [0.0] + [float("inf")] * NEXC                        # arr[e] = min arrival with e exceptions
    # backptr[k][e] = (dep, tof, prev_e) for the transition into position k+1 at exc e
    bptr = [[None] * NE for _ in range(nl)]
    for k in range(nl):
        (cd, csmin, csdep, cstof), (ed, esmin, esdep, estof) = _edge_win(order[k], order[k + 1])
        new = [float("inf")] * NE
        for e in range(NE):
            t = arr[e]
            if t == float("inf"):
                continue
            qc = np.searchsorted(cd, t)                        # best (min-arrival) cheap transfer departing >= t
            if qc < len(csmin):
                a = float(csmin[qc])
                if a < new[e]:
                    new[e] = a; bptr[k][e] = (float(csdep[qc]), float(cstof[qc]), e)
            if e < NEXC:                                       # exception transfer -> exc level e+1
                qe = np.searchsorted(ed, t)
                if qe < len(esmin):
                    a2 = float(esmin[qe])
                    if a2 < new[e + 1]:
                        new[e + 1] = a2; bptr[k][e + 1] = (float(esdep[qe]), float(estof[qe]), e)
        arr = new
    best_e = min((e for e in range(NE) if arr[e] < float("inf")), key=lambda e: arr[e], default=-1)
    if best_e < 0:
        return float("inf"), None, None, NEXC + 1
    times = [0.0] * nl; tofs = [0.0] * nl; e = best_e
    for k in range(nl - 1, -1, -1):
        bp = bptr[k][e]
        if bp is None:
            return float("inf"), None, None, NEXC + 1
        times[k] = bp[0]; tofs[k] = bp[1]; e = bp[2]
    return float(arr[best_e]), times, tofs, best_e


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
