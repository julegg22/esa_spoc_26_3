"""E-558 — Ch2 large (n=1051): multi-pass pure-cheap comp0 + star assembly.

WHY (quantitative decomposition, from E-556/E-557 evidence):
  First-feasible-bank gap has three confirmed causes:
    A. star topology  — comp1/2/3 mutually 0-edge => linear order
       impossible; smalls must interleave through comp0. (E-557 matrix)
    B. boundary walk-break — E-556 concatenated comp0->comp1 and the
       walk broke at leg 590 launching from comp0's greedy TAIL with
       approximate timing. Fix: launch bridges from gateway nodes. (E-557)
    C. comp0 pure-cheap incompleteness — single-start pure-cheap greedy
       covers only 329/601, but the 272 stranded nodes are NOT
       low-degree (median cheap out-deg 151, 26k internal cheap edges):
       the stranding is pure greedy MYOPIA, not infeasibility. (this exp)

  Cause C is the dominant unresolved one and the star needs comp0
  pure-cheap-COMPLETE (0 internal exc, since 5 star bridges == budget 5).

LEVER (3-sentence guardrail):
  1. Addresses decomposition row C (comp0 pure-cheap 329 -> ~601).
  2. Signature: a 2nd pure-cheap greedy restarted on the 272 stranded
     nodes covers most of them; repeat until coverage saturates.
  3. Magnitude: 329 -> 550+ enabling the 5-bridge star within budget.

ALGORITHM:
  1. Multi-pass pure-cheap comp0: pass over all unvisited comp0 with a
     fresh start node (max_exc=0). Each pass returns its covered prefix;
     remove from unvisited; repeat until no progress or full. Cache the
     ordered list of passes (segments).
  2. Reuse the 3 fully-covered small sub-tours from E-557 cache.
  3. Assemble star-interleaved perm: comp0 segments are concatenated in
     pass order to form S0'; the 3 smalls are inserted as detours at
     gateway anchors (reusing E-557's bridge_to logic), terminal small
     last. The AUTHORITATIVE walk_perm_chrono (global budget 5) is the
     only feasibility judge.
  4. SAFE BANK (verbatim triple guard) iff walk_ok AND 1051 covered AND
     kt.is_feasible. Else report the precise blocker (exc overage,
     missing nodes, or walk last_leg).

Run: micromamba run -n spoc26 python scripts/ch2_e558_comp0_multipass.py \
        2>&1 | tee runs/ch2_e558_comp0_multipass.log
Deps: PYTHONPATH=src ; env spoc26.
"""
from __future__ import annotations

import argparse
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
E557_CACHE = "/tmp/ch2_e557_subtours.json"
PASS_CACHE = "/tmp/ch2_e558_comp0_passes.json"
OUT = f"{ROOT}/solutions/upload/large.json"
PARTIAL = "/tmp/large_e558_partial.json"


