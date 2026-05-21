"""Ch2 KTTSP — sub-tour insertion for large missing clusters.

Multi-cluster insert handles missing clusters ≤ 5 nodes by enumerating
insertion positions × orderings. For larger clusters (e.g., 20-node
missing cluster on medium instance), enumeration is infeasible
(20! orderings). Instead:

1. Use greedy_findxfer restricted to the missing-cluster nodes ONLY
   to build a feasible sub-tour. Try each cluster node as start.
2. For each candidate sub-tour (start, perm[s..e]), find an insertion
   position p in the partial perm where the bridge arcs
   partial[p-1] → s and e → partial[p] are feasible (cheap or
   exception). Allow exception arcs as bridge if budget permits.
3. Combine: partial[0..p-1] + subtour + partial[p..n].
4. Re-walk the combined perm; verify feasible.

Sub-tour exception arcs and bridge exceptions all draw from the same
n_exc budget, so we track total exception count carefully.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_findtransfer_greedy import (
    find_earliest_transfer, greedy_findxfer,
)
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def greedy_subtour(kt, nodes, start, tof_window=20.0, n_steps=200,
                   max_exc=2):
    """Greedy through `nodes` only (set), starting at `start`. Limits
    exception arcs to `max_exc`. Returns (perm, tof_chain, ok) where
    perm is the in-cluster sequence (no fixed t_start; pure
    relative-time)."""
    unvis = set(nodes) - {start}
    perm = [start]
    tof_chain = []
    dv_chain = []
    exc = 0
    t = 0.0  # relative time inside the sub-tour
    cur = start
    while unvis:
        best = None  # (arr, j, tof, dv, is_exc)
        for j in unvis:
            tof, dv = find_earliest_transfer(
                kt, cur, j, t, kt.dv_thr, tof_window, n_steps)
            if tof is not None:
                if best is None or t + tof < best[0]:
                    best = (t + tof, j, tof, dv, False)
        if best is None and exc < max_exc:
            for j in unvis:
                tof, dv = find_earliest_transfer(
                    kt, cur, j, t, kt.dv_exc, tof_window, n_steps)
                if tof is not None:
                    if best is None or t + tof < best[0]:
                        best = (t + tof, j, tof, dv, True)
        if best is None:
            return perm, tof_chain, dv_chain, exc, False
        _, j, tof, dv, is_exc = best
        perm.append(j)
        tof_chain.append(tof)
        dv_chain.append(dv)
        if is_exc:
            exc += 1
        t += tof
        cur = j
        unvis.discard(j)
    return perm, tof_chain, dv_chain, exc, True


def find_best_subtour(kt, cluster_nodes, max_exc=2):
    """Try each cluster node as start; return shortest feasible
    sub-tour by total ToF (minus start)."""
    best = None  # (total_tof, subtour, exc)
    for start in cluster_nodes:
        perm, tofs, dvs, exc, ok = greedy_subtour(
            kt, cluster_nodes, start, max_exc=max_exc)
        if not ok or len(perm) != len(cluster_nodes):
            continue
        total = sum(tofs)
        if best is None or total < best[0]:
            best = (total, perm, exc, tofs, dvs)
    return best


def find_all_subtours(kt, cluster_nodes, max_exc=2):
    """Try each cluster node as start; return ALL feasible sub-tours
    sorted by total ToF ascending."""
    results = []
    for start in cluster_nodes:
        perm, tofs, dvs, exc, ok = greedy_subtour(
            kt, cluster_nodes, start, max_exc=max_exc)
        if not ok or len(perm) != len(cluster_nodes):
            continue
        results.append((sum(tofs), perm, exc, tofs, dvs))
    results.sort(key=lambda r: r[0])
    return results


def try_insert_subtour(kt, partial, subtour, max_extra_exc=2,
                        verbose=False):
    """Try each insertion position p; for each, check bridge arcs
    feasibly. Returns (full_perm, times, tofs, mk, n_exc_total) for
    best position."""
    best = None
    for p in range(1, len(partial) + 1):
        cand = list(partial[:p]) + list(subtour) + list(partial[p:])
        # Walk the partial-with-subtour (length partial+subtour, NOT
        # necessarily kt.n; remaining small clusters get added after).
        times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
        if not ok or not times:
            continue
        # Verify n_exc not exceeded by this segment
        n_exc_total = 0
        for k in range(len(cand) - 1):
            dv = kt.compute_transfer(cand[k], cand[k + 1],
                                       times[k], tofs[k])
            if dv > kt.dv_thr:
                n_exc_total += 1
        if n_exc_total > kt.n_exc:
            if verbose:
                print(f"  p={p}: n_exc={n_exc_total} > {kt.n_exc}, skip",
                      flush=True)
            continue
        mk = times[-1] + tofs[-1]
        if best is None or mk < best[3]:
            best = (cand, times, tofs, mk, n_exc_total)
            if verbose:
                print(f"  p={p}: mk={mk:.3f}, n_exc={n_exc_total} ✓",
                      flush=True)
    return best


def main(in_partial="/tmp/medium_partial_s3h.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="medium"):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{problem}.kttsp")
    kt = KTTSP(inst)
    with open(in_partial) as fh:
        d = json.load(fh)
    partial = list(d["perm"])
    missing = list(d["missing"])
    print(f"Partial: {len(partial)}/{kt.n}, missing: {len(missing)}",
          flush=True)
    # Cluster the missing nodes (use the same routine)
    from esa_spoc_26.ch2_multi_cluster_insert import cluster_missing_nodes
    clusters = cluster_missing_nodes(kt, missing, thr_cheap=kt.dv_thr)
    clusters.sort(key=len, reverse=True)
    print(f"Clusters: {[len(c) for c in clusters]}", flush=True)
    # For the biggest cluster, build a sub-tour
    big = clusters[0]
    print(f"Big cluster ({len(big)}): {big}", flush=True)
    t0 = time.time()
    subs = find_all_subtours(kt, big, max_exc=2)
    if not subs:
        print("FAILED: no feasible sub-tour through big cluster",
              flush=True)
        return {"status": "no_subtour"}
    print(f"Found {len(subs)} feasible sub-tours "
          f"(best total_tof={subs[0][0]:.2f}d, "
          f"wall={time.time()-t0:.1f}s)", flush=True)
    # Try each sub-tour (in order of ascending total_tof), both as-is
    # and reversed. Take the best feasible insertion overall.
    res = None
    t0 = time.time()
    for si, (total, subperm, exc, tofs_sub, dvs_sub) in enumerate(subs):
        for variant_name, sp in (("fwd", subperm),
                                  ("rev", list(reversed(subperm)))):
            r = try_insert_subtour(kt, partial, sp, verbose=False)
            if r is not None:
                cand, times, tofs, mk, n_exc = r
                if res is None or mk < res[3]:
                    print(f"  sub {si} {variant_name} (start={sp[0]}, "
                          f"total={total:.2f}): mk={mk:.3f}, "
                          f"n_exc={n_exc} ✓", flush=True)
                    res = r
    print(f"Sub-tour insertion search wall={time.time()-t0:.1f}s",
          flush=True)
    if res is None:
        print("FAILED: no feasible insertion of any sub-tour",
              flush=True)
        return {"status": "no_insert"}
    cand, times, tofs, mk, n_exc = res
    print(f"Sub-tour inserted: mk={mk:.3f} (partial now {len(cand)}/{kt.n}), "
          f"n_exc={n_exc}, wall={time.time()-t0:.1f}s", flush=True)
    # If small clusters / singletons remain, greedy-fill via existing
    in_perm = set(cand)
    remaining = sorted(set(range(kt.n)) - in_perm)
    print(f"Remaining unvisited: {len(remaining)}: {remaining}",
          flush=True)
    from esa_spoc_26.ch2_multi_cluster_insert import (
        insert_cluster, greedy_insert_node)
    cur_perm = list(cand)
    cur_times = times
    cur_tofs = tofs
    # Insert small clusters
    for ci in range(1, len(clusters)):
        c = clusters[ci]
        c = [v for v in c if v not in set(cur_perm)]
        if not c:
            continue
        if len(c) <= 5:
            r = insert_cluster(kt, cur_perm, c)
            if r is not None:
                mk_c, new_perm, new_times, new_tofs = r
                cur_perm = new_perm
                cur_times = new_times
                cur_tofs = new_tofs
                print(f"  Cluster {c}: mk={mk_c:.3f}", flush=True)
        else:
            # Greedy-fill node by node
            for v in c:
                if v in set(cur_perm):
                    continue
                r = greedy_insert_node(kt, cur_perm, v)
                if r is not None:
                    mk_c, new_perm, new_times, new_tofs = r
                    cur_perm = new_perm
                    cur_times = new_times
                    cur_tofs = new_tofs
                    print(f"  Node {v}: mk={mk_c:.3f}", flush=True)
    # Final feasibility check
    if len(cur_perm) != kt.n:
        print(f"Final perm length {len(cur_perm)} != {kt.n}: incomplete",
              flush=True)
        return {"status": "incomplete", "len": len(cur_perm)}
    x = cur_times + cur_tofs + [float(v) for v in cur_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    print(f"FINAL: mk={f[0]:.4f}, fitness={list(f)}, feas={feas}",
          flush=True)
    info = {"problem": problem, "n": kt.n,
            "mk": float(f[0]), "feasible": feas,
            "fitness": [float(v) for v in f]}
    if feas:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
        print(f"BANKED: {p}", flush=True)
    return info


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
