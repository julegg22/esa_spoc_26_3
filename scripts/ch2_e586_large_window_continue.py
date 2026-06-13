"""E-586: Ch2 LARGE — continue windowed destroy-repair LNS from the
unbanked 979.768d candidate (E-578 s2, interrupted before banking).

Identical monotone window-repair lever as E-578 (ch2_e578_large_window_lns.py)
but: (a) SEED = an arbitrary candidate json (default the 979.768d s2 cand),
(b) FINE walk grid (n_steps=2400, wait_dt=0.25 — E-045 sweet spot), so the
re-walk that VERIFIES each splice scores legs on the 0.005d grid the bank
itself uses. GUARDED: best feasible -> /tmp ONLY; banks NOTHING.
"""
import json
import os
import sys
import time

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
SEEDFILE = os.environ.get("E586_SEEDFILE",
                          "/tmp/ch2_large_window_cand_s2.json")
SEED = int(os.environ.get("E586_SEED", "0"))
OUT = os.environ.get("E586_OUT", f"/tmp/ch2_large_cand_e586_s{SEED}.json")
R1 = 424.62

BIG = 10_000_000
SCALE = 1000.0
WIN = float(os.environ.get("E586_WIN", "6.0"))
STEPS = int(os.environ.get("E586_STEPS", "40"))
WMIN = int(os.environ.get("E586_WMIN", "20"))
WMAX = int(os.environ.get("E586_WMAX", "45"))
SOLVE_S = int(os.environ.get("E586_SOLVES", "5"))
TL = float(os.environ.get("E586_TL", "5400"))
# FINE grid for the verifying re-walk (E-045 sweet spot)
WALK = dict(tof_window=40.0, n_steps=2400, wait_steps=8, wait_dt=0.25)


def walk(kt, perm):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, perm, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return dict(times=times, tofs=tofs, x=x, mk=float(fit[0]),
                feas=bool(kt.is_feasible(fit)), exc=exc, viols=list(fit[1:]))


def window_cost(kt, ids, t0):
    m = len(ids)
    C = np.full((m, m), BIG, dtype=np.int64)
    np.fill_diagonal(C, 0)
    for a in range(m):
        for b in range(m):
            if a == b:
                continue
            tof, dv = find_earliest_transfer(kt, ids[a], ids[b], t0,
                                             kt.dv_exc, WIN, STEPS)
            if tof is not None:
                C[a, b] = int(round(tof * SCALE))
    return C


def repair_window(C, start_local, end_local, time_s):
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
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    p.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    p.time_limit.FromSeconds(time_s)
    routing.CloseModelWithParameters(p)
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
    seedx = json.load(open(SEEDFILE))[0]["decisionVector"]
    order = [int(round(v)) for v in seedx[2 * (n - 1):]]
    cur = walk(kt, order)
    assert cur is not None and cur["feas"], "seed not walkable on fine grid"
    best_mk = cur["mk"]
    # bank the fine-grid re-walk of the seed immediately if it already <= seed
    json.dump([{"decisionVector": cur["x"], "problem": "large",
                "challenge": CHALLENGE}], open(OUT, "w"))
    print(f"[E-586] n={n} seed={SEEDFILE} fine-walk mk={cur['mk']:.4f} "
          f"feas={cur['feas']} exc={cur['exc']} viols={cur['viols']} "
          f"(r1 {R1})", flush=True)

    rng = np.random.default_rng(SEED)
    t_start = time.time()
    it = 0
    acc = 0
    while time.time() - t_start < TL:
        it += 1
        W = int(rng.integers(WMIN, WMAX + 1))
        i = int(rng.integers(1, n - W - 1))
        ids = [order[i - 1]] + order[i:i + W] + [order[i + W]]
        t0 = cur["times"][i - 1]
        C = window_cost(kt, ids, t0)
        sol = repair_window(C, 0, len(ids) - 1, SOLVE_S)
        if sol is None or len(set(sol)) != len(ids) or sol[0] != 0 \
                or sol[-1] != len(ids) - 1:
            continue
        new_internal = [ids[k] for k in sol[1:-1]]
        if new_internal == order[i:i + W]:
            continue
        new_order = order[:i] + new_internal + order[i + W:]
        if len(set(new_order)) != n:
            continue
        w = walk(kt, new_order)
        if w is None or not w["feas"]:
            continue
        if w["mk"] < cur["mk"] - 1e-4:
            order = new_order
            cur = w
            acc += 1
            if cur["mk"] < best_mk:
                best_mk = cur["mk"]
                json.dump([{"decisionVector": cur["x"], "problem": "large",
                            "challenge": CHALLENGE}], open(OUT, "w"))
            print(f"[it {it}] ACCEPT W={W}@{i} mk={cur['mk']:.4f} "
                  f"exc={cur['exc']} acc={acc} ({time.time()-t_start:.0f}s)",
                  flush=True)
        if it % 25 == 0:
            print(f"[it {it}] cur mk={cur['mk']:.4f} acc={acc} "
                  f"({time.time()-t_start:.0f}s)", flush=True)

    print(f"\n[FINAL] best feasible mk={best_mk:.4f} acc={acc} (r1 {R1})",
          flush=True)
    print(f"[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    main()
