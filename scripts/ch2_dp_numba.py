"""Numba-JIT fast forward DP for Ch2 small ultrafine table.

Drop-in replacement for the slow Python forward DP in E-527/E-529.
Expected speedup: 10-50× depending on reachable-state density.
"""
from __future__ import annotations
import numpy as np
from numba import njit

INF_INT = 10**9


@njit(cache=True)
def forward_dp_numba(c_arr, e_arr, T, n_legs, n_exc_max):
    """Forward DP for one perm.
    Inputs:
      c_arr[k, t']  = arrival bucket if cheap transfer at leg k, dep bucket t', else INF
      e_arr[k, t']  = arrival bucket if exc transfer
      T              = number of t-buckets (4000)
      n_legs         = number of legs in perm (48)
      n_exc_max      = exception budget (5)
    Returns:
      reach[k, t, e]      bool array
      pred_t, pred_e,
      pred_dep, pred_isexc int arrays for backtracking
    """
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=np.bool_)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_isexc = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True

    for k in range(n_legs):
        # Iterate over reachable states at step k
        any_reach = False
        for t in range(T):
            for e in range(n_exc_max + 1):
                if not reach[k, t, e]:
                    continue
                any_reach = True
                # Cheap transitions from departure tp >= t
                for tp in range(t, T):
                    arr = c_arr[k, tp]
                    if arr < INF_INT and arr < T:
                        if not reach[k+1, arr, e]:
                            reach[k+1, arr, e] = True
                            pred_t[k+1, arr, e] = t
                            pred_e[k+1, arr, e] = e
                            pred_dep[k+1, arr, e] = tp
                            pred_isexc[k+1, arr, e] = 0
                # Exc transitions (if budget allows)
                if e < n_exc_max:
                    for tp in range(t, T):
                        arr = e_arr[k, tp]
                        if arr < INF_INT and arr < T:
                            if not reach[k+1, arr, e+1]:
                                reach[k+1, arr, e+1] = True
                                pred_t[k+1, arr, e+1] = t
                                pred_e[k+1, arr, e+1] = e
                                pred_dep[k+1, arr, e+1] = tp
                                pred_isexc[k+1, arr, e+1] = 1
        if not any_reach:
            break

    return reach, pred_t, pred_e, pred_dep, pred_isexc


def precompute_edges_for_perm(perm, cheap_tab, exc_tab, q, T):
    """For each leg, build (arr_bucket, actual_tof) lookup. Pure numpy."""
    n_legs = len(perm) - 1
    c_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    e_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    for k in range(n_legs):
        i, j = perm[k], perm[k+1]
        c_row = cheap_tab[i, j]
        e_row = exc_tab[i, j]
        # Vectorized
        c_finite = np.isfinite(c_row)
        e_finite = np.isfinite(e_row)
        c_tof[k, c_finite] = c_row[c_finite]
        e_tof[k, e_finite] = e_row[e_finite]
        c_arr_full = np.arange(T) + np.ceil(c_row / q).astype(np.int32)
        e_arr_full = np.arange(T) + np.ceil(e_row / q).astype(np.int32)
        c_arr[k, c_finite & (c_arr_full < T)] = c_arr_full[c_finite & (c_arr_full < T)]
        e_arr[k, e_finite & (e_arr_full < T)] = e_arr_full[e_finite & (e_arr_full < T)]
    return c_arr, c_tof, e_arr, e_tof


def dp_evaluate_numba(perm, cheap_tab, exc_tab, q, T, n_exc_max):
    """Returns ((sink_t, e_used, legs), c_tof, e_tof) or (None, c_tof, e_tof)."""
    n_legs = len(perm) - 1
    c_arr, c_tof, e_arr, e_tof = precompute_edges_for_perm(
        perm, cheap_tab, exc_tab, q, T)
    # Hopeless check
    for k in range(n_legs):
        if (c_arr[k] >= INF_INT).all() and (e_arr[k] >= INF_INT).all():
            return None, c_tof, e_tof

    reach, pred_t, pred_e, pred_dep, pred_isexc = forward_dp_numba(
        c_arr, e_arr, T, n_legs, n_exc_max)
    sink = reach[n_legs]
    finite_ts = np.where(sink.any(axis=1))[0]
    if len(finite_ts) == 0:
        return None, c_tof, e_tof
    min_t = int(finite_ts.min())
    e_used = int(np.where(sink[min_t])[0].min())
    legs = []
    k = n_legs; t = min_t; e = e_used
    while k > 0:
        prev_t = int(pred_t[k, t, e])
        prev_e = int(pred_e[k, t, e])
        dep = int(pred_dep[k, t, e])
        isexc = int(pred_isexc[k, t, e])
        legs.append((dep, t, isexc))
        k -= 1; t = prev_t; e = prev_e
    legs.reverse()
    return (min_t, e_used, legs), c_tof, e_tof


def reconstruct_actual_schedule(legs, c_tof, e_tof, q):
    times = [leg[0] * q for leg in legs]
    tofs = []
    for k, (dep, arr, isexc) in enumerate(legs):
        tof = float(e_tof[k, dep] if isexc else c_tof[k, dep])
        tofs.append(tof)
    return times, tofs


def evaluate_perm_dp_numba(kt, perm, cheap_tab, exc_tab, q, T):
    res = dp_evaluate_numba(perm, cheap_tab, exc_tab, q, T, kt.n_exc)
    if res[0] is None:
        return None
    min_t, e_used, legs = res[0]
    _, c_tof, e_tof = res
    times, tofs = reconstruct_actual_schedule(legs, c_tof, e_tof, q)
    fit = kt.fitness(list(times) + list(tofs) + [float(p) for p in perm])
    if not kt.is_feasible(fit):
        return None
    return {'mk': float(fit[0]), 'times': times, 'tofs': tofs,
            'e_used': e_used, 'feasible': True}
