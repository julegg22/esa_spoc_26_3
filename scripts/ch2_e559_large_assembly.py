"""E-559 — Ch2 large (n=1051): OR-Tools global ordering + leaf-leaf bank.

First feasible bank for the LARGE instance. Replaces the MYOPIC greedy
(E-556/557) comp0 build — which painted itself into corners covering only
329/601 — with a GLOBAL Hamiltonian order from OR-Tools over comp0's static
cheap graph, then TIME-VALIDATES that order against the real time-dependent
walk.

Topology (established, /tmp/ch2_e533_large_adj.npz): cheap graph = 4
components [601,150,150,150]; the 601 big comp is labels==2 (comps[0] after
size-sort). STAR: each small connects to comp0 via ~8000 exc edges; smalls
mutually disconnected.

LEAF-LEAF routing (4 bridges, leaves 1 exc free for comp0-internal):
    small_S (start) -exc-> comp0[segA] -exc-> small_M (mid)
                    -exc-> comp0[segB] -exc-> small_E (end)
  comp0 is split into 2 cheap passes (segA, segB) joined through small_M.
  4 exc bridges + <=1 comp0-internal exc = <=5 = budget. BANKABLE iff
  comp0 needs at most 1 internal exc (K<=2 cheap passes).

Pipeline:
  1. comp0 = labels==2. OR-Tools ATSP on static cheap cost (1 if cheap else
     BIG) -> Hamiltonian ORDER minimising non-cheap jumps.
  2. TIME-VALIDATE the order forward with find_earliest_transfer (cheap;
     fall back to <=1 internal exc only where the cheap chain stalls).
     This is the authoritative check — static cheap != time-feasible.
  3. Split comp0 order into segA|segB at a point where a small can be
     inserted mid-route (the mid small's entry/exit bridge comp0->small
     ->comp0). Pick start/end/mid smalls.
  4. Assemble full 1051 perm, walk_perm_chrono, triple-guard safe bank.

Run: micromamba run -n spoc26 python scripts/ch2_e559_large_assembly.py \
        2>&1 | tee runs/ch2_e559_large_assembly.log
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

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

sys.stdout.reconfigure(line_buffering=True)

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ_FILE = "/tmp/ch2_e533_large_adj.npz"
OUT = f"{ROOT}/solutions/upload/large.json"
PARTIAL = "/tmp/large_e559_partial.json"
ORDER_CACHE = "/tmp/ch2_e559_comp0_order.json"

BIG = 100000  # OR-Tools cost for a non-cheap (would-be exc) jump


def load_comps():
    d = np.load(ADJ_FILE)
    labels = d['labels']
    ncomp = int(labels.max()) + 1
    comps = [[] for _ in range(ncomp)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps, d


def ortools_hamiltonian(cheap_sub, time_limit_s=180):
    """Solve an open-path ATSP over the static cheap subgraph: cost 1 if a
    cheap edge exists, else BIG. Returns the node ORDER (local indices into
    cheap_sub) as a list, plus the number of BIG (non-cheap) jumps used.

    Open path (not cycle): add a dummy depot with 0 cost to/from all real
    nodes so the optimal "cycle" through the dummy = an open Hamiltonian
    path over the real nodes."""
    n = cheap_sub.shape[0]
    N = n + 1  # node n = dummy depot
    DEPOT = n

    cost = np.full((N, N), BIG, dtype=np.int64)
    cost[:n, :n] = np.where(cheap_sub, 1, BIG)
    np.fill_diagonal(cost, 0)
    cost[DEPOT, :] = 0  # depot -> any real node free (start anywhere)
    cost[:, DEPOT] = 0  # any real node -> depot free (end anywhere)
    cost[DEPOT, DEPOT] = 0

    mgr = pywrapcp.RoutingIndexManager(N, 1, DEPOT)
    routing = pywrapcp.RoutingModel(mgr)

    def cb(a, b):
        return int(cost[mgr.IndexToNode(a), mgr.IndexToNode(b)])

    idx = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(idx)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    params.time_limit.FromSeconds(int(time_limit_s))
    params.log_search = False

    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None, None

    order = []
    big_jumps = 0
    i = routing.Start(0)
    prev_real = None
    while not routing.IsEnd(i):
        node = mgr.IndexToNode(i)
        if node != DEPOT:
            if prev_real is not None and not cheap_sub[prev_real, node]:
                big_jumps += 1
            order.append(node)
            prev_real = node
        i = sol.Value(routing.NextVar(i))
    return order, big_jumps


def validate_walk_segment(kt, nodes_seq, t_start, max_internal_exc,
                          tof_window=20.0, n_steps=120, wait_steps=6,
                          wait_dt=1.0):
    """Time-forward walk a FIXED node sequence (the OR-Tools order). At each
    leg try cheap, then (if budget) exc, then wait. Returns
    (perm_walked, times, tofs, dvs, exc_used, ok, stall_idx). Does NOT
    reorder; it reports exactly where it stalls so the caller can decide."""
    cur = nodes_seq[0]
    t = t_start
    perm = [cur]
    times, tofs, dvs = [], [], []
    exc = 0
    for k in range(1, len(nodes_seq)):
        j = nodes_seq[k]
        tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                         tof_window, n_steps)
        is_exc = False
        if tof is None and exc < max_internal_exc:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                             tof_window, n_steps)
            is_exc = tof is not None
        if tof is None:
            # wait then retry cheap (then exc)
            found = False
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                tof2, dv2 = find_earliest_transfer(kt, cur, j, t_try,
                                                   kt.dv_thr, tof_window,
                                                   n_steps)
                if tof2 is not None:
                    t, tof, dv, is_exc, found = t_try, tof2, dv2, False, True
                    break
                if exc < max_internal_exc:
                    tof2, dv2 = find_earliest_transfer(kt, cur, j, t_try,
                                                       kt.dv_exc, tof_window,
                                                       n_steps)
                    if tof2 is not None:
                        t, tof, dv = t_try, tof2, dv2
                        is_exc, found = True, True
                        break
            if not found:
                return perm, times, tofs, dvs, exc, False, k
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = t + tof
        cur = j
        perm.append(j)
    return perm, times, tofs, dvs, exc, True, len(nodes_seq)


def repair_order(kt, order, t_start, max_internal_exc, adj_cheap,
                 idx_of, tof_window=40.0, n_steps=300, wait_steps=12,
                 wait_dt=2.0):
    """Walk `order` STRICTLY in sequence. Established fact (E-559 probe):
    100% of static cheap edges are TIME-FEASIBLE with a ~40d tof window, so
    the static cheap graph == the time-feasible cheap graph and any
    REORDERING strands the walk in visited-out neighbourhoods (Hamiltonicity
    failure, not time-infeasibility). Therefore walk in OR-Tools order with
    NO substitution. Each static-cheap leg goes cheap (wide window + small
    wait); each static big-jump (>=1 in the order) is paid with one
    internal exc. Returns (perm,...,exc,n_left)."""
    cur = order[0]
    t = t_start
    perm = [cur]
    times, tofs, dvs = [], [], []
    exc = 0
    for k in range(1, len(order)):
        j = order[k]
        tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                         tof_window, n_steps)
        is_exc = False
        if tof is None:
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                 kt.dv_thr, tof_window,
                                                 n_steps)
                if tof is not None:
                    t = t_try
                    break
        if tof is None and exc < max_internal_exc:
            # static big-jump: pay one internal exc
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                             tof_window, n_steps)
            if tof is None:
                for w in range(1, wait_steps + 1):
                    t_try = t + w * wait_dt
                    if t_try >= kt.max_time:
                        break
                    tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                     kt.dv_exc, tof_window,
                                                     n_steps)
                    if tof is not None:
                        t = t_try
                        break
            is_exc = tof is not None
        if tof is None:
            break  # stuck (big-jump with no exc budget left)
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = t + tof
        cur = j
        perm.append(j)
    return perm, times, tofs, dvs, exc, len(order) - len(perm)


def best_small_subtour(smalls_cache, t):
    return list(smalls_cache[str(t)])


def safe_bank(kt, full_perm, tag="e559"):
    print(f"\n[BANK] Walking assembled perm (len={len(full_perm)})...",
          flush=True)
    t0 = time.time()
    times, tofs, dvs, ok, exc_n, last_leg = walk_perm_chrono(
        kt, full_perm, tof_window=40.0, n_steps=300, wait_steps=8,
        wait_dt=1.0)
    print(f"[BANK] walk_perm_chrono: {time.time()-t0:.0f}s ok={ok} "
          f"exc_used={exc_n}/{kt.n_exc} last_leg={last_leg}", flush=True)

    covered_all = len(set(full_perm)) == kt.n and len(full_perm) == kt.n
    if not (ok and covered_all):
        missing = sorted(set(range(kt.n)) - set(full_perm))
        print(f"[BANK] INFEASIBLE/PARTIAL ok={ok} perm={len(full_perm)}/"
              f"{kt.n} missing={len(missing)} last_leg={last_leg} — "
              f"banking NOTHING.", flush=True)
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "ok": bool(ok), "exc_used": int(exc_n),
            "last_leg": int(last_leg), "missing": missing[:80],
            "n_missing": len(missing)}))
        return {"status": "infeasible_partial", "walk_ok": bool(ok),
                "covered": len(set(full_perm)), "exc_used": int(exc_n),
                "last_leg": int(last_leg), "n_missing": len(missing)}

    x = list(times) + list(tofs) + [float(p) for p in full_perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    print(f"[BANK] UDP fitness: mk={mk:.4f}d feas={feas} "
          f"viols={list(fit[1:])}", flush=True)
    if not feas:
        Path(PARTIAL).write_text(json.dumps({
            "perm": list(full_perm), "fitness": list(fit),
            "note": "walk ok but UDP infeasible"}))
        return {"status": "udp_infeasible", "mk": mk, "viols": list(fit[1:])}

    if Path(OUT).exists():
        bak = OUT + f".bak.{time.strftime('%Y%m%d')}.{tag}"
        if not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"[BANK] Backed up existing large.json -> {bak}", flush=True)
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
    ap.add_argument("--ortools-time", type=int, default=180)
    ap.add_argument("--rebuild-order", action="store_true")
    args = ap.parse_args()

    t_all = time.time()
    kt = KTTSP(INST)
    comps, d = load_comps()
    cheap, exc = d['cheap'], d['exc']
    comp0 = comps[0]
    print(f"E-559: n={kt.n} comps={[len(c) for c in comps]} n_exc={kt.n_exc} "
          f"max_time={kt.max_time:.0f}d dv_thr={kt.dv_thr} dv_exc={kt.dv_exc}",
          flush=True)
    assert len(comp0) == 601, comp0

    # ── 1. OR-Tools Hamiltonian over comp0 static cheap graph ──
    # Prefer the GATEWAY-ENDPOINT order (head reachable-from start-small,
    # tail launch-into end-small), built separately; falls back to the plain
    # order if absent.
    cheap_sub = cheap[np.ix_(comp0, comp0)]
    gw_cache = Path("/tmp/ch2_e559_comp0_order_gw.json")
    gw_meta = None
    if gw_cache.exists() and not args.rebuild_order:
        gd = json.loads(gw_cache.read_text())
        order_local = gd["order"]
        gw_meta = gd
        print(f"[1] REUSED GATEWAY-endpoint order (len={len(order_local)} "
              f"start_small={gd['start_small']} end_small={gd['end_small']})",
              flush=True)
    elif Path(ORDER_CACHE).exists() and not args.rebuild_order:
        order_local = json.loads(Path(ORDER_CACHE).read_text())["order"]
        print(f"[1] REUSED cached OR-Tools order (len={len(order_local)})",
              flush=True)
    else:
        print(f"[1] OR-Tools ATSP on comp0 cheap graph "
              f"(time_limit={args.ortools_time}s)...", flush=True)
        t0 = time.time()
        order_local, big_jumps = ortools_hamiltonian(cheap_sub,
                                                     args.ortools_time)
        print(f"[1] OR-Tools done {time.time()-t0:.0f}s: order_len="
              f"{len(order_local) if order_local else None} "
              f"static_big_jumps={big_jumps}", flush=True)
        if order_local is None or len(order_local) != 601:
            print("[1] OR-Tools failed to return a full order — abort.",
                  flush=True)
            return
        Path(ORDER_CACHE).write_text(json.dumps(
            {"order": order_local, "big_jumps": big_jumps}))
    order_global = [int(comp0[i]) for i in order_local]
    idx_of = {int(g): k for k, g in enumerate(comp0)}

    # ── 2. locate any STATIC big-jump in the order (no Lambert needed) ──
    # E-559 probe: 100% of static cheap edges are time-feasible, so the
    # comp0 walk needs NO internal exc on cheap legs. The only obstacle is a
    # static big-jump. We do NOT spend an internal exc on it; instead we
    # split the comp0 order AT the big-jump and route the MID small through
    # that gap (segA_tail -> mid -> segB_head), turning the gap into two
    # already-budgeted bridges. walk_perm_chrono is the authoritative check.
    big_pos = [k for k in range(len(order_global) - 1)
               if not cheap_sub[idx_of[order_global[k]],
                                idx_of[order_global[k + 1]]]]
    print(f"[2] static big-jumps in order at positions {big_pos} "
          f"(0=>any split point works for mid small; 1=>force split there)",
          flush=True)
    if len(big_pos) > 1:
        print(f"[2] WARNING {len(big_pos)} big-jumps; leaf-leaf only hides "
              f"ONE via the mid small. Banking may fail.", flush=True)

    # ── 3. gateway-aware leaf-leaf assembly ──
    # Bridges (all EXC): B1 start_small_exit -> comp0_head; B2 segA_tail ->
    # mid_small_entry; B3 mid_small_exit -> segB_head; B4 segB_tail ->
    # end_small_entry. Each bridge endpoint pair needs a STATIC exc edge
    # (=> time-feasible per E-559 probe). The comp0 order has its HEAD
    # reachable-from start_small and TAIL launch-into end_small (gateway
    # solve). The mid-small split is forced AT the big-jump (if any) so the
    # gap is bridged by the mid detour, leaving the comp0 segments pure
    # cheap. Total exc = 4 bridges + 0 internal = 4 <= 5.
    smalls_cache = json.loads(
        Path("/tmp/ch2_e557_subtours.json").read_text())["smalls"]
    if gw_meta is not None:
        start_small = int(gw_meta["start_small"])
        end_small = int(gw_meta["end_small"])
        mid_small = ({1, 2, 3} - {start_small, end_small}).pop()
    else:
        start_small, mid_small, end_small = 1, 2, 3
    print(f"[3] gateway leaf-leaf: start=small{start_small} "
          f"mid=small{mid_small} end=small{end_small}", flush=True)

    c0 = order_global  # the static comp0 Hamiltonian order (601 nodes)
    sstart = list(smalls_cache[str(start_small)])
    smid = list(smalls_cache[str(mid_small)])
    send = list(smalls_cache[str(end_small)])

    def rotate_to_exit(sub, exit_set):
        """Rotate `sub` (a cheap cycle-ish order) so its LAST node has an exc
        edge in `exit_set` (set of allowed exit nodes). Return rotated list
        or None."""
        for r in range(len(sub)):
            rot = sub[r:] + sub[:r]
            if rot[-1] in exit_set:
                return rot
        return None

    def rotate_to_entry(sub, entry_set):
        for r in range(len(sub)):
            rot = sub[r:] + sub[:r]
            if rot[0] in entry_set:
                return rot
        return None

    def rotate_entry_exit(sub, entry_set, exit_set):
        for r in range(len(sub)):
            rot = sub[r:] + sub[:r]
            if rot[0] in entry_set and rot[-1] in exit_set:
                return rot
        return None

    head, tail = c0[0], c0[-1]
    # start_small must EXIT into head: rotate so last node has exc->head
    sstart_rot = rotate_to_exit(sstart, {n for n in sstart if exc[n, head]})
    # end_small must be ENTERED from tail: rotate so first node has tail->exc
    send_rot = rotate_to_entry(send, {n for n in send if exc[tail, n]})
    if sstart_rot is None or send_rot is None:
        print(f"[3] cannot rotate start/end small to gateways "
              f"(start_ok={sstart_rot is not None} "
              f"end_ok={send_rot is not None}) — abort.", flush=True)
        return

    # mid small: scan splits where c0[s-1] can launch into mid AND c0[s] is
    # reachable from mid. FORCE the big-jump position(s) first (so the gap is
    # hidden by the mid detour), then center-out.
    mid_launch = {int(c) for c in c0 for n in smid if exc[c, n]}   # comp0->mid
    mid_recv = {int(c) for c in c0 for n in smid if exc[n, c]}     # mid->comp0
    L = len(c0)
    forced = [bp + 1 for bp in big_pos]  # split index s puts big-jump at seg boundary
    rest = sorted((s for s in range(1, L) if s not in forced),
                  key=lambda s: abs(s - L // 2))
    cand_s = forced + rest
    tried = 0
    for s in cand_s:
        a_tail, b_head = c0[s - 1], c0[s]
        if a_tail not in mid_launch or b_head not in mid_recv:
            continue
        # rotate mid so entry reachable from a_tail and exit reaches b_head
        entry_set = {n for n in smid if exc[a_tail, n]}
        exit_set = {n for n in smid if exc[n, b_head]}
        smid_rot = rotate_entry_exit(smid, entry_set, exit_set)
        if smid_rot is None:
            continue
        tried += 1
        segA, segB = c0[:s], c0[s:]
        full_perm = (list(sstart_rot) + list(segA) + list(smid_rot)
                     + list(segB) + list(send_rot))
        if len(set(full_perm)) != kt.n or len(full_perm) != kt.n:
            continue
        print(f"[3] split s={s} (segA={len(segA)} segB={len(segB)}) bridges: "
              f"start->{head}, {a_tail}->mid, mid->{b_head}, {tail}->end "
              f"— full walk...", flush=True)
        info = safe_bank(kt, full_perm, tag="e559")
        print(json.dumps(info, indent=2), flush=True)
        if info["status"] == "banked":
            print(f"\nTotal wall {time.time()-t_all:.0f}s", flush=True)
            return
        if tried >= 8:
            break
    print(f"\n[3] No gateway split produced a feasible bank "
          f"(tried {tried}). See partial.", flush=True)
    print(f"Total wall {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
