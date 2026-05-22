"""Ch2 KTTSP large (n=1051) — hierarchical orbital-element decomposition.

Orthogonal angle missed in S-2026-05-21: the n=1051 instance is
intractable for any single-greedy approach (5860s for 14% coverage
at n_exc=0). The structure is exploitable: 1051 orbits cluster
naturally into orbit families on (a, e, i, RAAN, ω) similarity.
Within a cluster, transfers are cheap; between clusters, sometimes
expensive. With n_exc=5 budget, we need most cluster-to-cluster
transitions to be cheap.

Pipeline:
1. Extract orbital_elements for all n nodes. Skip mean anomaly (M),
   which is phase, not orbit-family identity.
2. K-means cluster on normalised (a, e, sin(i)*cos(RAAN),
   sin(i)*sin(RAAN), ω) — the standard orbital-family metric.
3. For each cluster k, build a greedy sub-tour through cluster
   members at relative time 0. Allow 0 internal exceptions.
4. Build a meta-graph: each "supernode" = one cluster, characterised
   by ENTRY node and EXIT node of its sub-tour. Try multiple
   (entry, exit) candidates per cluster.
5. Apply greedy_findxfer at the supernode level over (entry, exit)
   pairs, picking the best feasible meta-route within n_exc budget.
6. Stitch all sub-tours via the meta-route. Run walk_perm_chrono +
   fitness check.

If feasible, bank.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

from esa_spoc_26.ch2_findtransfer_greedy import (
    find_earliest_transfer,
)
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def extract_features(kt):
    """Return (n, 5) array of orbital-family features for clustering.
    Features: [a_norm, e, sin(i)*cos(RAAN), sin(i)*sin(RAAN),
    ω_normalised]."""
    feats = []
    for i in range(kt.n):
        a, e, inc, raan, w, M = kt.tom[i].orbital_elements
        feats.append([
            a,
            e,
            np.sin(inc) * np.cos(raan),
            np.sin(inc) * np.sin(raan),
            np.cos(w),  # ω cyclic; project to [-1,1]
        ])
    feats = np.array(feats)
    # Normalize each column to [0, 1] for k-means stability
    for j in range(feats.shape[1]):
        col = feats[:, j]
        lo, hi = col.min(), col.max()
        if hi - lo > 1e-9:
            feats[:, j] = (col - lo) / (hi - lo)
    return feats


def cluster_nodes(feats, k_clusters):
    """K-means cluster the orbital-element features."""
    km = KMeans(n_clusters=k_clusters, n_init=10, random_state=0)
    labels = km.fit_predict(feats)
    return labels


def greedy_subtour_only(kt, nodes, start, tof_window=20.0, n_steps=120,
                         max_exc=1, t_start=0.0):
    """Greedy sub-tour through `nodes` (subset of {0..n-1}) starting
    at `start` and absolute start time `t_start`. Pure cheap
    transfers if max_exc=0; allows up to max_exc exception arcs.
    Returns (perm, tofs, dvs, ok) — perm absolute, tofs relative."""
    unvis = set(nodes) - {start}
    perm = [start]
    tofs = []
    dvs = []
    exc = 0
    t = t_start
    cur = start
    while unvis:
        best = None
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
            return perm, tofs, dvs, False
        _, j, tof, dv, is_exc = best
        perm.append(j)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t += tof
        cur = j
        unvis.discard(j)
    return perm, tofs, dvs, True


def build_cluster_subtours(kt, labels, k_clusters, max_starts=4,
                            n_time_scans=8, max_exc_internal=1):
    """For each cluster, scan multiple start nodes AND multiple start
    times (cluster phase rotates with orbital period). Keep the
    feasible sub-tour with most coverage / shortest total_tof.
    Returns dict {k: {nodes, covered, total_tof, perm, tofs, dvs,
    t_start}}."""
    subtours = {}
    time_grid = np.linspace(0, kt.max_time * 0.9, n_time_scans)
    for k in range(k_clusters):
        cluster_nodes_k = [i for i in range(kt.n) if labels[i] == k]
        if not cluster_nodes_k:
            continue
        best = None  # (covered, total_tof, perm, tofs, dvs, t_start)
        starts = cluster_nodes_k[:max_starts]
        for t0 in time_grid:
            for start in starts:
                perm, tofs, dvs, ok = greedy_subtour_only(
                    kt, cluster_nodes_k, start,
                    max_exc=max_exc_internal, t_start=float(t0))
                covered = len(perm)
                total_tof = sum(tofs)
                if best is None or covered > best[0] or (
                        covered == best[0] and total_tof < best[1]):
                    best = (covered, total_tof, perm, tofs, dvs,
                            float(t0))
                if covered == len(cluster_nodes_k):
                    break  # fully covered, move to next start
            if best is not None and best[0] == len(cluster_nodes_k):
                break  # fully covered, move to next cluster
        if best is not None:
            subtours[k] = {
                "nodes": cluster_nodes_k,
                "covered": best[0],
                "total_tof": best[1],
                "perm": best[2],
                "tofs": best[3],
                "dvs": best[4],
                "t_start": best[5],
            }
    return subtours


def meta_route(kt, subtours, n_exc_meta=5, tof_window=20.0, n_steps=120):
    """Greedy at the supernode level: each supernode = a cluster
    sub-tour. Transition cost = transfer from exit_k → entry_{k+1}
    at current time. We track absolute time; the sub-tour appends
    its internal tofs after each meta-transition."""
    cluster_ids = list(subtours.keys())
    if not cluster_ids:
        return None
    # Pick best starting cluster: smallest mean semi-major axis
    # (closer to Earth = easier to start). For now, just first.
    start_k = cluster_ids[0]
    visited_k = {start_k}
    full_perm = list(subtours[start_k]["perm"])
    full_times = [0.0]  # td of each leg
    full_tofs = list(subtours[start_k]["tofs"])
    # Build cumulative times for the first sub-tour
    t = 0.0
    for i, tof in enumerate(subtours[start_k]["tofs"]):
        full_times.append(full_times[-1] + tof if i > 0 else 0.0 + 0)
    # Restart properly: walk the cluster to fix times
    times, tofs, _, ok, _, _ = walk_perm_chrono(kt, full_perm)
    if not ok:
        print(f"  meta_route start_k={start_k} unwalkable", flush=True)
        return None
    full_times = list(times)
    full_tofs = list(tofs)
    cur = full_perm[-1]
    t_cur = full_times[-1] + full_tofs[-1] if full_tofs else 0.0
    exc_used = 0
    while len(visited_k) < len(cluster_ids):
        # Pick next cluster with cheapest entry from cur at t_cur
        best = None  # (arr, k, entry, tof, dv, is_exc)
        for k in cluster_ids:
            if k in visited_k:
                continue
            entry = subtours[k]["perm"][0]
            tof, dv = find_earliest_transfer(
                kt, cur, entry, t_cur, kt.dv_thr, tof_window, n_steps)
            if tof is not None:
                if best is None or t_cur + tof < best[0]:
                    best = (t_cur + tof, k, entry, tof, dv, False)
        if best is None and exc_used < n_exc_meta:
            for k in cluster_ids:
                if k in visited_k:
                    continue
                entry = subtours[k]["perm"][0]
                tof, dv = find_earliest_transfer(
                    kt, cur, entry, t_cur, kt.dv_exc, tof_window, n_steps)
                if tof is not None:
                    if best is None or t_cur + tof < best[0]:
                        best = (t_cur + tof, k, entry, tof, dv, True)
        if best is None:
            print(f"  meta_route stalled at {len(visited_k)} clusters",
                  flush=True)
            return None
        arr, k, entry, tof, dv, is_exc = best
        # Append cluster k's sub-tour
        sub_perm = subtours[k]["perm"]
        # Add the bridge leg
        full_perm.extend(sub_perm)
        # Times need re-walk; do it incrementally
        # Re-walk the whole perm to get correct chronology
        times, tofs, _, ok, _, _ = walk_perm_chrono(kt, full_perm)
        if not ok or not times:
            print(f"  meta_route walk fail after cluster {k}",
                  flush=True)
            return None
        full_times = list(times)
        full_tofs = list(tofs)
        # Count actual excs in the perm
        n_exc_actual = 0
        for i in range(len(full_perm) - 1):
            dv_i = kt.compute_transfer(full_perm[i], full_perm[i + 1],
                                         full_times[i], full_tofs[i])
            if dv_i > kt.dv_thr:
                n_exc_actual += 1
        if n_exc_actual > kt.n_exc:
            print(f"  meta_route: n_exc={n_exc_actual} > {kt.n_exc} "
                  f"after cluster {k}", flush=True)
            return None
        exc_used = n_exc_actual
        visited_k.add(k)
        cur = full_perm[-1]
        t_cur = full_times[-1] + full_tofs[-1] if full_tofs else t_cur
        print(f"  added cluster {k} ({len(sub_perm)} nodes), "
              f"perm={len(full_perm)}/{kt.n}, n_exc={n_exc_actual}, "
              f"t_cur={t_cur:.1f}d, exc_bridge={is_exc}",
              flush=True)
        if t_cur > kt.max_time:
            print(f"  meta_route: time overrun", flush=True)
            return None
    return full_perm, full_times, full_tofs


def main(out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="large", k_clusters=50):
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "hard"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
    kt = KTTSP(inst)
    print(f"Hierarchical large: n={kt.n}, k_clusters={k_clusters}",
          flush=True)
    # Step 1-2: cluster
    t0 = time.time()
    feats = extract_features(kt)
    labels = cluster_nodes(feats, k_clusters)
    print(f"Clustering: {time.time()-t0:.1f}s, sizes="
          f"{sorted([(labels==k).sum() for k in range(k_clusters)], reverse=True)[:10]}...",
          flush=True)
    # Step 3: per-cluster sub-tours
    t0 = time.time()
    subtours = build_cluster_subtours(kt, labels, k_clusters,
                                        max_starts=3)
    full_cov = sum(1 for k, st in subtours.items()
                    if st["covered"] == (labels == k).sum())
    print(f"Sub-tours: {len(subtours)} built, {full_cov} fully cover "
          f"their cluster ({time.time()-t0:.1f}s)", flush=True)
    # Use ALL subtours (full or partial); we'll handle truly-missing
    # at the end with time-limited insertion
    full_subtours = subtours
    nodes_covered = set()
    for st in full_subtours.values():
        nodes_covered |= set(st["perm"])
    n_missed = kt.n - len(nodes_covered)
    print(f"  Total perm-covered: {len(nodes_covered)} ({n_missed} truly missing)",
          flush=True)
    # Step 4-5: meta route
    t0 = time.time()
    result = meta_route(kt, full_subtours)
    print(f"Meta-route: {time.time()-t0:.1f}s", flush=True)
    if result is None:
        return {"status": "no_meta_route", "n_clusters": len(full_subtours)}
    full_perm, full_times, full_tofs = result
    print(f"Result: perm={len(full_perm)}/{kt.n}", flush=True)
    if len(full_perm) != kt.n:
        missing = sorted(set(range(kt.n)) - set(full_perm))
        print(f"  INCOMPLETE: {len(missing)} missing nodes",
              flush=True)
        # Report partial state, save for inspection, but do NOT
        # attempt 900+ single-node insertions (would take days).
        with open("/tmp/large_hierarchical_partial.json", "w") as f:
            json.dump({
                "perm": list(full_perm), "times": list(full_times),
                "tofs": list(full_tofs), "missing": list(missing),
                "n_clusters_used": len(full_subtours),
            }, f)
        print(f"  Partial state saved to /tmp/large_hierarchical_partial.json",
              flush=True)
        return {"status": "incomplete",
                "covered": len(full_perm), "n": kt.n,
                "missing": len(missing),
                "mk_partial": float(full_times[-1] + full_tofs[-1])
                if full_tofs else 0.0}
    x = full_times + full_tofs + [float(v) for v in full_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    print(f"FINAL: mk={f[0]:.4f}, feas={feas}, fitness={list(f)}",
          flush=True)
    info = {"problem": problem, "n": kt.n,
            "k_clusters": k_clusters,
            "mk": float(f[0]), "feasible": feas}
    if feas:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
        print(f"BANKED: {p}", flush=True)
    return info


if __name__ == "__main__":
    kc = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    print(json.dumps(main(k_clusters=kc), indent=2))
