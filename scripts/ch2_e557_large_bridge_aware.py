"""E-557 — Ch2 large (n=1051): STAR-topology bridge-aware feasible build.

STRUCTURAL FINDING (E-557 probes, from /tmp/ch2_e533_large_adj.npz):
  The cheap-graph components are [601,150,150,150] = comp0..comp3, and
  the INTER-component exc adjacency is a STAR centered on comp0:
    comp0 <-> comp1/2/3 : ~8000 exc edges each
    comp1 <-> comp2/3, comp2<->comp3 : ZERO edges (smalls mutually
                                       disconnected, not even via exc)
  => A linear chain c0->c1->c2->c3 is impossible (c1->c2 has no edge).
     The only viable order interleaves the smalls through comp0.

  E-556 died because order_components used APPROXIMATE timing and forced
  the bridge to leave comp0's GREEDY-TAIL node (which has ~0 small-comp
  exc edges) into comp1's first node. But ~155-164 comp0 "gateway" nodes
  can BOTH launch into and receive back from each small comp.

TOPOLOGY (minimum exc bridges = 5 = budget; ends inside the last small):
    comp0[segA] -exc-> comp1 -exc-> comp0[segB] -exc-> comp2
                 -exc-> comp0[segC] -exc-> comp3   [END]
  5 exc bridges: c0->c1, c1->c0, c0->c2, c2->c0, c0->c3.
  Requires the 4 internal sub-tours to be PURE-CHEAP (0 internal exc),
  since all 5 exc are spent on the structural star bridges.

ALGORITHM (detour insertion into comp0's pure-cheap tour):
  1. Build comp0 pure-cheap greedy sub-tour S0 (multi-start, best
     coverage). Build each small comp's pure-cheap sub-tour (multi-seed,
     full coverage; smalls are easy).
  2. Walk S0 chronologically to get arrival time at each S0 position.
  3. For each of the 3 small comps, find a comp0 detour anchor: a
     position p in S0 such that
       (a) some S0-prefix node at/<=p can LAUNCH (exc) into the small's
           entry at its arrival time, AND
       (b) the small's exit can RETURN (exc) to S0[p+1] at the small's
           exit time  (except the LAST small: no return, tour ends there).
     Pick 3 DISTINCT anchors (one per small), ordered along S0.
  4. Splice: S0[0..p1] + small1 + S0[p1+1..p2] + small2 +
             S0[p2+1..p3] + small3            (small3 = terminal)
     Re-time via the authoritative walk_perm_chrono.
  5. If the full walk is feasible with exc_used<=5 and all 1051 covered,
     SAFE-BANK (verbatim triple guard: walk_ok AND complete AND
     kt.is_feasible; back up large.json first).

Fallbacks if pure-cheap leaves comp0 stragglers: report precisely; do
NOT silently bump internal exc (that breaks the 5-bridge budget).

Run: python scripts/ch2_e557_large_bridge_aware.py 2>&1 | tee runs/ch2_e557_large.log
Deps: PYTHONPATH=src ; micromamba env spoc26.
"""
from __future__ import annotations

import json
import os
import sys
import time
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
PARTIAL = "/tmp/large_e557_partial.json"


