"""Ch2 KTTSP — greedy via the OFFICIAL find_transfer helper pattern.

Critical insight from reading SpOC4/utils_users.py:
the official `find_transfer(i, j, t_start, dv_thr, max_time=5.0, n_steps=1000)`
returns the EARLIEST tof such that Δv ≤ dv_thr at fixed t_start —
NOT the global-min-Δv tof. This implies competitors do greedy on
arrival time using min-tof-feasible transfers, scanning tof at fine
resolution (1000 steps over 5 d ⇒ 5 ms tof step) within a per-step
window. With this, even tight 112 d makespans become tractable.

Implementation: per step (cur, t_ready), for each unvisited j scan
tof ∈ [min_tof, tof_window] at step δ; record first feasible
(tof, Δv) at threshold dv_thr; pick j minimising (t_ready + tof).
If no cheap transfer found, retry at exc threshold (if budget left)
and/or advance t_ready by Δt (wait).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def find_earliest_transfer(kt, i, j, t_start, dv_thr, tof_window=5.0,
                           n_steps=200):
    """Return (tof, dv) of the earliest tof ∈ [min_tof, tof_window]
    at which compute_transfer(i, j, t_start, tof) ≤ dv_thr.
    Returns (None, None) if not found."""
    if t_start + tof_window > kt.max_time:
        tof_window = max(kt.min_tof + 1e-3, kt.max_time - t_start - 1e-3)
        if tof_window <= kt.min_tof:
            return None, None
    grid = np.linspace(max(kt.min_tof, 0.05), tof_window, n_steps)
    for tof in grid:
        dv = kt.compute_transfer(i, j, float(t_start), float(tof))
        if dv <= dv_thr + 1e-6:
            return float(tof), float(dv)
    return None, None


def find_earliest_transfer_fast(kt, i, j, t_start, dv_thr, tof_window=40.0,
                                n_coarse=60, n_fine=40):
    """~10-40x faster find_earliest_transfer: COARSE scan to locate the first cheap region,
    then FINE-refine for the earliest cheap tof within it (resolution ≈ n_steps=2400 equiv).
    Fast None when no coarse point is cheap. Small risk of missing a sub-coarse-spacing cheap
    window (densify n_coarse if the retime control drifts >2%). Same (tof,dv) semantics."""
    if t_start + tof_window > kt.max_time:
        tof_window = max(kt.min_tof + 1e-3, kt.max_time - t_start - 1e-3)
        if tof_window <= kt.min_tof:
            return None, None
    lo = max(kt.min_tof, 0.05)
    coarse = np.linspace(lo, tof_window, n_coarse)
    kfound = -1
    for k, tof in enumerate(coarse):
        dv = kt.compute_transfer(i, j, float(t_start), float(tof))
        if dv <= dv_thr + 1e-6:
            kfound = k
            break
    if kfound < 0:
        return None, None
    a = coarse[kfound - 1] if kfound > 0 else lo
    b = coarse[kfound]
    fine = np.linspace(a, b, n_fine)
    for tof in fine:                       # earliest cheap in the bracketing sub-interval
        dv = kt.compute_transfer(i, j, float(t_start), float(tof))
        if dv <= dv_thr + 1e-6:
            return float(tof), float(dv)
    # fine missed (boundary numerics) -> fall back to the coarse hit
    tof = float(coarse[kfound])
    return tof, float(kt.compute_transfer(i, j, float(t_start), tof))


def greedy_findxfer(kt, start, tof_window=12.0, n_steps=120,
                    wait_steps=4, wait_dt=0.5, verbose=False):
    """Greedy: at (cur, t), for each unvisited j find earliest feasible
    transfer. Try cheap (dv_thr) first; if no j feasible cheap and exc
    budget left, try exc (dv_exc); if still none, advance t and retry."""
    n = kt.n
    cur, t = start, 0.0
    unvis = set(range(n)) - {start}
    perm, times, tofs, dvs = [start], [], [], []
    exc = 0
    while unvis:
        best = None  # (arr, j, tof, dv, is_exc)
        # Try cheap first
        for j in unvis:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                              tof_window, n_steps)
            if tof is not None:
                arr = t + tof
                if best is None or arr < best[0]:
                    best = (arr, j, tof, dv, False)
        # If no cheap, try exc
        if best is None and exc < kt.n_exc:
            for j in unvis:
                tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                                  tof_window, n_steps)
                if tof is not None:
                    arr = t + tof
                    if best is None or arr < best[0]:
                        best = (arr, j, tof, dv, True)
        # If still none, try waiting
        if best is None:
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                for j in unvis:
                    tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                     kt.dv_thr,
                                                     tof_window, n_steps)
                    if tof is not None:
                        arr = t_try + tof
                        if best is None or arr < best[0]:
                            best = (arr, j, tof, dv, False)
                            t = t_try
                            break
                if best is not None:
                    break
            if best is None and exc < kt.n_exc:
                for w in range(1, wait_steps + 1):
                    t_try = t + w * wait_dt
                    if t_try >= kt.max_time:
                        break
                    for j in unvis:
                        tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                         kt.dv_exc,
                                                         tof_window, n_steps)
                        if tof is not None:
                            arr = t_try + tof
                            if best is None or arr < best[0]:
                                best = (arr, j, tof, dv, True)
                                t = t_try
                                break
                    if best is not None:
                        break
        if best is None:
            return perm, times, tofs, dvs, False
        _, j, tof, dv, is_exc = best
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        perm.append(j)
        if is_exc:
            exc += 1
        t = t + tof
        unvis.discard(j)
        cur = j
        if verbose:
            print(f"  → t={t:.2f} cur={cur} dvs={dv:.1f} exc={exc} unvis={len(unvis)}",
                  flush=True)
    return perm, times, tofs, dvs, True


_WORKER_KT_FX = [None]


def _init_worker_fx(inst):
    _WORKER_KT_FX[0] = KTTSP(inst)


def _worker_search(args):
    st, tof_window, n_steps = args
    kt = _WORKER_KT_FX[0]
    perm, times, tofs, dvs, ok = greedy_findxfer(
        kt, start=st, tof_window=tof_window, n_steps=n_steps,
        verbose=False)
    return st, perm, times, tofs, dvs, ok


def search(inst, problem="small",
           out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
           tof_window=12.0, n_steps=120, n_starts=49, n_workers=4,
           verbose=False):
    import multiprocessing as mp
    kt = KTTSP(inst)
    best_full = None
    best_partial = None
    results = []
    t0 = time.time()
    args = [(st, tof_window, n_steps)
            for st in range(min(n_starts, kt.n))]
    with mp.Pool(n_workers, initializer=_init_worker_fx,
                 initargs=(inst,)) as pool:
        for st, perm, times, tofs, dvs, ok in pool.imap_unordered(
                _worker_search, args):
            legs = len(perm) - 1
            if ok and legs == kt.n - 1:
                mk = times[-1] + tofs[-1]
                results.append({"start": st, "mk": round(mk, 2),
                                "legs": legs,
                                "n_exc": sum(1 for d in dvs if d > kt.dv_thr)})
                if best_full is None or mk < best_full[0]:
                    best_full = (mk, st, perm, times, tofs, dvs)
            else:
                results.append({"start": st, "legs": legs, "ok": ok})
                if best_partial is None or legs > best_partial[0]:
                    best_partial = (legs, st, perm, times, tofs, dvs)
    wall = time.time() - t0
    info = {"problem": problem, "n": kt.n, "wall_s": round(wall, 1),
            "n_full": sum(1 for r in results if r.get("legs") == kt.n - 1),
            "results_summary": results,
            "rank3_small_d": 111.76}
    if best_full is not None:
        mk, st, perm, times, tofs, dvs = best_full
        x = times + tofs + [float(p) for p in perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        info["best_full"] = {"start": st, "makespan_d": round(mk, 3),
                             "fitness": list(f), "feasible": feas,
                             "perm": [int(p) for p in perm]}
        if feas:
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["artifact"] = str(p)
    if best_partial is not None:
        legs_cov, st, perm, _, _, _ = best_partial
        info["best_partial"] = {"start": st, "legs": legs_cov,
                                "perm_so_far": [int(p) for p in perm]}
    return info


if __name__ == "__main__":
    import sys
    # Default to small (easy) instance; override via CLI arg 2
    instance_name = sys.argv[2] if len(sys.argv) > 2 else "easy"
    inst = (f"reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{instance_name}.kttsp")
    starts = int(sys.argv[1]) if len(sys.argv) > 1 else 49
    print(json.dumps(search(inst, n_starts=starts,
                            problem=instance_name), indent=2))
