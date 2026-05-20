"""Ch2 KTTSP — small-cluster-FIRST construction (structural alternative).

Hypothesis: starting at a small-cluster node and traversing the entire
small cluster cheaply BEFORE bridging to big cluster saves one
exception slot (cluster-entry-via-depot is free; only cluster-exit
costs an exception). The 5-slot budget becomes: 0 entry + 1 exit + 4
big-cluster transitions, vs the current 1 entry + 1 exit + 3 big-cluster.

For each of 6 cluster orderings (3! permutations of {4, 17, 11}):
1. Build forced cluster opener (3 cheap internal legs).
2. Continue greedy_findxfer over the 46 big-cluster nodes.
3. If full tour: 2-opt polish.
4. Bank best feasible.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

CLUSTER = (4, 17, 11)


def greedy_continue(kt, perm0, t0, exc0=0, tof_window=12.0, n_steps=120,
                    wait_steps=4, wait_dt=0.5):
    """Continue the greedy_findxfer pattern from a forced opener.
    perm0 = list of already-visited nodes (must be non-empty), t0 = time
    after the opener, exc0 = exceptions already spent. Returns
    (full_perm, times, tofs, dvs, full_ok)."""
    perm = list(perm0)
    cur = perm[-1]
    unvis = set(range(kt.n)) - set(perm)
    times, tofs, dvs = [], [], []
    t = t0
    exc = exc0
    while unvis:
        best = None
        # Cheap first
        for j in unvis:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                              tof_window, n_steps)
            if tof is not None:
                arr = t + tof
                if best is None or arr < best[0]:
                    best = (arr, j, tof, dv, False)
        # Exception
        if best is None and exc < kt.n_exc:
            for j in unvis:
                tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                                  tof_window, n_steps)
                if tof is not None:
                    arr = t + tof
                    if best is None or arr < best[0]:
                        best = (arr, j, tof, dv, True)
        # Wait + retry
        if best is None:
            found = False
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                for j in unvis:
                    tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                     kt.dv_thr,
                                                     tof_window, n_steps)
                    if tof is not None:
                        t = t_try
                        best = (t + tof, j, tof, dv, False)
                        found = True
                        break
                if found:
                    break
            if not found and exc < kt.n_exc:
                for w in range(1, wait_steps + 1):
                    t_try = t + w * wait_dt
                    if t_try >= kt.max_time:
                        break
                    for j in unvis:
                        tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                          kt.dv_exc,
                                                          tof_window,
                                                          n_steps)
                        if tof is not None:
                            t = t_try
                            best = (t + tof, j, tof, dv, True)
                            found = True
                            break
                    if found:
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
        cur = j
    return perm, times, tofs, dvs, True


def build_cluster_opener(kt, ordering, tof_window=8.0, n_steps=200):
    """Walk the cluster nodes in order, finding cheap (<= dv_thr)
    transfers internally. Returns (perm=[ordering], times, tofs, dvs,
    t_end, exc_used) or None if any internal leg infeasible."""
    perm = [ordering[0]]
    times, tofs, dvs = [], [], []
    t = 0.0
    cur = ordering[0]
    exc = 0
    for nxt in ordering[1:]:
        # internal cluster is cheap; tight tof_window since they're nearby
        tof, dv = find_earliest_transfer(kt, cur, nxt, t, kt.dv_thr,
                                          tof_window, n_steps)
        if tof is None:
            tof, dv = find_earliest_transfer(kt, cur, nxt, t, kt.dv_exc,
                                              tof_window, n_steps)
            if tof is None:
                return None
            exc += 1
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        perm.append(nxt)
        t = t + tof
        cur = nxt
    return perm, times, tofs, dvs, t, exc


def search(inst, problem="small",
           out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
           tof_window_opener=8.0, n_steps_opener=200,
           tof_window_main=12.0, n_steps_main=120, verbose=True):
    kt = KTTSP(inst)
    n = kt.n
    results = []
    full_tours = []
    t0_global = time.time()
    for ordering in itertools.permutations(CLUSTER):
        if verbose:
            print(f"--- ordering {ordering} ---", flush=True)
        opener = build_cluster_opener(kt, ordering,
                                      tof_window=tof_window_opener,
                                      n_steps=n_steps_opener)
        if opener is None:
            results.append({"ordering": list(ordering),
                            "opener_ok": False})
            continue
        perm_o, t_o, tof_o, dv_o, t_end, exc_used = opener
        if verbose:
            print(f"  opener: perm={perm_o}, t_end={t_end:.2f}, "
                  f"exc_used={exc_used}, dvs={[round(d,1) for d in dv_o]}",
                  flush=True)
        # Continue greedy from cluster[-1]
        perm, times, tofs, dvs, ok = greedy_continue(
            kt, perm_o, t_end, exc_used,
            tof_window=tof_window_main, n_steps=n_steps_main)
        # Combine opener + continuation
        all_times = t_o + times
        all_tofs = tof_o + tof_o[:0] + tofs  # opener + continuation
        # Actually: t_o is opener's times, tofs is continuation's tofs
        # Need: all_times = opener_times + continuation_times
        #       all_tofs = opener_tofs + continuation_tofs
        all_times = t_o + times
        all_tofs = tof_o + tofs
        all_dvs = dv_o + dvs
        legs = len(perm) - 1
        if ok and legs == n - 1:
            mk = all_times[-1] + all_tofs[-1]
            full_tours.append({
                "ordering": list(ordering), "mk": round(mk, 3),
                "perm": [int(p) for p in perm], "exc_total":
                sum(1 for d in all_dvs if d > kt.dv_thr),
                "all_times": all_times, "all_tofs": all_tofs,
                "all_dvs": all_dvs,
            })
            if verbose:
                print(f"  FULL TOUR: mk={mk:.2f}, n_exc={sum(1 for d in all_dvs if d > kt.dv_thr)}",
                      flush=True)
        else:
            results.append({"ordering": list(ordering),
                            "legs": legs, "ok": ok,
                            "perm_partial": [int(p) for p in perm]})
            if verbose:
                print(f"  PARTIAL: legs={legs}, missing={sorted(set(range(n)) - set(perm))}",
                      flush=True)
    wall = time.time() - t0_global
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "n_orderings_tried": 6,
            "n_full_tours": len(full_tours),
            "rank3_small_d": 111.76}
    if full_tours:
        best = min(full_tours, key=lambda r: r["mk"])
        info["best_full_tour"] = {"ordering": best["ordering"],
                                  "mk": best["mk"],
                                  "exc_total": best["exc_total"]}
        x = best["all_times"] + best["all_tofs"] + \
            [float(p) for p in best["perm"]]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        info["fitness"] = list(f)
        info["feasible_by_fitness"] = feas
        if feas and f[0] < 142.99:
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["replaced_banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(search(inst), indent=2))
