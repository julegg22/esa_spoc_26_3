"""Fast table-based chronological walker for Ch2 KTTSP.

Uses precomputed time-coupled edge tables. ~100k walks/sec — enables
massive LNS over permutations.

API: fast_walk(perm, cheap_tbl, exc_tbl, t_starts, n_exc_budget=5)
  Returns (mk, times_q, tofs_d, exc_used, feasible) where mk is in days,
  times_q is in QUANTUM units (int array), tofs_d is in days (float).
"""
from __future__ import annotations
import sys, json
import numpy as np


def fast_walk(perm, cheap_tbl, exc_tbl, quantum, n_exc_budget=5,
              window_q=200, T_max_d=200.0, exc_policy='cheap_unless_infeasible',
              exc_threshold_d=2.0):
    """Greedy chronological walk using table. O(n * window_q) lookups.

    exc_policy:
      - 'cheap_unless_infeasible': use cheap whenever feasible; exc only fallback
      - 'cheap_unless_savings': use cheap unless exc saves > exc_threshold_d days
      - 'opportunistic': use exc whenever strictly faster than cheap
    """
    n = len(perm)
    T = cheap_tbl.shape[2]
    cur = perm[0]
    t_d = 0.0
    times_d = []
    tofs_d = []
    is_exc = []
    exc_used = 0
    for k in range(1, n):
        j = perm[k]
        t_min_q = int(np.ceil(t_d / quantum))
        if t_min_q >= T:
            return None, None, None, exc_used, False
        t_max_q = min(T, t_min_q + window_q)
        cs = cheap_tbl[cur, j, t_min_q:t_max_q]
        es = exc_tbl[cur, j, t_min_q:t_max_q]
        # Compute arrival for each feasible cell
        idxs = np.arange(t_min_q, t_max_q)
        cheap_arr = (idxs * quantum) + cs  # NaN if cs is inf
        exc_arr = (idxs * quantum) + es
        # Best cheap arrival
        best_cheap = np.inf
        best_cheap_idx = -1
        cheap_mask = np.isfinite(cheap_arr)
        if cheap_mask.any():
            best_cheap_idx = int(np.argmin(np.where(cheap_mask, cheap_arr, np.inf)))
            best_cheap = float(cheap_arr[best_cheap_idx])
        # Best exc arrival
        best_exc = np.inf
        best_exc_idx = -1
        if exc_used < n_exc_budget:
            exc_mask = np.isfinite(exc_arr)
            if exc_mask.any():
                best_exc_idx = int(np.argmin(np.where(exc_mask, exc_arr, np.inf)))
                best_exc = float(exc_arr[best_exc_idx])
        # Choose by policy
        if best_cheap == np.inf and best_exc == np.inf:
            return None, None, None, exc_used, False
        if exc_policy == 'cheap_unless_infeasible':
            use_exc_flag = (best_cheap == np.inf)
        elif exc_policy == 'cheap_unless_savings':
            use_exc_flag = (best_cheap == np.inf) or \
                (best_exc + exc_threshold_d < best_cheap)
        else:  # opportunistic
            use_exc_flag = best_cheap > best_exc
        if use_exc_flag:
            sel_idx = best_exc_idx
            sel_tof = float(es[sel_idx])
            sel_arr = best_exc
        else:
            sel_idx = best_cheap_idx
            sel_tof = float(cs[sel_idx])
            sel_arr = best_cheap
        if sel_arr > T_max_d:
            return None, None, None, exc_used, False
        t_dep_q = t_min_q + sel_idx
        times_d.append(float(t_dep_q * quantum))
        tofs_d.append(sel_tof)
        is_exc.append(use_exc_flag)
        if use_exc_flag:
            exc_used += 1
        t_d = sel_arr
        cur = j
    mk = times_d[-1] + tofs_d[-1]
    return mk, times_d, tofs_d, exc_used, True


