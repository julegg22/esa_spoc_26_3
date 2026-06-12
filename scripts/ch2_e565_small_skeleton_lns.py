"""E-048 (script e565): Ch2 SMALL skeleton-level destroy-repair LNS.

E-564 proved the bank perm is converged for (a) timing (ultrafine-DP
floored) and (b) comp0 INTERIOR order (epoch-aware reorder iter null),
AND its Phase-2 only relocated nodes WITHIN a single comp0 run -> cannot
change the SKELETON. The live board (2026-06-12) shows our 116.37 sits
~rank 7 behind a dense competitor cluster at 111.75 (r4-6) -> a better
skeleton provably exists (achieved by others). The skeleton DoF E-564
never touched: the ORDER of the 3 tiny comps (start/mid/end roles), the
comp0 SPLIT (run sizes), and WHICH comp0 nodes serve as bridge endpoints.

Lever: monotone windowed destroy-repair over the FULL perm (n=49 is tiny
enough for whole-tour windows). Destroy a random contiguous window, repair
with an OR-Tools open-path solve over an epoch-aware cost that allows BOTH
cheap and exception arcs (cost = min(cheap,exc)*epoch + exc penalty), fixed
window endpoints, splice back, then ultrafine-DP re-time the FULL perm
(exact n_exc<=5 accounting) and OFFICIAL kt.fitness score. Accept ONLY a
strictly-lower feasible official makespan => MONOTONE, cannot diverge; the
repair is free to re-route bridges so the skeleton itself moves.

GUARDED: best feasible candidate -> /tmp ONLY; banks NOTHING. Reuses the
validated E-564 Table/solve_open_path/dp_time_perm/score machinery.
"""
from __future__ import annotations
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
sys.path.insert(0, f"{ROOT}/scripts")
from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # noqa: E402
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from ch2_e564_small_epoch_aware import (  # noqa: E402
    Table, dp_time_perm, score, BIG, SCALE)

sys.stdout.reconfigure(line_buffering=True)

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
BANK = f"{ROOT}/solutions/upload/small.json"
TABLE = "/tmp/ch2_small_tcoupled_ultrafine.npz"
CURRENT_BANK = 116.37377097878698
R5_SMALL = 111.79
R3_SMALL = 108.77

SEED = int(os.environ.get("E565_SEED", "0"))
CAND = os.environ.get("E565_OUT", f"/tmp/ch2_small_skeleton_cand_s{SEED}.json")
WMIN = int(os.environ.get("E565_WMIN", "8"))
WMAX = int(os.environ.get("E565_WMAX", "20"))
SOLVE_S = int(os.environ.get("E565_SOLVES", "3"))
EXC_PEN = float(os.environ.get("E565_EXCPEN", "2.0"))   # days added per exc
TL = float(os.environ.get("E565_TL", "10800"))
TCAP = float(os.environ.get("E565_TCAP", "130"))


def window_cost(tab, nodes, depart_epoch):
    """Epoch-aware cost over `nodes` allowing cheap AND exc arcs.
    cost = best feasible tof at the entry epoch (+ flat penalty if the
    only feasible arc is an exception), so the repair prefers cheap arcs
    but may bridge across components when needed. BIG if neither reachable.
    """
    m = len(nodes)
    pen = int(round(EXC_PEN * SCALE))
    C = np.full((m, m), BIG, dtype=np.int64)
    for a in range(m):
        i = nodes[a]
        t_i = depart_epoch[a]
        for b in range(m):
            if a == b:
                C[a][b] = 0
                continue
            j = nodes[b]
            ctof = tab.cheap_tof(i, j, t_i) if tab.cheap_any[i, j] else None
            if ctof is not None:
                C[a][b] = int(round(ctof * SCALE))
                continue
            etof = tab.exc_tof(i, j, t_i)
            if etof is not None:
                C[a][b] = int(round(etof * SCALE)) + pen
    return C


def repair(C, start_local, end_local, time_s, seed_order=None):
    m = C.shape[0]
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, :] = BIG
    D[:, depot] = BIG
    D[depot, depot] = 0
    D[depot, start_local] = 0
    D[end_local, depot] = 0
    mgr = pywrapcp.RoutingIndexManager(N, 1, depot)
    routing = pywrapcp.RoutingModel(mgr)

    def cb(fi, ti):
        return int(D[mgr.IndexToNode(fi)][mgr.IndexToNode(ti)])

    idx = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(idx)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)
    p.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    p.time_limit.FromSeconds(time_s)
    routing.CloseModelWithParameters(p)
    if seed_order is not None:
        init = routing.ReadAssignmentFromRoutes([list(seed_order)], True)
        sol = (routing.SolveFromAssignmentWithParameters(init, p)
               if init is not None else routing.SolveWithParameters(p))
    else:
        sol = routing.SolveWithParameters(p)
    if sol is None:
        return None
    order, it = [], routing.Start(0)
    while not routing.IsEnd(it):
        node = mgr.IndexToNode(it)
        if node != depot:
            order.append(node)
        it = sol.Value(routing.NextVar(it))
    return order


