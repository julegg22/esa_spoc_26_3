"""Ch2 KTTSP — three-small-cluster arrangement enumeration.

Critical structural insight (ultrathink 2026-05-21): the 142.99 d
banked perm uses a specific cluster arrangement:
  retrograde-START → big-1 → polar-MID → big-2 → equatorial-END

This is ONE of 6 possible (start, mid, end) cluster orderings × 6³ =
216 internal-orderings = 1296 total structures. The other 1295
are untested.

Per O-007:
- Retrograde cluster (i≈π): nodes {18, 23, 34}
- Polar cluster   (i≈π/2): nodes {4, 11, 17}
- Equatorial cluster (i≈0): nodes {16, 27, 32}

Each cluster is traversed via 2 cheap internal arcs (Δv ~ 17–96 m/s).
The bridges in/out are 500–600 m/s exceptions:
- START cluster: NO in-bridge (depot→start is free), 1 out-bridge
- MID cluster: 1 in-bridge + 1 out-bridge
- END cluster: 1 in-bridge, NO out-bridge (path ends there)
Total: 4 cluster-bridges; 5th exception spare for big-cluster.

Algorithm:
1. For each cluster-arrangement (start, mid, end) — 6 options
2. For each internal-ordering of each cluster — 6³ options
3. Build forced opener (start-cluster traversal), invoke greedy
   through big nodes, force mid-cluster insertion, continue greedy,
   force end-cluster as last 3 nodes
4. Walk chronologically, evaluate via official fitness, bank best
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

RETROGRADE = (18, 23, 34)   # i ≈ π
POLAR = (4, 11, 17)         # i ≈ π/2
EQUATORIAL = (16, 27, 32)   # i ≈ 0
ALL_SMALL = set(RETROGRADE + POLAR + EQUATORIAL)
CLUSTERS = {"R": RETROGRADE, "P": POLAR, "E": EQUATORIAL}


def greedy_through_big(kt, perm_prefix, target_set, forbidden_set,
                       end_cluster, tof_window=12.0, n_steps=120,
                       wait_steps=4, wait_dt=0.5):
    """Greedy from end of perm_prefix to visit `target_set` nodes
    (big-cluster nodes excluding forbidden small-cluster nodes that
    aren't yet to be visited). Stops when target_set exhausted or no
    more feasible move.

    Returns (perm, times, tofs, dvs, exc_used, ok).
    """
    perm = list(perm_prefix)
    cur = perm[-1]
    # Use existing times/tofs from prefix; rebuild them via walk
    times_pre, tofs_pre, _, ok_pre, exc_pre, _ = walk_perm_chrono(
        kt, perm, tof_window=tof_window, n_steps=n_steps)
    if not ok_pre or not times_pre:
        return perm, [], [], [], 0, False
    t = times_pre[-1] + tofs_pre[-1]
    exc = exc_pre
    unvis = set(target_set)
    times = list(times_pre)
    tofs = list(tofs_pre)
    dvs = []
    while unvis:
        best = None  # (arr, j, tof, dv, is_exc)
        for j in unvis:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                              tof_window, n_steps)
            if tof is not None:
                arr = t + tof
                if best is None or arr < best[0]:
                    best = (arr, j, tof, dv, False)
        if best is None and exc < kt.n_exc:
            for j in unvis:
                tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                                  tof_window, n_steps)
                if tof is not None:
                    arr = t + tof
                    if best is None or arr < best[0]:
                        best = (arr, j, tof, dv, True)
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
                        t = t_try
                        best = (t + tof, j, tof, dv, False)
                        break
                if best is not None:
                    break
        if best is None:
            return perm, times, tofs, dvs, exc, False
        arr, j, tof, dv, is_exc = best
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        perm.append(j)
        if is_exc:
            exc += 1
        t = arr
        unvis.discard(j)
        cur = j
    return perm, times, tofs, dvs, exc, True


def evaluate_arrangement(kt, start_cluster, mid_cluster, end_cluster,
                         start_order, mid_order, end_order):
    """Build perm:
       <start_cluster in start_order> → greedy(big - end_cluster) →
       <forced mid-cluster insert in mid_order> → greedy(rest) →
       <end_cluster in end_order>

    Strategy: forced opener; greedy through big-cluster until enough
    progress; cluster-insert mid; continue greedy; close with
    end-cluster prefix.
    Returns (mk, perm, x, fitness) or (None, None, None, None) on
    infeasibility.
    """
    n = kt.n
    big_nodes = [v for v in range(n) if v not in ALL_SMALL]
    # Build forced START opener via walk_perm_chrono of start_order
    perm_open = list(start_order)
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, perm_open)
    if not ok or not times:
        return None, None, None, None
    # All non-end-cluster big nodes
    big_target = set(big_nodes)
    # Greedy through ALL big nodes first (we'll re-arrange to insert
    # mid-cluster in best position later via a 2-pass approach).
    full, _t_full, _tof_full, _dv_full, _exc, full_ok = greedy_through_big(
        kt, perm_open, big_target, ALL_SMALL,
        end_cluster=end_cluster)
    if not full_ok:
        return None, None, None, None
    # Now `full` is start_cluster + all big in greedy order.
    # Try to INSERT mid_cluster (in mid_order) at each interior position
    # AND END_cluster (in end_order) at the END. Brute enumerate
    # insertion positions for mid_cluster.
    best = None  # (mk, perm, times, tofs)
    # `full` = perm_open + greedy_visited_big. Mid + end go after.
    # Try inserting mid_order at each position p in [len(perm_open),
    # len(full) + 1] inclusive, end-cluster always at the end.
    p_lo = len(perm_open)
    p_hi = len(full) + 1  # before end-cluster start
    for p in range(p_lo, p_hi):
        cand = list(full[:p]) + list(mid_order) + list(full[p:]) + \
            list(end_order)
        if len(cand) != n or len(set(cand)) != n:
            continue
        times, tofs, _, ok, _exc_post, _ = walk_perm_chrono(kt, cand)
        if not ok or not times:
            continue
        x = times + tofs + [float(v) for v in cand]
        f = kt.fitness(x)
        if kt.is_feasible(f):
            mk = float(f[0])
            if best is None or mk < best[0]:
                best = (mk, cand, times, tofs, list(f))
    return best


def sweep(inst, problem="small", verbose=True,
          out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    n = kt.n
    cluster_names = list(CLUSTERS.keys())   # R, P, E
    best_overall = None
    t_overall = time.time()
    # 6 cluster arrangements
    for arr in itertools.permutations(cluster_names):
        start_c, mid_c, end_c = arr
        start_nodes = CLUSTERS[start_c]
        mid_nodes = CLUSTERS[mid_c]
        end_nodes = CLUSTERS[end_c]
        # 6 × 6 × 6 internal orderings = 216 per arrangement
        for so in itertools.permutations(start_nodes):
            for mo in itertools.permutations(mid_nodes):
                for eo in itertools.permutations(end_nodes):
                    result = evaluate_arrangement(
                        kt, start_c, mid_c, end_c, so, mo, eo)
                    if result is None or result[0] is None:
                        continue
                    mk, perm, times, tofs, fitness = result
                    if best_overall is None or mk < best_overall[0]:
                        best_overall = (mk, perm, times, tofs, fitness,
                                        arr, so, mo, eo)
                        if verbose:
                            print(f"  {arr} so={so} mo={mo} eo={eo}: "
                                  f"mk={mk:.3f}", flush=True)
    wall = time.time() - t_overall
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "rank3_small_d": 111.76}
    if best_overall is None:
        info["feasible"] = False
        return info
    mk, perm, times, tofs, f, arr, so, mo, eo = best_overall
    info.update({
        "best_mk": float(mk),
        "arr": list(arr), "so": list(so), "mo": list(mo), "eo": list(eo),
        "perm": [int(p) for p in perm],
        "fitness": list(f),
    })
    if mk < 142.99:
        x = times + tofs + [float(p) for p in perm]
        p_path = Path(out) / f"{problem}.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        p_path.write_text(json.dumps([{"decisionVector": list(x),
                                       "problem": problem,
                                       "challenge": CHALLENGE}]))
        info["banked"] = str(p_path)
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(sweep(inst), indent=2))