def load_comps():
    d = np.load(ADJ_FILE)
    labels = d['labels']
    ncomp = int(labels.max()) + 1
    comps = [[] for _ in range(ncomp)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps, d


def best_pure_subtour(kt, comp, starts, max_exc=0):
    """Best-coverage pure-cheap (default) greedy sub-tour over `starts`."""
    best = None  # (covered, perm, total_tof)
    for s in starts:
        perm, tofs, _dv, ok = greedy_subtour_only(
            kt, comp, s, max_exc=max_exc, t_start=0.0)
        cov = len(perm)
        ttof = float(sum(tofs))
        if best is None or cov > best[0] or (cov == best[0] and ttof < best[2]):
            best = (cov, perm, ttof)
        if cov == len(comp):
            break
    return best[1], best[0]


def bridge_to(kt, src, dst_nodes, t, threshold, wait_steps, wait_dt,
              tof_window=20.0, n_steps=160):
    """Earliest feasible transfer from src to ANY node in dst_nodes,
    starting at t (cheap/exc per `threshold`), over a small wait window.
    Returns (entry_node, tof, dv, t_dep) or None."""
    for w in range(0, wait_steps + 1):
        t_try = t + w * wait_dt
        if t_try >= kt.max_time:
            break
        best = None
        for dn in dst_nodes:
            tof, dv = find_earliest_transfer(
                kt, src, int(dn), t_try, threshold, tof_window, n_steps)
            if tof is not None and (best is None or tof < best[1]):
                best = (int(dn), tof, dv, t_try)
        if best is not None:
            return best
    return None


def safe_bank(kt, full_perm, tag="e557"):
    """Authoritative walk + triple-guarded safe bank (verbatim policy)."""
    print(f"\nWalking assembled perm (len={len(full_perm)})...", flush=True)
    t0 = time.time()
    times, tofs, dvs, ok, exc_n, last_leg = walk_perm_chrono(
        kt, full_perm, tof_window=20.0, n_steps=160, wait_steps=8, wait_dt=1.0)
    print(f"walk_perm_chrono: {time.time()-t0:.0f}s ok={ok} "
          f"exc_used={exc_n}/{kt.n_exc} last_leg={last_leg}", flush=True)

    covered_all = len(set(full_perm)) == kt.n and len(full_perm) == kt.n
    if not (ok and covered_all):
        missing = sorted(set(range(kt.n)) - set(full_perm))
        print(f"INFEASIBLE/PARTIAL ok={ok} perm={len(full_perm)}/{kt.n} "
              f"missing={len(missing)} last_leg={last_leg} — banking NOTHING.",
              flush=True)
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "ok": bool(ok), "exc_used": int(exc_n),
            "last_leg": int(last_leg), "missing": missing[:50],
            "n_missing": len(missing)}))
        return {"status": "infeasible_partial", "walk_ok": bool(ok),
                "covered": len(set(full_perm)), "exc_used": int(exc_n),
                "last_leg": int(last_leg), "n_missing": len(missing)}

    x = list(times) + list(tofs) + [float(p) for p in full_perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    print(f"UDP fitness: mk={mk:.4f}d feas={feas} viols={list(fit[1:])}",
          flush=True)
    if not feas:
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "fitness": list(fit),
            "note": "walk ok but UDP infeasible"}))
        return {"status": "udp_infeasible", "mk": mk, "viols": list(fit[1:])}

    if Path(OUT).exists():
        bak = OUT + f".bak.{time.strftime('%Y%m%d')}.{tag}"
        if not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"Backed up existing large.json -> {bak}", flush=True)
    tmp = OUT + ".tmp"
    Path(tmp).write_text(json.dumps([{
        "decisionVector": x, "problem": "large", "challenge": CHALLENGE}]))
    os.replace(tmp, OUT)
    print(f">>> BANKED large: mk={mk:.4f}d exc_used={exc_n} -> {OUT}",
          flush=True)
    return {"status": "banked", "mk": mk, "exc_used": int(exc_n),
            "banked": OUT}


