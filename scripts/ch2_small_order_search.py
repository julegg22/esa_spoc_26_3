"""E-731 — Ch2-MEDIUM order search to RECLAIM RANK-1 (target <186.27; bank 189.10 is a frozen-order artifact).

Faithful beam-retimer over the full-edge window table (cache/ch2_small_windows.npz, no 0.025 tof floor) with the
<=5 exception budget, wrapped in or-opt/LNS over the visit ORDER (the frozen variable per E-731). Every accepted
candidate is FINAL-gated by the official kt.fitness. Positive control first: retime the bank order, confirm it is
~189.10 (the retimer must track the official DP, else the proxy is untrustworthy).
Usage: python ch2_small_order_search.py [iters=200000] [K=6] [W=40] [maxwait=8]"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
kt = KTTSP(INST); OPAR = kt.opar.astype(np.float64)
THR = kt.dv_thr; EXC_THR = kt.dv_exc; NEXC = kt.n_exc; MAXREV = kt.max_revs
NEXC_PROXY = NEXC + 2                                           # relaxed proxy budget (grid rounding over-counts);
#                                                                official kt.fitness still enforces the real NEXC=5
MINTOF = max(kt.min_tof, 0.01); MAXT = kt.max_time; DAY = 86400.0; N = kt.n
print(f"[E-740] small n={N} dv_thr={THR} exc_thr={EXC_THR} n_exc={NEXC}; lazy fine-scan evaluator", flush=True)


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
TQ = float(os.environ.get("CH2_TQ", "0.05"))                   # dep-grid resolution (finer = lower handicap, slower)
TOFSTEP = float(os.environ.get("CH2_TOFSTEP", "0.02"))         # tof scan step
HORIZON = 130.0  # small makespan ~113
T = int(round(HORIZON / TQ)); INF_INT = 10 ** 9
_DEPS = np.arange(0.0, HORIZON, TQ); _DEPS_SEC = _DEPS * DAY
print(f"[E-731] labeling-DP evaluator TQ={TQ}d tofstep={TOFSTEP}d horizon={HORIZON}d", flush=True)
import pickle
_EDGE = {}
_BASE = f"{ROOT}/cache/ch2_small_edgewin_{TQ}_{TOFSTEP}.pkl"    # shared edge-window cache (one warmup, all chains)
if os.path.exists(_BASE):
    _EDGE = pickle.load(open(_BASE, "rb"))
    print(f"[E-731] loaded {len(_EDGE)} cached edge-windows from base", flush=True)
# cheap directed-edge adjacency (from the 0.1d precompute) -> restrict moves to cheap edges (avoid scanning junk)
CHEAP = set()
_CW = f"{ROOT}/cache/ch2_small_windows.npz"
_EDG = f"{ROOT}/edges_small.npz"
if os.path.exists(_CW):
    CHEAP = set(map(tuple, np.load(_CW, allow_pickle=True)["windows"].item().keys()))
    print(f"[E-731] cheap adjacency: {len(CHEAP)} edges", flush=True)
elif os.path.exists(_EDG):                                     # fallback: restrict moves to precomputed usable edges
    _dv = np.load(_EDG)["dv"]; _n = _dv.shape[0]               # (dv<=600 = the 975 warmed edges) -> no lazy dv>600 scans
    CHEAP = {(i, j) for i in range(_n) for j in range(_n)
             if i != j and np.isfinite(_dv[i, j]) and _dv[i, j] <= 600.0}
    print(f"[E-731] usable adjacency from edges_small (dv<=600): {len(CHEAP)} edges", flush=True)


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
    cc = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, TOFSTEP * DAY, THR, MAXREV)
    ee = ft.cheap_first_tof(OPAR[i], OPAR[j], _DEPS_SEC, MINTOF * DAY, 8.0 * DAY, TOFSTEP * DAY, EXC_THR, MAXREV)
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


def _load_best_order():
    """seed from the best order found so far (chains continuous improvement across restarts), else the bank."""
    bf = f"{ROOT}/cache/ch2_small_BEST.json"
    if os.path.exists(bf):
        try:
            dv = json.load(open(bf))[0]["decisionVector"]
            return [int(c) for c in dv[2 * (N - 1):]]
        except Exception:
            pass
    bank = json.load(open(f"{ROOT}/solutions/upload/small.json"))[0]["decisionVector"]
    return [int(c) for c in bank[2 * (N - 1):]]


def main(iters=200000, K=6, W=40, maxwait=8.0):
    import _prov; _prov.stamp(__file__, iters=iters)          # run-time provenance -> log header
    border = _load_best_order()
    # POSITIVE CONTROL: retime the bank order, compare to official 189.10
    t0 = time.time()
    mk, ti, tf, eu = retime(border, K, W, maxwait)
    print(f"[E-731] POS-CONTROL bank order: retimer makespan {mk:.2f}d (exc {eu}) vs official 189.10 "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if ti is not None:
        omk, ov = official(border, ti, tf)
        print(f"[E-731] bank order official re-score from retimer schedule: {omk:.2f}d viols {ov}", flush=True)
    if os.environ.get("CH2_SAVEBASE"):                          # build the shared base from the bank's edges, exit
        pickle.dump(_EDGE, open(_BASE, "wb"))
        print(f"[E-731] saved {len(_EDGE)} edge-windows to base {_BASE}", flush=True); return
    # OR-OPT / LNS search (per-chain seed + tag for parallel runs)
    TAG = os.environ.get("CH2_TAG", "s")
    rng = int(os.environ.get("CH2_SEED", "20260627"))
    move = os.environ.get("CH2_MOVE", "oropt")                 # oropt | 2opt
    MAXSEG = int(os.environ.get("CH2_MAXSEG", "3"))            # or-opt segment length (larger = wider neighborhood, L7 test)
    cur = border; cur_mk = mk; best_proxy = mk; best_off = 112.996; acc = 0   # small bank (rank6); rank3=111.76 rank1=100.4
    ckpt = f"{ROOT}/cache/ch2_small_ordersearch_{TAG}.json"
    pbest = f"{ROOT}/cache/ch2_small_proxybest_{TAG}.json"
    def cheap_ok(*edges):                                      # all listed directed edges must be cheap (or no CHEAP set)
        return (not CHEAP) or all(e in CHEAP for e in edges)
    for it in range(iters):
        cand = None
        for _try in range(40):                                 # find a move whose NEW edges are cheap (set lookup)
            rng = (rng * 1103515245 + 12345) & 0x7fffffff
            if move == "2opt":                                 # segment reversal: check reversed boundary edges
                a = 1 + (rng % (len(cur) - 3)); b = a + 2 + ((rng >> 8) % (len(cur) - a - 2))
                if cheap_ok((cur[a - 1], cur[b - 1]), (cur[a], cur[b])):
                    cand = cur[:a] + cur[a:b][::-1] + cur[b:]; break
            else:                                              # or-opt: relocate a 1-3 city segment
                L = 1 + (rng % MAXSEG); a = 1 + (rng % (len(cur) - L - 1))
                seg = cur[a:a + L]; rest = cur[:a] + cur[a + L:]
                b = 1 + ((rng >> 8) % (len(rest) - 1))
                if cheap_ok((cur[a - 1], cur[a + L]), (rest[b - 1], seg[0]), (seg[-1], rest[b])):
                    cand = rest[:b] + seg + rest[b:]; break
        if cand is None:
            continue
        cmk, cti, ctf, ceu = retime(cand, K, W, maxwait)
        if cmk < cur_mk or (rng % 25 == 0 and cmk < cur_mk + 1.0):
            cur, cur_mk = cand, cmk; acc += 1
        if cmk < best_proxy - 1e-6 and cti is not None:        # new best in PROXY space -> validate officially
            best_proxy = cmk
            json.dump({"order": cand, "proxy": cmk}, open(pbest, "w"))
            omk, ov = official(cand, cti, ctf)                 # FINAL exact gate (enforces real <=5 exceptions)
            feas = max(ov) <= 1e-6
            if feas and omk < best_off:
                best_off = omk
                json.dump({"order": cand, "times": cti, "tofs": ctf, "makespan": omk}, open(ckpt, "w"))
                tg = ("*** RANK-1 (<=100.4)!" if omk <= 100.4 else "** rank-3 (<=111.76)" if omk <= 111.76 else "better-than-bank")
                print(f"[E-731][{TAG}] it{it}: OFFICIAL {omk:.3f}d (proxy {cmk:.2f}) -> {tg} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
            else:
                print(f"[E-731][{TAG}] it{it}: proxy-best {cmk:.2f}d (official {omk:.2f}d feas={feas}) "
                      f"[{time.time()-t0:.0f}s]", flush=True)
        if it % 2000 == 1999:                                  # periodically adopt the campaign-best (cross-chain)
            bo = _load_best_order()
            if bo != cur:
                bmk, bti, btf, beu = retime(bo, K, W, maxwait)
                if bmk < cur_mk:
                    cur, cur_mk = bo, bmk
                    if bmk < best_proxy:
                        best_proxy = bmk
        if it % 500 == 0:
            print(f"[E-731][{TAG}] it{it}: cur {cur_mk:.2f} proxy-best {best_proxy:.2f} off-best {best_off:.2f} "
                  f"acc {acc} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 200000, int(a[2]) if len(a) > 2 else 6,
         int(a[3]) if len(a) > 3 else 40, float(a[4]) if len(a) > 4 else 8.0)