def main():
    kt = KTTSP(INST)
    n = kt.n
    tab = Table(TABLE, t_cap=TCAP)
    bank = json.load(open(BANK))[0]["decisionVector"]
    order = [int(round(v)) for v in bank[2 * (n - 1):]]

    tt, tf, dok = dp_time_perm(tab, order, kt.n_exc)
    assert dok, "bank not DP-timable"
    x, fit, feas, mk = score(kt, order, tt, tf)
    assert feas, "bank infeasible under DP-timing"
    cur_mk = mk
    cur_times = tt
    best_mk = mk
    print(f"[E-565] n={n} start mk={mk:.4f} feas={feas} "
          f"(bank {CURRENT_BANK}, r5 {R5_SMALL}, r3 {R3_SMALL}) seed={SEED}",
          flush=True)

    rng = np.random.default_rng(SEED)
    t0 = time.time()
    it = 0
    acc = 0
    while time.time() - t0 < TL:
        it += 1
        W = int(rng.integers(WMIN, WMAX + 1))
        W = min(W, n - 2)
        i = int(rng.integers(1, n - W))         # keep node0 fixed as start
        block = [order[i - 1]] + order[i:i + W] + (
            [order[i + W]] if i + W < n else [])
        # local departure epochs from current timing
        ep = {order[k]: float(cur_times[k]) for k in range(len(cur_times))}
        ep[order[-1]] = float(cur_times[-1]) if cur_times else 0.0
        depart_epoch = [ep.get(nd, cur_times[i - 1] if cur_times else 0.0)
                        for nd in block]
        C = window_cost(tab, block, depart_epoch)
        end_local = len(block) - 1
        seed_local = list(range(len(block)))
        sol = repair(C, 0, end_local, SOLVE_S, seed_order=seed_local)
        if sol is None or len(set(sol)) != len(block) \
                or sol[0] != 0 or sol[-1] != end_local:
            continue
        new_internal = [block[k] for k in sol[1:-1]]
        if new_internal == order[i:i + W]:
            continue
        tail = order[i + W:] if i + W < n else []
        new_order = order[:i] + new_internal + tail
        if len(set(new_order)) != n:
            continue
        tt2, tf2, dok2 = dp_time_perm(tab, new_order, kt.n_exc)
        if not dok2:
            continue
        x2, fit2, feas2, mk2 = score(kt, new_order, tt2, tf2)
        if feas2 and mk2 < cur_mk - 1e-4:
            order = new_order
            cur_mk = mk2
            cur_times = tt2
            acc += 1
            if mk2 < best_mk:
                best_mk = mk2
                tag = (" BEATS r3!" if mk2 < R3_SMALL else
                       " BEATS r5!" if mk2 < R5_SMALL else "")
                Path(CAND).write_text(json.dumps([{
                    "decisionVector": x2, "problem": "small",
                    "challenge": CHALLENGE}]))
                print(f"[it {it}] ACCEPT W={W}@{i} mk={mk2:.4f} acc={acc}{tag} "
                      f"({time.time()-t0:.0f}s) -> wrote cand", flush=True)
            else:
                print(f"[it {it}] accept W={W}@{i} mk={mk2:.4f} acc={acc} "
                      f"({time.time()-t0:.0f}s)", flush=True)
        if it % 25 == 0:
            print(f"[it {it}] cur mk={cur_mk:.4f} best={best_mk:.4f} acc={acc} "
                  f"({time.time()-t0:.0f}s)", flush=True)

    print(f"\n[FINAL] best feasible mk={best_mk:.4f} acc={acc} "
          f"(bank {CURRENT_BANK})", flush=True)
    if best_mk < CURRENT_BANK - 1e-4:
        print(f"[FINAL] beats bank by {CURRENT_BANK-best_mk:.4f}d"
              f"{' — BEATS r5' if best_mk < R5_SMALL else ''}"
              f"{' — BEATS r3' if best_mk < R3_SMALL else ''}", flush=True)
    else:
        print("[FINAL] no improvement over bank.", flush=True)
    print(f"[OUT] {CAND}", flush=True)


if __name__ == "__main__":
    main()
