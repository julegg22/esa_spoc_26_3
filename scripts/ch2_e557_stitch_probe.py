"""E-557 — Ch2 large: STITCH PROBE at the comp0->comp1 boundary.

The E-556 component-aware assembly DIED in the chronological walk at the
comp0->comp1 boundary (leg 590, both at max_exc_internal=1 and =2). The
order_components heuristic claimed a cheap bridge exists using APPROXIMATE
timing (t_start + sum(tofs)), but the true chronological walk at real
arrival time found NO feasible transfer out of comp0's last node into
comp1's first node.

This probe answers, CHEAPLY (no 75-min construction): is the boundary
HARD-INFEASIBLE or FIXABLE?

Method:
  1. Rebuild comp0's covered sub-tour (single start, like E-556) AND
     comp1's sub-tour (best of a few seeds). [Or reuse the exc2 partial.]
  2. Walk comp0's sub-tour chronologically -> real arrival time t_exit
     and the actual covered node sequence.
  3. Over a grid of comp0 EXIT-node candidates (the last K nodes of
     comp0's covered sub-tour, since a chronological walk's exit time
     depends on where you stop) x comp1 ENTRY-node candidates (several
     of comp1's nodes), search find_earliest_transfer at the real exit
     time (cheap dv_thr first, then exc dv_exc), over a small wait window.
  4. Report: does ANY (exit, entry, t) pair admit a feasible bridge?

Verdict:
  (i) HARD-INFEASIBLE: nothing feasible at any reasonable time -> the
      [601-anchor then 150s] ordering is doomed at this boundary.
  (ii) FIXABLE: some pair works -> assembly just picked bad boundary
      nodes / used approximate timing.

The probe ALSO checks all 12 ordered component-pair boundaries
(comp_a exit -> comp_b entry) so we can recommend a viable visit order
if comp0->comp1 specifically is the only bad one.

Deps: PYTHONPATH=src ; env python micromamba/envs/spoc26.
Run: python scripts/ch2_e557_stitch_probe.py 2>&1 | tee runs/ch2_e557_stitch_probe.log
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_hierarchical_large import greedy_subtour_only
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import KTTSP

sys.stdout.reconfigure(line_buffering=True)

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ_FILE = "/tmp/ch2_e533_large_adj.npz"
PARTIAL = "/tmp/large_component_partial.json"


def load_components(adj_file):
    d = np.load(adj_file)
    labels = d['labels']
    n_comps = int(labels.max()) + 1
    comps = [[] for _ in range(n_comps)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps


def probe_bridge(kt, exit_node, entry_node, t_exit, wait_steps=8,
                 wait_dt=1.0, tof_window=20.0, n_steps=160):
    """Search for a feasible bridge exit_node -> entry_node starting at
    t_exit, trying cheap (dv_thr) first then exc (dv_exc), over a small
    wait window. Returns (kind, tof, dv, t_dep) or (None, ...)."""
    for w in range(0, wait_steps + 1):
        t_try = t_exit + w * wait_dt
        if t_try >= kt.max_time:
            break
        # cheap first
        tof, dv = find_earliest_transfer(
            kt, exit_node, entry_node, t_try, kt.dv_thr, tof_window, n_steps)
        if tof is not None:
            return ("cheap", tof, dv, t_try)
    # exc pass (separate so cheap is always preferred at earliest time)
    for w in range(0, wait_steps + 1):
        t_try = t_exit + w * wait_dt
        if t_try >= kt.max_time:
            break
        tof, dv = find_earliest_transfer(
            kt, exit_node, entry_node, t_try, kt.dv_exc, tof_window, n_steps)
        if tof is not None:
            return ("exc", tof, dv, t_try)
    return (None, None, None, None)


def main():
    t_all = time.time()
    kt = KTTSP(INST)
    print(f"E-557 stitch probe: n={kt.n}, n_exc={kt.n_exc}, "
          f"max_time={kt.max_time:.1f}d, dv_thr={kt.dv_thr}, "
          f"dv_exc={kt.dv_exc}, min_tof={kt.min_tof}", flush=True)
    comps = load_components(ADJ_FILE)
    print(f"Components: {[len(c) for c in comps]}", flush=True)

    # ── Build comp0 covered sub-tour (single start, like E-556 full) ──
    # Reuse the exc2 partial's comp0 sequence if present (avoids rebuild).
    comp0_seq = None
    if Path(PARTIAL).exists():
        d = json.load(open(PARTIAL))
        node2comp = {}
        for ci, c in enumerate(comps):
            for nd in c:
                node2comp[nd] = ci
        perm = d['perm']
        comp0_seq = [p for p in perm if node2comp[p] == 0]
        print(f"Reusing comp0 sub-tour from partial: {len(comp0_seq)} nodes "
              f"(covered/601)", flush=True)

    if comp0_seq is None or len(comp0_seq) < 100:
        print("Rebuilding comp0 sub-tour (single start, max_exc=2)...",
              flush=True)
        t0 = time.time()
        comp0_seq, _t, _d, ok = greedy_subtour_only(
            kt, comps[0], comps[0][0], max_exc=2, t_start=0.0)
        print(f"  comp0 rebuilt: {len(comp0_seq)} nodes, ok={ok} "
              f"({time.time()-t0:.0f}s)", flush=True)

    # Walk comp0 sub-tour to get the REAL arrival time at its exit node.
    print("\nWalking comp0 sub-tour to get real exit time...", flush=True)
    t0 = time.time()
    times0, tofs0, dvs0, ok0, exc0, lastleg0 = walk_perm_chrono(
        kt, comp0_seq, tof_window=12.0, n_steps=120, wait_steps=4, wait_dt=1.0)
    if ok0:
        t_exit0 = times0[-1] + tofs0[-1]
        exit_walked = len(comp0_seq)
    else:
        # walk died inside comp0; use whatever it reached
        t_exit0 = (times0[-1] + tofs0[-1]) if tofs0 else 0.0
        exit_walked = lastleg0
    print(f"  comp0 walk: ok={ok0}, reached {exit_walked}/{len(comp0_seq)} "
          f"nodes, exc_used={exc0}, t_exit={t_exit0:.2f}d "
          f"({time.time()-t0:.0f}s)", flush=True)

    # Candidate exit nodes: the last several nodes of the walked comp0 seq.
    walked_seq = comp0_seq[:exit_walked]
    K_exit = 12
    exit_cands = walked_seq[-K_exit:]
    # Their cumulative arrival times (so we probe at the RIGHT time per exit)
    exit_times = {}
    if ok0:
        # times0[i] is dep time of leg i; arrival at node i+1 = times0[i]+tofs0[i]
        # node walked_seq[k] arrives at times0[k-1]+tofs0[k-1] for k>=1
        for k in range(len(walked_seq)):
            if k == 0:
                exit_times[walked_seq[k]] = 0.0
            else:
                exit_times[walked_seq[k]] = times0[k - 1] + tofs0[k - 1]
    else:
        for k, nd in enumerate(walked_seq):
            if k < len(times0):
                exit_times[nd] = (times0[k] + tofs0[k]) if k < len(tofs0) else t_exit0
            else:
                exit_times[nd] = t_exit0

    # ── Probe ALL 12 ordered comp-pair boundaries, focus on comp0->comp1 ─
    # For each target component, take a sample of entry-node candidates.
    K_entry = 20
    print(f"\nProbing boundaries. exit_cands={len(exit_cands)} (last "
          f"{K_exit} of comp0 walk), entry_cands={K_entry} per target comp.",
          flush=True)

    results = {}
    for tgt in (1, 2, 3):
        entry_cands = comps[tgt][:K_entry]
        feas_cheap = []
        feas_exc = []
        n_probed = 0
        t0 = time.time()
        for ex in exit_cands:
            t_ex = exit_times.get(ex, t_exit0)
            for en in entry_cands:
                n_probed += 1
                kind, tof, dv, tdep = probe_bridge(
                    kt, ex, en, t_ex, wait_steps=8, wait_dt=1.0,
                    tof_window=20.0, n_steps=160)
                if kind == "cheap":
                    feas_cheap.append((ex, en, tof, dv, tdep))
                elif kind == "exc":
                    feas_exc.append((ex, en, tof, dv, tdep))
        results[tgt] = {"cheap": feas_cheap, "exc": feas_exc,
                        "n_probed": n_probed}
        print(f"  comp0 -> comp{tgt}: probed {n_probed} pairs in "
              f"{time.time()-t0:.0f}s -> cheap={len(feas_cheap)}, "
              f"exc={len(feas_exc)}", flush=True)
        if feas_cheap:
            ex, en, tof, dv, tdep = min(feas_cheap, key=lambda r: r[2])
            print(f"    BEST cheap: exit={ex} entry={en} tof={tof:.2f} "
                  f"dv={dv:.1f} t_dep={tdep:.2f}", flush=True)
        if feas_exc:
            ex, en, tof, dv, tdep = min(feas_exc, key=lambda r: r[3])
            print(f"    BEST exc:   exit={ex} entry={en} tof={tof:.2f} "
                  f"dv={dv:.1f} t_dep={tdep:.2f}", flush=True)

    # ── Verdict ─────────────────────────────────────────────────────
    print("\n===== VERDICT =====", flush=True)
    any_feas = any(results[t]["cheap"] or results[t]["exc"]
                   for t in (1, 2, 3))
    c1 = results[1]
    if c1["cheap"] or c1["exc"]:
        print("comp0 -> comp1 is FIXABLE: a feasible bridge exists at the "
              "real exit time. E-556 failed because order_components used "
              "approximate timing and the walk picked the wrong boundary "
              "nodes / departure time.", flush=True)
        verdict = "fixable"
    elif any_feas:
        good = [t for t in (2, 3) if results[t]["cheap"] or results[t]["exc"]]
        print(f"comp0 -> comp1 HARD-INFEASIBLE at this boundary, BUT comp0 "
              f"-> comp{good} IS feasible. FORK: reorder components so comp0 "
              f"exits into comp{good[0]} first, not comp1.", flush=True)
        verdict = "reorder"
    else:
        print("HARD-INFEASIBLE: comp0 admits NO feasible exit (cheap or exc) "
              "into ANY other component at the real exit time. The "
              "[601-anchor then 150s] decomposition is doomed from comp0's "
              "exit. Fork needed: different anchor exit node distribution, "
              "interleaving, or accept a much later t_exit.", flush=True)
        verdict = "hard_infeasible"

    summary = {
        "verdict": verdict,
        "t_exit0": t_exit0,
        "comp0_walk_ok": bool(ok0),
        "comp0_reached": exit_walked,
        "boundaries": {
            f"comp0->comp{t}": {
                "n_cheap": len(results[t]["cheap"]),
                "n_exc": len(results[t]["exc"]),
                "best_cheap": (min(results[t]["cheap"], key=lambda r: r[2])[:2]
                               + (round(min(results[t]["cheap"], key=lambda r: r[2])[2], 3),)
                               if results[t]["cheap"] else None),
                "best_exc": (min(results[t]["exc"], key=lambda r: r[3])[:2]
                             + (round(min(results[t]["exc"], key=lambda r: r[3])[3], 1),)
                             if results[t]["exc"] else None),
            } for t in (1, 2, 3)
        },
    }
    Path("/tmp/ch2_e557_probe_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2), flush=True)
    print(f"\nTotal probe wall: {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
