"""E-556 — Ch2 large (n=1051): component-aware feasible first solution.

Recipe that banked MEDIUM, transferred to LARGE:
  The CHEAP-transfer graph of `large` has exactly 4 connected components
  of sizes [601, 150, 150, 150] (from E-533 adjacency dump). Bridging 4
  components needs only ~3 inter-component exc transitions — which FITS
  inside the kt.n_exc=5 budget (leaving ~2 exc for intra-component needs).

  E-555 FAILED by k-means clustering into k=50 clusters: bridging 50
  clusters needs up to 49 exc bridges but only 5 are allowed. The
  4-natural-component decomposition is the correct unit.

Pipeline:
  1. Load the 4 cheap-graph components from /tmp/ch2_e533_large_adj.npz
     (reuse E-537's component extraction).
  2. For EACH component, build a TIME-FEASIBLE greedy sub-tour via
     greedy_subtour_only (reused from ch2_hierarchical_large). Single
     start for the 601-comp; a few (start,t0) seeds for the three
     150-comps. Small intra exc budget so coverage is high.
  3. Choose a component ORDER (4 supernodes → only 3 bridges) by
     scanning exit→entry transfers between consecutive comps; prefer the
     order using fewest exc bridges.
  4. Concatenate the 4 sub-tours in that order → full permutation.
  5. Authoritative check: walk_perm_chrono re-walks the whole perm and
     enforces the global exc budget itself; then kt.fitness/is_feasible.
  6. SAFE BANK: write solutions/upload/large.json ONLY if feas AND all
     1051 nodes covered. Otherwise /tmp/large_component_partial.json,
     bank nothing. Back up any existing large.json first.

Smoke modes:
  --check : import + argparse sanity, exit before any KTTSP load.
  --probe : time ONE greedy_subtour_only on a 150-comp (+ a truncated
            601-comp probe) to estimate full-construction wall cost.
  (default / --full) : full construction + walk + safe bank.

Deps: PYTHONPATH=src ; env python micromamba/envs/spoc26.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_hierarchical_large import greedy_subtour_only
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

sys.stdout.reconfigure(line_buffering=True)

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ_FILE = "/tmp/ch2_e533_large_adj.npz"
OUT = f"{ROOT}/solutions/upload/large.json"
PARTIAL = "/tmp/large_component_partial.json"


def load_components(adj_file):
    """Return components as lists of GLOBAL node ids, sorted desc by size
    (mirrors E-537 extraction). comp_sizes should be [601,150,150,150]."""
    d = np.load(adj_file)
    labels = d['labels']
    n_comps = int(labels.max()) + 1
    comps = [[] for _ in range(n_comps)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps


def build_component_subtour(kt, comp, seeds, max_exc_internal):
    """Build the best-coverage time-feasible greedy sub-tour for one
    component over the given (start, t_start) seeds. Returns dict with
    perm/tofs/dvs/covered/t_start/full(bool). `seeds` is a list of
    (start_node, t_start)."""
    best = None  # (covered, total_tof, perm, tofs, dvs, t_start)
    target = len(comp)
    for (start, t0) in seeds:
        perm, tofs, dvs, ok = greedy_subtour_only(
            kt, comp, start, max_exc=max_exc_internal, t_start=float(t0))
        covered = len(perm)
        total_tof = float(sum(tofs))
        if (best is None or covered > best[0]
                or (covered == best[0] and total_tof < best[1])):
            best = (covered, total_tof, perm, tofs, dvs, float(t0))
        if covered == target:
            break  # fully covered; no need for more seeds
    covered, total_tof, perm, tofs, dvs, t0 = best
    return {
        "perm": perm, "tofs": tofs, "dvs": dvs,
        "covered": covered, "size": target,
        "total_tof": total_tof, "t_start": t0,
        "full": covered == target,
    }


def order_components(kt, subtours, tof_window=20.0, n_steps=120):
    """Greedily order the (few) component sub-tours to minimise the number
    of EXC bridges between consecutive comps. Start from comp0 (the 601
    big component) since it anchors most of the tour. At each step try a
    CHEAP exit->entry transfer first, falling back to EXC. Returns the
    list of component indices in chosen visit order and the count of exc
    bridges used at the supernode level (an estimate; the authoritative
    count comes from walk_perm_chrono)."""
    ncomp = len(subtours)
    order = [0]
    remaining = set(range(1, ncomp))
    exc_bridges = 0
    # absolute time after finishing comp0: walk it to get the real time
    cur = subtours[0]["perm"][-1]
    # approximate current time as t_start + sum(tofs) of comp0
    t_cur = subtours[0]["t_start"] + float(sum(subtours[0]["tofs"]))
    while remaining:
        cand = None  # (is_exc, arr, k)
        # cheap first across all remaining entries
        for k in sorted(remaining):
            entry = subtours[k]["perm"][0]
            tof, _ = find_earliest_transfer(
                kt, cur, entry, t_cur, kt.dv_thr, tof_window, n_steps)
            if tof is not None:
                arr = t_cur + tof
                if cand is None or arr < cand[1]:
                    cand = (False, arr, k)
        if cand is None:
            for k in sorted(remaining):
                entry = subtours[k]["perm"][0]
                tof, _ = find_earliest_transfer(
                    kt, cur, entry, t_cur, kt.dv_exc, tof_window, n_steps)
                if tof is not None:
                    arr = t_cur + tof
                    if cand is None or arr < cand[1]:
                        cand = (True, arr, k)
        if cand is None:
            # no transfer at all from cur — fall back to size order
            for k in sorted(remaining):
                order.append(k)
                remaining.discard(k)
            break
        is_exc, arr, k = cand
        if is_exc:
            exc_bridges += 1
        order.append(k)
        remaining.discard(k)
        cur = subtours[k]["perm"][-1]
        t_cur = arr + float(sum(subtours[k]["tofs"]))
    return order, exc_bridges


def make_seeds(comp, t_grid, max_starts):
    """(start, t_start) seed list: max_starts start nodes x t_grid."""
    starts = comp[:max_starts]
    return [(s, t0) for t0 in t_grid for s in starts]


def run_probe(kt, comps):
    """Tractability probe: time one greedy_subtour_only on a 150-comp and
    a truncated 601-comp, extrapolate the full per-construction cost."""
    small = min(comps, key=len)
    big = max(comps, key=len)
    print(f"PROBE: small comp size {len(small)}, big comp size {len(big)}",
          flush=True)

    t0 = time.time()
    perm, tofs, dvs, ok = greedy_subtour_only(
        kt, small, small[0], max_exc=1, t_start=0.0)
    dt_small = time.time() - t0
    print(f"PROBE 150-comp: {dt_small:.1f}s, covered={len(perm)}/{len(small)}, "
          f"ok={ok}", flush=True)

    # Truncated 601 probe: build a sub-tour over the first 150 nodes of the
    # big comp to estimate per-node cost, then extrapolate to 601.
    big_trunc = big[:150]
    t0 = time.time()
    perm_b, tb, db, okb = greedy_subtour_only(
        kt, big_trunc, big_trunc[0], max_exc=1, t_start=0.0)
    dt_btrunc = time.time() - t0
    print(f"PROBE 601-trunc(150): {dt_btrunc:.1f}s, covered={len(perm_b)}/150, "
          f"ok={okb}", flush=True)

    # greedy_subtour_only is O(n^2) in find_earliest_transfer calls
    # (each of the n steps scans all remaining unvisited). Scale the
    # truncated big-comp time by (601/150)^2.
    scale = (len(big) / 150.0) ** 2
    est_big = dt_btrunc * scale
    est_total = est_big + 3 * dt_small  # 3 small comps
    print(f"PROBE extrapolation: big-comp ~{est_big:.0f}s "
          f"(scale x{scale:.1f}), 3 small ~{3*dt_small:.0f}s, "
          f"single-pass total ~{est_total:.0f}s ({est_total/60:.1f} min)",
          flush=True)
    return {
        "dt_small_150": dt_small, "dt_big_trunc150": dt_btrunc,
        "est_big_601_s": est_big, "est_total_s": est_total,
    }


def safe_bank(kt, full_perm):
    """Authoritative walk + safe bank. Returns info dict."""
    print(f"\nWalking assembled perm (len={len(full_perm)}) — Lambert per "
          f"leg, this takes minutes on n=1051...", flush=True)
    t0 = time.time()
    times, tofs, dvs, ok, exc_n, last_leg = walk_perm_chrono(
        kt, full_perm, tof_window=12.0, n_steps=120,
        wait_steps=4, wait_dt=1.0)
    print(f"walk_perm_chrono: {time.time()-t0:.0f}s, ok={ok}, "
          f"exc_used={exc_n}/{kt.n_exc}, last_leg={last_leg}", flush=True)

    covered_all = len(set(full_perm)) == kt.n and len(full_perm) == kt.n
    if not (ok and covered_all):
        missing = sorted(set(range(kt.n)) - set(full_perm))
        print(f"INFEASIBLE/PARTIAL: ok={ok}, perm={len(full_perm)}/{kt.n}, "
              f"missing={len(missing)} — banking NOTHING.", flush=True)
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "ok": bool(ok),
            "exc_used": int(exc_n), "last_leg": int(last_leg),
            "missing": missing[:50], "n_missing": len(missing),
        }))
        print(f"Partial saved to {PARTIAL}", flush=True)
        return {"status": "infeasible_partial", "walk_ok": bool(ok),
                "covered": len(set(full_perm)), "exc_used": int(exc_n),
                "n_missing": len(missing)}

    # Authoritative UDP fitness
    x = list(times) + list(tofs) + [float(p) for p in full_perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    print(f"UDP fitness: mk={mk:.4f}d feas={feas} viols={list(fit[1:])}",
          flush=True)
    if not feas:
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "fitness": list(fit),
            "note": "walk ok but UDP infeasible",
        }))
        print(f"UDP infeasible despite walk ok — banking NOTHING. "
              f"Saved {PARTIAL}", flush=True)
        return {"status": "udp_infeasible", "mk": mk,
                "viols": list(fit[1:])}

    # SAFE BANK: back up any existing large.json first
    if Path(OUT).exists():
        bak = OUT + f".bak.{time.strftime('%Y%m%d')}.e556"
        if not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"Backed up existing large.json -> {bak}", flush=True)
    tmp = OUT + ".tmp"
    Path(tmp).write_text(json.dumps([{
        "decisionVector": x, "problem": "large", "challenge": CHALLENGE,
    }]))
    os.replace(tmp, OUT)
    print(f">>> BANKED large: mk={mk:.4f}d -> {OUT}", flush=True)
    return {"status": "banked", "mk": mk, "exc_used": int(exc_n),
            "banked": OUT}


def main():
    ap = argparse.ArgumentParser(description="E-556 large component-aware")
    ap.add_argument("--check", action="store_true",
                    help="import/argparse sanity only; no KTTSP load")
    ap.add_argument("--probe", action="store_true",
                    help="tractability probe only")
    ap.add_argument("--full", action="store_true",
                    help="full construction + walk + safe bank (default)")
    ap.add_argument("--max-exc-internal", type=int, default=1,
                    help="intra-component exc budget per sub-tour")
    ap.add_argument("--small-starts", type=int, default=3,
                    help="start-node seeds for the three 150-comps")
    ap.add_argument("--small-times", type=int, default=2,
                    help="t_start seeds for the three 150-comps")
    args = ap.parse_args()

    if args.check:
        print("CHECK: imports OK, argparse OK. Exiting before KTTSP load.",
              flush=True)
        return

    if not Path(ADJ_FILE).exists():
        print(f"ERR adjacency missing: {ADJ_FILE}", flush=True)
        sys.exit(1)

    kt = KTTSP(INST)
    print(f"E-556 large: n={kt.n}, n_exc={kt.n_exc}, "
          f"max_time={kt.max_time:.1f}d, dv_thr={kt.dv_thr}, "
          f"dv_exc={kt.dv_exc}", flush=True)
    comps = load_components(ADJ_FILE)
    print(f"Components (sorted desc): {[len(c) for c in comps]}", flush=True)

    if args.probe:
        run_probe(kt, comps)
        return

    # ── Full construction ───────────────────────────────────────────
    t_max = kt.max_time
    big_idx = 0  # comps[0] is the 601 big comp (sorted desc)
    subtours = {}
    t_all0 = time.time()
    for ci, comp in enumerate(comps):
        is_big = (ci == big_idx)
        if is_big:
            seeds = [(comp[0], 0.0)]  # single start for the big comp
        else:
            t_grid = np.linspace(0.0, t_max * 0.5, args.small_times)
            seeds = make_seeds(comp, t_grid, args.small_starts)
        t0 = time.time()
        st = build_component_subtour(
            kt, comp, seeds, max_exc_internal=args.max_exc_internal)
        subtours[ci] = st
        # progress AFTER each component completes (not buried)
        print(f"comp{ci} size={st['size']:4d} covered={st['covered']:4d} "
              f"full={st['full']} t_start={st['t_start']:.1f} "
              f"total_tof={st['total_tof']:.1f} "
              f"({time.time()-t0:.0f}s)", flush=True)

    total_covered = sum(st["covered"] for st in subtours.values())
    print(f"All sub-tours built in {time.time()-t_all0:.0f}s. "
          f"total covered={total_covered}/{kt.n}", flush=True)
    if total_covered != kt.n:
        per = {ci: f"{st['covered']}/{st['size']}"
               for ci, st in subtours.items()}
        print(f"WARNING: not all nodes covered by sub-tours: {per}. "
              f"Assembled perm will be incomplete -> will NOT bank.",
              flush=True)

    # ── Order components (only 3 bridges) ───────────────────────────
    order, exc_bridges_est = order_components(kt, subtours)
    print(f"Component order: {order}, estimated exc bridges="
          f"{exc_bridges_est}", flush=True)

    full_perm = []
    for ci in order:
        full_perm.extend(subtours[ci]["perm"])
    dup = len(full_perm) - len(set(full_perm))
    print(f"Assembled perm: len={len(full_perm)} unique={len(set(full_perm))} "
          f"dups={dup}", flush=True)

    info = safe_bank(kt, full_perm)
    print(json.dumps(info, indent=2), flush=True)


if __name__ == "__main__":
    main()
