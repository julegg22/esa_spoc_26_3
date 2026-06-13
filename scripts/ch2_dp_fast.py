"""Faster forward DP for Ch2 small order search (E-609).

Same semantics as scripts/ch2_dp_numba.evaluate_perm_dp_numba (the trusted
oracle), but the inner per-leg propagation is vectorized and avoids the
O(T^2) python/numba double loop. Used only as an INNER timing oracle inside
the order search; any beating order is re-verified through the trusted
ch2_dp_numba + official KTTSP.fitness before being reported.

State: reach[t, e] = True if arrival bucket t reachable at current step with
e exceptions used. Per leg we propagate:
  - "earliest reachable t" frontier: for a given set of reachable arrival
    buckets at step k, a leg can DEPART at any bucket tp >= (some reachable t).
    Since waiting is free (departures only need tp >= reachable arrival), the
    set of feasible departure buckets is {tp : tp >= min reachable t in this
    e-layer that is <= tp}. Equivalent: tp is a feasible departure iff there
    exists a reachable arrival bucket <= tp. So departure-feasibility is a
    suffix-OR (cumulative max) of the reachable mask over t.
  - For each feasible departure bucket tp, arrival = c_arr[k,tp] (cheap) or
    e_arr[k,tp] (exc). Scatter those arrivals into the next layer.
"""
from __future__ import annotations
import numpy as np
from numba import njit

INF_INT = 10**9


@njit(cache=True)
def _forward(c_arr, e_arr, T, n_legs, n_exc):
    # reach[t, e]
    reach = np.zeros((T, n_exc + 1), dtype=np.bool_)
    pred_dep = np.full((n_legs + 1, T, n_exc + 1), -1, dtype=np.int32)
    pred_te = np.full((n_legs + 1, T, n_exc + 1), -1, dtype=np.int32)  # prev t
    pred_pe = np.full((n_legs + 1, T, n_exc + 1), -1, dtype=np.int8)   # prev e
    pred_ex = np.full((n_legs + 1, T, n_exc + 1), -1, dtype=np.int8)
    reach[0, 0] = True

    for k in range(n_legs):
        nxt = np.zeros((T, n_exc + 1), dtype=np.bool_)
        any_reach = False
        for e in range(n_exc + 1):
            # earliest reachable arrival bucket in this e-layer
            first_t = -1
            for t in range(T):
                if reach[t, e]:
                    first_t = t
                    break
            if first_t < 0:
                continue
            any_reach = True
            # departures tp >= first_t are feasible (wait is free).
            # cheap: scatter arrivals
            for tp in range(first_t, T):
                arr = c_arr[k, tp]
                if arr < T:
                    if not nxt[arr, e]:
                        nxt[arr, e] = True
                        pred_dep[k + 1, arr, e] = tp
                        pred_te[k + 1, arr, e] = first_t
                        pred_pe[k + 1, arr, e] = e
                        pred_ex[k + 1, arr, e] = 0
            if e < n_exc:
                for tp in range(first_t, T):
                    arr = e_arr[k, tp]
                    if arr < T:
                        if not nxt[arr, e + 1]:
                            nxt[arr, e + 1] = True
                            pred_dep[k + 1, arr, e + 1] = tp
                            pred_te[k + 1, arr, e + 1] = first_t
                            pred_pe[k + 1, arr, e + 1] = e
                            pred_ex[k + 1, arr, e + 1] = 1
        reach = nxt
        if not any_reach:
            return reach, pred_dep, pred_te, pred_pe, pred_ex, k
    return reach, pred_dep, pred_te, pred_pe, pred_ex, n_legs


def _precompute(perm, cheap_tab, exc_tab, q, T):
    n_legs = len(perm) - 1
    c_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    e_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    e_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    ar = np.arange(T)
    for k in range(n_legs):
        i, j = perm[k], perm[k + 1]
        c_row = cheap_tab[i, j]
        e_row = exc_tab[i, j]
        cf = np.isfinite(c_row)
        ef = np.isfinite(e_row)
        c_tof[k, cf] = c_row[cf]
        e_tof[k, ef] = e_row[ef]
        if cf.any():
            ca = ar + np.ceil(np.where(cf, c_row, 0.0) / q).astype(np.int64)
            m = cf & (ca < T)
            c_arr[k, m] = ca[m]
        if ef.any():
            ea = ar + np.ceil(np.where(ef, e_row, 0.0) / q).astype(np.int64)
            m = ef & (ea < T)
            e_arr[k, m] = ea[m]
    return c_arr, e_arr, c_tof, e_tof


def dp_fast(perm, cheap_tab, exc_tab, q, T, n_exc):
    """Returns dict with mk_bucket, e_used, legs, c_tof, e_tof or None."""
    n_legs = len(perm) - 1
    c_arr, e_arr, c_tof, e_tof = _precompute(perm, cheap_tab, exc_tab, q, T)
    # hopeless check: any leg with no edge at all
    for k in range(n_legs):
        if (c_arr[k] >= INF_INT).all() and (e_arr[k] >= INF_INT).all():
            return None
    reach, pred_dep, pred_te, pred_pe, pred_ex, reached = _forward(
        c_arr, e_arr, T, n_legs, n_exc)
    if reached < n_legs:
        return None
    sink = reach  # reach[t,e] at step n_legs
    ts = np.where(sink.any(axis=1))[0]
    if len(ts) == 0:
        return None
    min_t = int(ts.min())
    e_used = int(np.where(sink[min_t])[0].min())
    legs = []
    k = n_legs
    t = min_t
    e = e_used
    while k > 0:
        dep = int(pred_dep[k, t, e])
        pt = int(pred_te[k, t, e])
        pe = int(pred_pe[k, t, e])
        ex = int(pred_ex[k, t, e])
        legs.append((dep, t, ex))
        k -= 1
        t = pt
        e = pe
    legs.reverse()
    return {'min_t': min_t, 'e_used': e_used, 'legs': legs,
            'c_tof': c_tof, 'e_tof': e_tof}


def makespan_fast(perm, cheap_tab, exc_tab, q, T, n_exc):
    """Cheap scalar makespan (in days) or None. Uses bucketed timing."""
    r = dp_fast(perm, cheap_tab, exc_tab, q, T, n_exc)
    if r is None:
        return None
    # actual final arrival = dep_bucket*q + tof of last leg
    legs = r['legs']
    c_tof = r['c_tof']
    e_tof = r['e_tof']
    dep, arr, ex = legs[-1]
    tof = float(e_tof[len(legs) - 1, dep] if ex else c_tof[len(legs) - 1, dep])
    mk = dep * q + tof
    return mk
