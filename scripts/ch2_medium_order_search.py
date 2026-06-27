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
MINTOF = max(kt.min_tof, 0.01); MAXT = kt.max_time; DAY = 86400.0; N = kt.n
WIN = np.load(f"{ROOT}/cache/ch2_medium_windows.npz", allow_pickle=True)["windows"].item()
print(f"[E-731] medium n={N} dv_thr={THR} exc_thr={EXC_THR} n_exc={NEXC}; windows {len(WIN)} cheap edges", flush=True)


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
# infer the grid quantum from the precomputed window departures (must match the precompute dep_step)
_some = next(iter(WIN.values()))[0]
TQ = float(round(np.min(np.diff(np.unique(_some))), 4)) if len(_some) > 1 else 0.1
T = int(round(MAXT / TQ))                                       # time-index horizon
print(f"[E-731] window grid TQ={TQ}d  T={T}", flush=True)
INF_INT = 10 ** 9
# precompute per-edge coarse arrival-index arrays (cheap), once, from WIN: cidx[(i,j)] = arr_index per dep_index
_CIDX = {}
for (i, j), (deps, tofs) in WIN.items():
    arr = np.full(T, INF_INT, dtype=np.int32)
    di = np.round(deps / TQ).astype(np.int64)
    ai = np.round((deps + tofs) / TQ).astype(np.int64)
    ok = (di >= 0) & (ai < T) & (ai > di)
    arr[di[ok]] = np.minimum(arr[di[ok]], ai[ok])
    _CIDX[(i, j)] = arr
_EXC_CACHE = {}


def _exc_idx(i, j):
    """arrival-index array for EXCEPTION transfers (100<dv<=600) on i->j, per dep-index; numba scan, cached."""
    if (i, j) in _EXC_CACHE:
        return _EXC_CACHE[(i, j)]
    deps = np.arange(0.0, MAXT, TQ)
    et = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, 6.0 * DAY, 0.05 * DAY, EXC_THR, MAXREV)
    arr = np.full(T, INF_INT, dtype=np.int32)
    m = et > 0
    if m.any():
        di = np.round(deps[m] / TQ).astype(np.int64)
        ai = np.round((deps[m] + et[m] / DAY) / TQ).astype(np.int64)
        ok = (ai < T) & (ai > di)
        arr[di[ok]] = ai[ok]
    _EXC_CACHE[(i, j)] = arr
    return arr


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
        ij = (order[k], order[k + 1])
        ca = _CIDX.get(ij)
        if ca is not None:
            c_arr[k] = ca
        else:                                                  # no cheap window -> forced exception (numba scan)
            e_arr[k] = _exc_idx(ij[0], ij[1])
    reach, pdep, pe = _fwd_dp(c_arr, e_arr, nl, T, NEXC)
    # best final arrival index over exc levels
    best_t = -1; best_e = -1
    for e in range(NEXC + 1):
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
        tp = int(pdep[k, t, e]); used = int(pe[k, t, e])
        times[k - 1] = tp * TQ; tofs[k - 1] = (t - tp) * TQ
        e = e - used; t = tp
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
