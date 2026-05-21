"""Ch2 KTTSP — fast sub-tour insertion via bridge-feasibility prefilter.

Naïve sub-tour insertion (ch2_subtour_insert) walks the entire
176-node candidate for each of ~6000 (subtour × direction × position)
configurations — too slow (~6h).

Optimization: most candidates fail because the bridge arc
`partial[p-1] → subtour[0]` at time t_p is infeasible. Pre-cache
the partial-perm walk (one pass), then check only the bridge arc
for each candidate. Run the full walk ONLY for candidates whose
bridge passes. Reduces 6000 walks to ~6000 bridge-checks +
≤100 full walks.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_subtour_insert import find_all_subtours


def prewalk_partial(kt, partial):
    """Walk the partial perm; return (cum_times, cum_tofs). Caller
    uses cum_times[p-1] + cum_tofs[p-1] as t_ready BEFORE partial[p].
    cum_times[k] = absolute departure time of leg k = visit time of
    partial[k]."""
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, partial)
    if not ok or not times:
        return None
    # cum_times[k] = time AT partial[k+1] (= times[k] + tofs[k])
    # times[k] = td of leg k (from partial[k] to partial[k+1])
    # tofs[k] = tof of leg k
    return list(times), list(tofs)


def fast_insert_subtour(kt, partial, partial_times, partial_tofs,
                         subtour, dv_thr_cap=None, tof_window=20.0,
                         n_steps=200, verbose=False):
    """For each position p (insert subtour BEFORE partial[p]), check
    bridge feasibility:
      partial[p-1] → subtour[0]   at  t = visit_time_of_partial[p-1] + 0
    If bridge feasible (cheap or exc), do full walk of
    partial[:p] + subtour + partial[p:]. Return best feasible
    candidate (cand, times, tofs, mk, n_exc) or None."""
    if dv_thr_cap is None:
        dv_thr_cap = kt.dv_exc
    best = None
    bridge_passed = 0
    candidates_walked = 0
    for p in range(1, len(partial) + 1):
        # The bridge leg starts at the visit time of partial[p-1]:
        # partial_times[p-2] + partial_tofs[p-2] for p >= 2.
        # For p=1, the bridge starts at t=0 (after partial[0]).
        if p == 1:
            t_bridge = 0.0  # partial[0] is visited at t=0
        else:
            t_bridge = partial_times[p - 2] + partial_tofs[p - 2]
        # Try cheap bridge first
        tof_b, dv_b = find_earliest_transfer(
            kt, partial[p - 1], subtour[0], t_bridge, kt.dv_thr,
            tof_window, n_steps)
        if tof_b is None:
            # Try exception
            tof_b, dv_b = find_earliest_transfer(
                kt, partial[p - 1], subtour[0], t_bridge, kt.dv_exc,
                tof_window, n_steps)
            if tof_b is None:
                continue
        bridge_passed += 1
        # Bridge feasible at SOME tof; do full walk to verify total
        # feasibility and get the mk
        cand = list(partial[:p]) + list(subtour) + list(partial[p:])
        times, tofs, _, ok, _, _ = walk_perm_chrono(kt, cand)
        candidates_walked += 1
        if not ok or not times:
            continue
        # Check n_exc budget
        n_exc_total = 0
        for k in range(len(cand) - 1):
            dv = kt.compute_transfer(cand[k], cand[k + 1],
                                       times[k], tofs[k])
            if dv > kt.dv_thr:
                n_exc_total += 1
        if n_exc_total > kt.n_exc:
            continue
        mk = times[-1] + tofs[-1]
        if best is None or mk < best[3]:
            best = (cand, times, tofs, mk, n_exc_total)
            if verbose:
                print(f"  p={p} (after node {partial[p-1]}, "
                      f"t_bridge={t_bridge:.2f}): mk={mk:.3f}, "
                      f"n_exc={n_exc_total} ✓", flush=True)
    if verbose:
        print(f"  bridges passed={bridge_passed}, walked={candidates_walked}",
              flush=True)
    return best


def main(in_partial="/tmp/medium_partial_s3h.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="medium", max_subs=5):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{problem}.kttsp")
    kt = KTTSP(inst)
    with open(in_partial) as fh:
        d = json.load(fh)
    partial = list(d["perm"])
    missing = list(d["missing"])
    print(f"Partial: {len(partial)}/{kt.n}, missing: {len(missing)}",
          flush=True)

    from esa_spoc_26.ch2_multi_cluster_insert import cluster_missing_nodes
    clusters = cluster_missing_nodes(kt, missing, thr_cheap=kt.dv_thr)
    clusters.sort(key=len, reverse=True)
    print(f"Clusters: {[len(c) for c in clusters]}", flush=True)

    # Iterate over all BIG clusters (len > 5): insert each one via
    # sub-tour. After each insertion, partial grows; re-prewalk.
    cur_perm = list(partial)
    cur_times = None
    cur_tofs = None
    big_clusters = [c for c in clusters if len(c) > 5]
    small_clusters = [c for c in clusters if len(c) <= 5]
    print(f"Big clusters: {[len(c) for c in big_clusters]}, "
          f"small: {[len(c) for c in small_clusters]}", flush=True)
    for big_idx, big in enumerate(big_clusters):
        print(f"\n=== BIG CLUSTER {big_idx + 1}/{len(big_clusters)} "
              f"({len(big)} nodes) ===", flush=True)
        t0 = time.time()
        subs = find_all_subtours(kt, big, max_exc=2)
        if not subs:
            print(f"FAILED: no sub-tour for big cluster {big_idx}",
                  flush=True)
            return {"status": "no_subtour", "big_idx": big_idx}
        print(f"  Found {len(subs)} sub-tours; using top {max_subs} "
              f"(wall={time.time()-t0:.1f}s)", flush=True)
        pw = prewalk_partial(kt, cur_perm)
        if pw is None:
            print(f"FAILED: cur_perm not walkable at big {big_idx}",
                  flush=True)
            return {"status": "partial_unwalkable", "big_idx": big_idx}
        p_times, p_tofs = pw
        # Search
        res = None
        t0 = time.time()
        for si, (total, subperm, exc, tofs_sub, dvs_sub) in \
                enumerate(subs[:max_subs]):
            for direction, sp in (("fwd", subperm),
                                   ("rev", list(reversed(subperm)))):
                r = fast_insert_subtour(kt, cur_perm, p_times, p_tofs,
                                         sp, verbose=False)
                if r is not None:
                    cand, times, tofs, mk, n_exc = r
                    if res is None or mk < res[3]:
                        print(f"  sub {si} {direction} "
                              f"(start={sp[0]}, total={total:.2f}): "
                              f"mk={mk:.3f}, n_exc={n_exc} ✓",
                              flush=True)
                        res = r
        print(f"  Search wall={time.time()-t0:.1f}s", flush=True)
        if res is None:
            print(f"FAILED: no feasible sub-tour insertion for big "
                  f"{big_idx}", flush=True)
            return {"status": "no_insert", "big_idx": big_idx}
        cand, times, tofs, mk, n_exc = res
        cur_perm = list(cand)
        cur_times = times
        cur_tofs = tofs
        print(f"  After big {big_idx}: n={len(cur_perm)}/{kt.n}, "
              f"mk={mk:.3f}, n_exc={n_exc}", flush=True)

    # Now process small clusters
    print(f"\n=== SMALL CLUSTERS ({len(small_clusters)}) ===", flush=True)
    in_perm = set(cur_perm)
    remaining_clusters = []
    for c in small_clusters:
        c = [v for v in c if v not in in_perm]
        if c:
            remaining_clusters.append(c)
    print(f"Remaining clusters to insert: "
          f"{[len(c) for c in remaining_clusters]}", flush=True)
    from esa_spoc_26.ch2_multi_cluster_insert import (
        insert_cluster, greedy_insert_node)
    cur_perm = list(cand)
    cur_times = times
    cur_tofs = tofs
    for c in remaining_clusters:
        if len(c) <= 5:
            r = insert_cluster(kt, cur_perm, c)
            if r is not None:
                mk_c, new_perm, new_times, new_tofs = r
                cur_perm = new_perm
                cur_times = new_times
                cur_tofs = new_tofs
                print(f"  Cluster {c}: mk={mk_c:.3f}", flush=True)
            else:
                print(f"  Cluster {c}: NO INSERT", flush=True)
        else:
            for v in c:
                if v not in set(cur_perm):
                    r = greedy_insert_node(kt, cur_perm, v)
                    if r is not None:
                        mk_c, new_perm, new_times, new_tofs = r
                        cur_perm = new_perm
                        cur_times = new_times
                        cur_tofs = new_tofs
                        print(f"  Node {v}: mk={mk_c:.3f}", flush=True)
    # Final result
    if len(cur_perm) != kt.n:
        print(f"INCOMPLETE: {len(cur_perm)}/{kt.n}", flush=True)
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
    ms = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(json.dumps(main(max_subs=ms), indent=2))