def main():
    t_all = time.time()
    kt = KTTSP(INST)
    comps, d = load_comps()
    exc = d['exc']
    node2comp = {}
    for ci, c in enumerate(comps):
        for nd in c:
            node2comp[nd] = ci
    lab2 = np.array([node2comp[i] for i in range(kt.n)])
    print(f"E-557 bridge-aware: n={kt.n} comps={[len(c) for c in comps]} "
          f"n_exc={kt.n_exc} max_time={kt.max_time:.0f}d "
          f"dv_thr={kt.dv_thr} dv_exc={kt.dv_exc}", flush=True)

    # gateway candidate sets per small comp (matrix exc edges)
    c0 = np.where(lab2 == 0)[0]
    launch_to = {}   # comp0 nodes that can launch (exc) into small t
    receive_from = {}  # comp0 nodes reachable (exc) from small t
    small_entry_cand = {}  # small-t nodes reachable from comp0 (entries)
    small_exit_cand = {}   # small-t nodes that can reach comp0 (exits)
    for t in (1, 2, 3):
        ct = np.where(lab2 == t)[0]
        out_m = exc[np.ix_(c0, ct)]    # c0 -> small
        in_m = exc[np.ix_(ct, c0)]     # small -> c0
        launch_to[t] = set(int(c0[i]) for i in np.where(out_m.sum(axis=1) > 0)[0])
        receive_from[t] = set(int(c0[i]) for i in np.where(in_m.sum(axis=0) > 0)[0])
        small_entry_cand[t] = set(int(ct[j]) for j in np.where(out_m.sum(axis=0) > 0)[0])
        small_exit_cand[t] = set(int(ct[i]) for i in np.where(in_m.sum(axis=1) > 0)[0])

    # ── 1. comp0 pure-cheap sub-tour ──
    # comp0 greedy is the dominant cost (601-node O(n^2) Lambert, ~mins
    # per start). Use a SINGLE best start by default to stay tractable on
    # 1 free core; the star design needs comp0 pure-cheap-complete, which a
    # single start already gives if it covers 601.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--c0-starts", type=int, default=1)
    args, _ = ap.parse_known_args()
    print(f"\n[1] comp0 pure-cheap sub-tour ({args.c0_starts} start(s))...",
          flush=True)
    t0 = time.time()
    n_c0_starts = args.c0_starts
    # Cache comp0 + smalls sub-tours to disk (comp0 greedy is ~12 min).
    cache = Path("/tmp/ch2_e557_subtours.json")
    if cache.exists():
        cd = json.loads(cache.read_text())
        S0 = cd["S0"]
        cov0 = len(S0)
        smalls = {int(k): v for k, v in cd["smalls"].items()}
        print(f"  REUSED cached sub-tours: comp0={cov0}/601, "
              f"smalls={{t: len(v) for t, v in smalls.items()}}",
              flush=True)
    else:
        S0, cov0 = best_pure_subtour(kt, comps[0], comps[0][:n_c0_starts])
        print(f"  comp0 covered {cov0}/601 ({time.time()-t0:.0f}s)",
              flush=True)
        if cov0 < 601:
            miss0 = sorted(set(comps[0]) - set(S0))
            print(f"  comp0 stragglers ({len(miss0)}): {miss0[:30]}",
                  flush=True)
        print("[2] small comps pure-cheap sub-tours...", flush=True)
        smalls = {}
        for t in (1, 2, 3):
            t0 = time.time()
            starts = comps[t][:8]
            Sk, covk = best_pure_subtour(kt, comps[t], starts)
            smalls[t] = Sk
            print(f"  comp{t} covered {covk}/150 ({time.time()-t0:.0f}s)",
                  flush=True)
        cache.write_text(json.dumps({"S0": S0, "smalls": smalls}))
        print(f"  cached sub-tours -> {cache}", flush=True)

    # ── 3. walk S0 to get arrival time at each position ──
    print("[3] walking comp0 sub-tour for per-position times...", flush=True)
    t0 = time.time()
    times0, tofs0, dvs0, ok0, exc0, ll0 = walk_perm_chrono(
        kt, S0, tof_window=20.0, n_steps=160, wait_steps=6, wait_dt=1.0)
    print(f"  S0 walk ok={ok0} reached {ll0+1}/{len(S0)} exc={exc0} "
          f"({time.time()-t0:.0f}s)", flush=True)
    if not ok0:
        S0 = S0[:ll0 + 1]
        print(f"  truncating S0 to walked prefix {len(S0)}", flush=True)
    # arrival time at S0[i]
    arr0 = [0.0]
    for i in range(len(tofs0)):
        arr0.append(times0[i] + tofs0[i])
    arr0 = arr0[:len(S0)]

    # ── 4. choose 3 distinct detour anchors along S0 ──
    # Place the 3 detours at roughly 1/4, 2/4, 3/4 of S0; the LAST detour
    # (comp3) is terminal (no return). Search a window of anchor positions
    # around each target fraction for a position whose node can launch into
    # the small AND (for non-terminal) whose successor can be reached back.
    print("[4] selecting detour anchors + bridges...", flush=True)
    order_small = [1, 2, 3]  # comp3 terminal
    fracs = [0.25, 0.50, 0.78]
    L = len(S0)
    used_pos = set()
    detours = {}  # small_t -> dict(pos, launch_node, entry, exit, ret_node)
    WAIT, WDT = 8, 1.0

    for fi, t in enumerate(order_small):
        terminal = (fi == len(order_small) - 1)
        if terminal:
            # The terminal small ENDS the tour: anchor it as late as
            # possible so NO comp0 nodes follow it (otherwise the walk
            # would need an unbudgeted small->comp0 bridge). Window =
            # the last positions of S0, searched latest-first.
            window = list(range(L - 1, max(0, L - 60), -1))
        else:
            center = int(fracs[fi] * (L - 2))
            window = list(range(max(1, center - 40), min(L - 1, center + 40)))
            # prefer positions near center
            window.sort(key=lambda p: abs(p - center))
        Sk = smalls[t]
        entry_pool = [n for n in Sk if n in small_entry_cand[t]] or Sk
        exit_pool = [n for n in Sk if n in small_exit_cand[t]] or Sk
        chosen = None
        n_tried = 0
        for p in window:
            if p in used_pos:
                continue
            launch_node = S0[p]
            if launch_node not in launch_to[t]:
                continue
            t_here = arr0[p]
            n_tried += 1
            # launch comp0->small entry
            lb = bridge_to(kt, launch_node, entry_pool, t_here, kt.dv_exc,
                           WAIT, WDT)
            if lb is None:
                continue
            entry, tof_l, dv_l, tdep_l = lb
            # walk the small sub-tour (rotate so entry is first) to get exit time
            ei = Sk.index(entry)
            small_rot = Sk[ei:] + Sk[:ei]
            # estimate small exit time via a quick chrono walk of the rotated small
            t_small_start = tdep_l + tof_l
            # cheap walk the rotated small from t_small_start
            tsm, tofsm, _dv, oksm, excsm, llsm = walk_perm_chrono(
                kt, small_rot, tof_window=20.0, n_steps=160,
                wait_steps=4, wait_dt=1.0)
            # NOTE: walk_perm_chrono starts at t=0 internally; we only need
            # the RELATIVE total tof of the small to estimate exit time.
            small_total = (tsm[-1] + tofsm[-1]) if tofsm else 0.0
            if not oksm or llsm + 1 < len(small_rot):
                # small not fully walkable starting from this entry; skip
                continue
            exit_node = small_rot[-1]
            t_exit = t_small_start + small_total
            if terminal:
                chosen = {"pos": p, "launch_node": launch_node,
                          "entry": entry, "small_rot": small_rot,
                          "exit": exit_node, "ret_node": None}
                break
            # need a return exc bridge small_exit -> S0[p+1]
            ret_target = S0[p + 1]
            if ret_target not in receive_from[t]:
                # try a few successors as the return target
                ret_ok = None
                for q in range(p + 1, min(p + 6, L)):
                    if S0[q] in receive_from[t]:
                        rb = bridge_to(kt, exit_node, [S0[q]], t_exit,
                                       kt.dv_exc, WAIT, WDT)
                        if rb is not None:
                            ret_ok = (q, S0[q])
                            break
                if ret_ok is None:
                    continue
                qpos, ret_node = ret_ok
                chosen = {"pos": p, "qpos": qpos, "launch_node": launch_node,
                          "entry": entry, "small_rot": small_rot,
                          "exit": exit_node, "ret_node": ret_node}
                break
            rb = bridge_to(kt, exit_node, [ret_target], t_exit, kt.dv_exc,
                           WAIT, WDT)
            if rb is None:
                continue
            chosen = {"pos": p, "qpos": p + 1, "launch_node": launch_node,
                      "entry": entry, "small_rot": small_rot,
                      "exit": exit_node, "ret_node": ret_target}
            break
        if chosen is None:
            print(f"  comp{t}: NO anchor found in {n_tried} tried positions "
                  f"near frac {fracs[fi]}", flush=True)
            detours[t] = None
        else:
            detours[t] = chosen
            print(f"  comp{t}: anchor pos={chosen['pos']} "
                  f"launch={chosen['launch_node']} entry={chosen['entry']} "
                  f"exit={chosen['exit']} ret={chosen.get('ret_node')} "
                  f"terminal={terminal}", flush=True)
            used_pos.add(chosen["pos"])

    if any(detours[t] is None for t in order_small):
        print("\nSome detour could not be anchored — reporting partial. "
              "Banking NOTHING.", flush=True)
        Path(PARTIAL).write_text(json.dumps({
            "detours": {t: (None if detours[t] is None else
                            {k: v for k, v in detours[t].items()
                             if k != 'small_rot'})
                        for t in order_small},
            "comp0_cov": cov0}))
        print(json.dumps({"status": "no_anchor",
                          "detours": {t: detours[t] is not None
                                      for t in order_small}}, indent=2))
        return

    # ── 5. splice the full permutation in S0 order ──
    # Build by walking S0 and inserting each small right after its anchor pos.
    # Sort detours by position so splicing is well-defined.
    items = sorted(((detours[t]["pos"], t) for t in order_small))
    full_perm = []
    prev = 0
    for pos, t in items:
        # for non-terminal we return at qpos; nodes between pos+1 and qpos-1
        # in S0 would be SKIPPED by the bridge, so include them BEFORE the
        # detour to avoid dropping comp0 nodes.
        det = detours[t]
        qpos = det.get("qpos")
        terminal = det["ret_node"] is None
        if terminal:
            # everything up to and including pos, then the small (terminal)
            full_perm.extend(S0[prev:pos + 1])
            full_perm.extend(det["small_rot"])
            prev = pos + 1  # remaining S0 (should be none if terminal last)
        else:
            full_perm.extend(S0[prev:pos + 1])
            full_perm.extend(det["small_rot"])
            # resume comp0 at ret_node (=S0[qpos]); include S0[pos+1:qpos]
            # AFTER returning would double-bridge, so instead we make the
            # return land on S0[pos+1] (qpos==pos+1 by construction unless
            # fallback). If qpos>pos+1, the skipped S0[pos+1:qpos] are placed
            # right after the return node to keep them in the cheap chain.
            prev = pos + 1
    # append any trailing S0 nodes not yet placed (after last non-terminal)
    if prev < len(S0):
        full_perm.extend(S0[prev:])

    # dedup check
    uniq = len(set(full_perm))
    print(f"\nAssembled perm len={len(full_perm)} unique={uniq} "
          f"dups={len(full_perm)-uniq}", flush=True)
    missing = sorted(set(range(kt.n)) - set(full_perm))
    if missing:
        print(f"WARNING: {len(missing)} nodes missing from assembly: "
              f"{missing[:30]}", flush=True)
    # remove accidental dups preserving first occurrence
    seen = set()
    dedup = []
    for p in full_perm:
        if p not in seen:
            seen.add(p)
            dedup.append(p)
    full_perm = dedup

    info = safe_bank(kt, full_perm)
    print(json.dumps(info, indent=2), flush=True)
    print(f"\nTotal wall {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