def load_comps():
    d = np.load(ADJ_FILE)
    labels = d['labels']
    ncomp = int(labels.max()) + 1
    comps = [[] for _ in range(ncomp)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps, d


def multipass_pure_cheap(kt, comp, cheap, max_passes=12, seed_seg=None,
                         resume_segments=None):
    """Pure-cheap (max_exc=0) greedy passes until comp covered or no
    progress. Each pass starts at the cheap-highest-out-degree unvisited
    node (best chance of a long chain). Returns list of segment perms.
    `seed_seg`: an already-computed pure-cheap segment (e.g. the cached
    329-node E-557 S0) used as pass 0 to avoid recomputation."""
    comp_set = set(comp)
    unvis = set(comp)
    segments = []
    # precompute cheap out-degree within comp for start selection
    comp_arr = np.array(comp)
    outdeg = {int(n): int(cheap[n, comp_arr].sum()) for n in comp}
    if resume_segments:
        for seg in resume_segments:
            kept = [n for n in seg if n in unvis]
            segments.append(kept)
            for n in kept:
                unvis.discard(n)
        cov = sum(len(s) for s in segments)
        print(f"  resumed {len(segments)} segments, covered {cov}, "
              f"remaining={len(unvis)}", flush=True)
    elif seed_seg:
        seed = [n for n in seed_seg if n in unvis]
        segments.append(seed)
        for n in seed:
            unvis.discard(n)
        print(f"  pass 0 (seeded): covered={len(seed)} "
              f"remaining={len(unvis)}", flush=True)
    base = len(segments)
    for pi in range(max_passes):
        p = base + pi
        if not unvis:
            break
        # start node: highest cheap out-degree among unvisited
        start = max(unvis, key=lambda n: outdeg[n])
        t0 = time.time()
        perm, tofs, dvs, ok = greedy_subtour_only(
            kt, sorted(unvis), start, max_exc=0, t_start=0.0)
        seg = [n for n in perm if n in unvis]  # safety: only unvisited
        segments.append(seg)
        for n in seg:
            unvis.discard(n)
        print(f"  pass {p}: start={start} covered={len(seg)} "
              f"remaining={len(unvis)} ok={ok} ({time.time()-t0:.0f}s)",
              flush=True)
        # checkpoint segments so far (partial progress survives a kill)
        Path(PASS_CACHE + ".partial").write_text(
            json.dumps({"segments": segments}))
        if len(seg) == 0:
            print("  pass produced 0 new nodes — stopping.", flush=True)
            break
    covered = sum(len(s) for s in segments)
    print(f"  multipass total covered {covered}/{len(comp_set)} in "
          f"{len(segments)} passes", flush=True)
    return segments


def bridge_to(kt, src, dst_nodes, t, threshold, wait_steps, wait_dt,
              tof_window=20.0, n_steps=160):
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


def safe_bank(kt, full_perm, tag="e558"):
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
              f"missing={len(missing)} last_leg={last_leg} exc={exc_n} "
              f"— banking NOTHING.", flush=True)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-passes", type=int, default=12)
    args = ap.parse_args()

    t_all = time.time()
    kt = KTTSP(INST)
    comps, d = load_comps()
    cheap = d['cheap']
    exc = d['exc']
    node2comp = {}
    for ci, c in enumerate(comps):
        for nd in c:
            node2comp[nd] = ci
    lab2 = np.array([node2comp[i] for i in range(kt.n)])
    print(f"E-558 multipass: n={kt.n} comps={[len(c) for c in comps]} "
          f"n_exc={kt.n_exc} dv_thr={kt.dv_thr} dv_exc={kt.dv_exc}",
          flush=True)

    # gateway candidate sets per small comp (matrix exc edges)
    c0 = np.where(lab2 == 0)[0]
    launch_to, receive_from = {}, {}
    small_entry_cand, small_exit_cand = {}, {}
    for t in (1, 2, 3):
        ct = np.where(lab2 == t)[0]
        out_m = exc[np.ix_(c0, ct)]
        in_m = exc[np.ix_(ct, c0)]
        launch_to[t] = set(int(c0[i]) for i in np.where(out_m.sum(axis=1) > 0)[0])
        receive_from[t] = set(int(c0[i]) for i in np.where(in_m.sum(axis=0) > 0)[0])
        small_entry_cand[t] = set(int(ct[j]) for j in np.where(out_m.sum(axis=0) > 0)[0])
        small_exit_cand[t] = set(int(ct[i]) for i in np.where(in_m.sum(axis=1) > 0)[0])

    # ── 1. multi-pass pure-cheap comp0 ──
    print("\n[1] multi-pass pure-cheap comp0...", flush=True)
    if Path(PASS_CACHE).exists():
        segments = json.loads(Path(PASS_CACHE).read_text())["segments"]
        cov = sum(len(s) for s in segments)
        print(f"  REUSED cached passes: {len(segments)} segments, "
              f"covered {cov}/601", flush=True)
    elif Path(PASS_CACHE + ".partial").exists():
        prior = json.loads(Path(PASS_CACHE + ".partial").read_text())["segments"]
        cov = sum(len(s) for s in prior)
        print(f"  RESUME from partial: {len(prior)} segments, covered "
              f"{cov}/601 — continuing passes on remainder", flush=True)
        segments = multipass_pure_cheap(kt, comps[0], cheap,
                                        max_passes=args.max_passes,
                                        resume_segments=prior)
        Path(PASS_CACHE).write_text(json.dumps({"segments": segments}))
        print(f"  cached passes -> {PASS_CACHE}", flush=True)
    else:
        seed_seg = None
        if Path(E557_CACHE).exists():
            seed_seg = json.loads(Path(E557_CACHE).read_text()).get("S0")
        segments = multipass_pure_cheap(kt, comps[0], cheap,
                                        max_passes=args.max_passes,
                                        seed_seg=seed_seg)
        Path(PASS_CACHE).write_text(json.dumps({"segments": segments}))
        print(f"  cached passes -> {PASS_CACHE}", flush=True)
    S0 = [n for seg in segments for n in seg]
    cov0 = len(S0)
    miss0 = sorted(set(comps[0]) - set(S0))
    print(f"  comp0 multipass S0 len={cov0}/601 missing={len(miss0)} "
          f"{miss0[:20]}", flush=True)

    # smalls from E-557 cache
    smalls = {int(k): v for k, v in
              json.loads(Path(E557_CACHE).read_text())["smalls"].items()}
    print(f"  smalls (E-557 cache): "
          f"{{t: len(v) for t,v in smalls.items()}}={{1: {len(smalls[1])}, "
          f"2: {len(smalls[2])}, 3: {len(smalls[3])}}}", flush=True)

    # ── 2. walk S0 for per-position arrival times ──
    print("\n[2] walking S0 for per-position times...", flush=True)
    t0 = time.time()
    times0, tofs0, dvs0, ok0, exc0, ll0 = walk_perm_chrono(
        kt, S0, tof_window=20.0, n_steps=160, wait_steps=6, wait_dt=1.0)
    print(f"  S0 walk ok={ok0} reached {ll0+1}/{len(S0)} exc={exc0} "
          f"({time.time()-t0:.0f}s)", flush=True)
    if not ok0:
        S0 = S0[:ll0 + 1]
        print(f"  truncating S0 to walked prefix {len(S0)}", flush=True)
    arr0 = [0.0]
    for i in range(len(tofs0)):
        arr0.append(times0[i] + tofs0[i])
    arr0 = arr0[:len(S0)]

    # ── 3. star-interleaved detour anchors ──
    print("\n[3] selecting detour anchors + bridges...", flush=True)
    order_small = [1, 2, 3]
    fracs = [0.25, 0.50, 0.78]
    L = len(S0)
    used_pos = set()
    detours = {}
    WAIT, WDT = 8, 1.0
    for fi, t in enumerate(order_small):
        terminal = (fi == len(order_small) - 1)
        if terminal:
            window = list(range(L - 1, max(0, L - 120), -1))
        else:
            center = int(fracs[fi] * (L - 2))
            window = list(range(max(1, center - 80), min(L - 1, center + 80)))
            window.sort(key=lambda p: abs(p - center))
        Sk = smalls[t]
        entry_pool = [n for n in Sk if n in small_entry_cand[t]] or Sk
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
            lb = bridge_to(kt, launch_node, entry_pool, t_here, kt.dv_exc,
                           WAIT, WDT)
            if lb is None:
                continue
            entry, tof_l, dv_l, tdep_l = lb
            ei = Sk.index(entry)
            small_rot = Sk[ei:] + Sk[:ei]
            t_small_start = tdep_l + tof_l
            tsm, tofsm, _dv, oksm, excsm, llsm = walk_perm_chrono(
                kt, small_rot, tof_window=20.0, n_steps=160,
                wait_steps=4, wait_dt=1.0)
            small_total = (tsm[-1] + tofsm[-1]) if tofsm else 0.0
            if not oksm or llsm + 1 < len(small_rot):
                continue
            exit_node = small_rot[-1]
            t_exit = t_small_start + small_total
            if terminal:
                chosen = {"pos": p, "launch_node": launch_node,
                          "entry": entry, "small_rot": small_rot,
                          "exit": exit_node, "ret_node": None}
                break
            ret_ok = None
            for q in range(p + 1, min(p + 8, L)):
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
        if chosen is None:
            print(f"  comp{t}: NO anchor in {n_tried} tried positions",
                  flush=True)
            detours[t] = None
        else:
            detours[t] = chosen
            print(f"  comp{t}: anchor pos={chosen['pos']} "
                  f"launch={chosen['launch_node']} entry={chosen['entry']} "
                  f"exit={chosen['exit']} ret={chosen.get('ret_node')} "
                  f"terminal={terminal}", flush=True)
            used_pos.add(chosen["pos"])

    if any(detours[t] is None for t in order_small):
        print("\nSome detour could not be anchored. Banking NOTHING.",
              flush=True)
        Path(PARTIAL).write_text(json.dumps({
            "detours": {t: (None if detours[t] is None else
                            {k: v for k, v in detours[t].items()
                             if k != 'small_rot'}) for t in order_small},
            "comp0_cov": cov0}))
        print(json.dumps({"status": "no_anchor", "comp0_cov": cov0,
                          "detours": {t: detours[t] is not None
                                      for t in order_small}}, indent=2))
        return

    # ── 4. splice (S0 order) ──
    items = sorted(((detours[t]["pos"], t) for t in order_small))
    full_perm = []
    prev = 0
    for pos, t in items:
        det = detours[t]
        full_perm.extend(S0[prev:pos + 1])
        full_perm.extend(det["small_rot"])
        prev = pos + 1
    if prev < len(S0):
        full_perm.extend(S0[prev:])
    seen, dedup = set(), []
    for p in full_perm:
        if p not in seen:
            seen.add(p)
            dedup.append(p)
    full_perm = dedup
    uniq = len(set(full_perm))
    missing = sorted(set(range(kt.n)) - set(full_perm))
    print(f"\nAssembled perm len={len(full_perm)} unique={uniq} "
          f"missing={len(missing)} {missing[:20]}", flush=True)

    info = safe_bank(kt, full_perm)
    print(json.dumps(info, indent=2), flush=True)
    print(f"\nTotal wall {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
