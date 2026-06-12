"""E-047 (script e578): Ch2 LARGE — windowed destroy-repair LNS (monotone).

E-042/E-577 isolated the lever: the 1048 bank is an Or-opt LOCAL OPTIMUM
under realized makespan (single-node relocations all fail re-walk: the
downstream epoch cascade wipes every local gain). Global re-solves (E-572)
and fixpoints (E-573) diverge (epoch-shift trap). The one remaining
tractable, monotone, untried attack: re-optimize a CONTIGUOUS WINDOW of the
tour at once (multi-node move => can escape single-move optima), with the
entry epoch FIXED and the result spliced back only if the FULL re-walk
gives a strictly lower, still-feasible realized makespan.

Repair = OR-Tools open Hamilton path over [entry-pred + window nodes +
exit-succ], fixed start/end, epoch-aware cost built at the window's entry
epoch (approx). Verify by chrono re-walk from the window start; accept only
strict feasible improvement => MONOTONE, cannot diverge. Bounded epoch
shift (only the window + downstream re-walk). Random window starts + sizes.

GUARDED: best feasible candidate -> /tmp ONLY; banks NOTHING. BINARY
(E-042): only realized mk < r1=424.62 changes rank — low-point-EV frontier
probe on idle cores.
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
BANK = f"{ROOT}/solutions/upload/large.json"
SEED = int(os.environ.get("E578_SEED", "0"))
OUT = os.environ.get("E578_OUT", f"/tmp/ch2_large_window_cand_s{SEED}.json")
CURRENT_BANK = 1048.9786
R1 = 424.62

BIG = 10_000_000
SCALE = 1000.0
WIN = float(os.environ.get("E578_WIN", "6.0"))
STEPS = int(os.environ.get("E578_STEPS", "40"))
WMIN = int(os.environ.get("E578_WMIN", "20"))
WMAX = int(os.environ.get("E578_WMAX", "45"))
SOLVE_S = int(os.environ.get("E578_SOLVES", "5"))
TL = float(os.environ.get("E578_TL", "36000"))
WALK = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)


def walk(kt, perm):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, perm, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return dict(times=times, tofs=tofs, x=x, mk=float(fit[0]),
                feas=bool(kt.is_feasible(fit)), exc=exc, viols=list(fit[1:]))


def window_cost(kt, ids, t0):
    """Epoch-aware cost among `ids` built at entry epoch t0 (approx)."""
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
    """Open path over all nodes, fixed start_local -> ... -> end_local."""
    m = C.shape[0]
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, :] = BIG
    D[:, depot] = BIG
    D[depot, depot] = 0
    D[depot, start_local] = 0       # path starts at start_local
    D[end_local, depot] = 0         # ...and ends at end_local
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
    bank = json.load(open(BANK))[0]["decisionVector"]
    order = [int(round(v)) for v in bank[2 * (n - 1):]]
    cur = walk(kt, order)
    assert cur is not None and cur["feas"], "bank not walkable"
    best_mk = cur["mk"]
    print(f"[E-578] n={n} start mk={cur['mk']:.3f} feas={cur['feas']} "
          f"exc={cur['exc']} (bank {CURRENT_BANK}, r1 {R1})", flush=True)

    rng = np.random.default_rng(SEED)
    t_start = time.time()
    it = 0
    acc = 0
    while time.time() - t_start < TL:
        it += 1
        W = int(rng.integers(WMIN, WMAX + 1))
        i = int(rng.integers(1, n - W - 1))     # window start (keep fixed s0)
        # block: [pred] + window[i..i+W-1] + [succ]
        ids = [order[i - 1]] + order[i:i + W] + [order[i + W]]
        t0 = cur["times"][i - 1]
        C = window_cost(kt, ids, t0)
        sol = repair_window(C, 0, len(ids) - 1, SOLVE_S)
        if sol is None or len(set(sol)) != len(ids) or sol[0] != 0 \
                or sol[-1] != len(ids) - 1:
            continue
        new_internal = [ids[k] for k in sol[1:-1]]
        if new_internal == order[i:i + W]:
            continue                              # unchanged
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
            print(f"[it {it}] ACCEPT W={W}@{i} mk={cur['mk']:.3f} "
                  f"exc={cur['exc']} acc={acc} ({time.time()-t_start:.0f}s)",
                  flush=True)
        if it % 50 == 0:
            print(f"[it {it}] cur mk={cur['mk']:.3f} acc={acc} "
                  f"({time.time()-t_start:.0f}s)", flush=True)

    print(f"\n[FINAL] best feasible mk={best_mk:.3f} acc={acc} "
          f"(bank {CURRENT_BANK}, r1 {R1})", flush=True)
    if best_mk < R1:
        print("[FINAL] *** BEATS r1 -> RANK 1 ***", flush=True)
    elif best_mk < CURRENT_BANK - 1e-4:
        print(f"[FINAL] beats bank by {CURRENT_BANK-best_mk:.3f}d "
              f"(still r2 unless <424)", flush=True)
    else:
        print("[FINAL] no improvement over bank.", flush=True)
    print(f"[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    main()