def fast_walk_with_exc_planning(perm, cheap_tbl, exc_tbl, quantum,
                                  n_exc_budget=5, window_q=200,
                                  T_max_d=200.0, exc_reserve_for=None):
    """Variant: reserve last K exc slots for legs marked in exc_reserve_for."""
    n = len(perm)
    T = cheap_tbl.shape[2]
    cur = perm[0]
    t_d = 0.0
    times_d, tofs_d, is_exc = [], [], []
    exc_used = 0
    for k in range(1, n):
        j = perm[k]
        is_reserved_leg = (exc_reserve_for is not None and (k-1) in exc_reserve_for)
        budget_now = n_exc_budget if is_reserved_leg else \
                     n_exc_budget - (len([r for r in (exc_reserve_for or []) if r >= k]))
        t_min_q = int(np.ceil(t_d / quantum))
        if t_min_q >= T:
            return None, None, None, exc_used, False
        t_max_q = min(T, t_min_q + window_q)
        cs = cheap_tbl[cur, j, t_min_q:t_max_q]
        es = exc_tbl[cur, j, t_min_q:t_max_q]
        idxs = np.arange(t_min_q, t_max_q)
        cheap_arr = (idxs * quantum) + cs
        exc_arr = (idxs * quantum) + es
        best_cheap = np.inf
        best_cheap_idx = -1
        if np.isfinite(cheap_arr).any():
            mask = np.isfinite(cheap_arr)
            best_cheap_idx = int(np.argmin(np.where(mask, cheap_arr, np.inf)))
            best_cheap = float(cheap_arr[best_cheap_idx])
        best_exc = np.inf
        best_exc_idx = -1
        if exc_used < budget_now and np.isfinite(exc_arr).any():
            mask = np.isfinite(exc_arr)
            best_exc_idx = int(np.argmin(np.where(mask, exc_arr, np.inf)))
            best_exc = float(exc_arr[best_exc_idx])
        if best_cheap == np.inf and best_exc == np.inf:
            return None, None, None, exc_used, False
        if best_cheap <= best_exc:
            sel_idx, sel_tof, sel_arr = best_cheap_idx, float(cs[best_cheap_idx]), best_cheap
            ex = False
        else:
            sel_idx, sel_tof, sel_arr = best_exc_idx, float(es[best_exc_idx]), best_exc
            ex = True
        if sel_arr > T_max_d:
            return None, None, None, exc_used, False
        times_d.append(float((t_min_q + sel_idx) * quantum))
        tofs_d.append(sel_tof)
        is_exc.append(ex)
        if ex:
            exc_used += 1
        t_d = sel_arr
        cur = j
    return times_d[-1] + tofs_d[-1], times_d, tofs_d, exc_used, True


if __name__ == "__main__":
    # Smoke test: walk bank perm with coarse table; time the throughput
    import time
    import sys as _sys
    _sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
    from esa_spoc_26.ch2_kttsp import KTTSP

    INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
            "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(INST)
    d = np.load('/tmp/ch2_small_tcoupled.npz')
    cheap = d['cheap']
    exc = d['exc']
    t_starts = d['t_starts']
    quantum = float(t_starts[1] - t_starts[0])
    print(f"Coarse table: T={cheap.shape[2]}, quantum={quantum}d")

    bank = json.load(open("/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    print(f"Bank perm[:10]: {bank_perm[:10]}")

    # Single walk
    mk, times_d, tofs_d, exc_used, ok = fast_walk(
        bank_perm, cheap, exc, quantum, n_exc_budget=5)
    print(f"Bank perm walk: mk={mk} exc={exc_used} ok={ok}")

    # Throughput test
    import random
    rng = random.Random(0)
    t0 = time.time()
    n_calls = 10000
    n_feasible = 0
    for _ in range(n_calls):
        p = list(bank_perm)
        # Random 2-opt
        i = rng.randint(1, n - 3); j = rng.randint(i + 1, n - 2)
        p[i:j+1] = p[i:j+1][::-1]
        res = fast_walk(p, cheap, exc, quantum, n_exc_budget=5)
        if res[4]:
            n_feasible += 1
    wall = time.time() - t0
    print(f"Throughput: {n_calls}/{wall:.2f}s = {n_calls/wall:.0f} walks/sec")
    print(f"Feasible: {n_feasible}/{n_calls} = {n_feasible/n_calls*100:.0f}%")
