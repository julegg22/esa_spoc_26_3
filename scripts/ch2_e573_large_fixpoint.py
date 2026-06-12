"""E-043 (script e573): Ch2 LARGE — time-dependent fixpoint rebuild.

E-042 (e572) found a GLOBAL order with cheap-cost ~389d (< r1=424d) but
the chronological walk REJECTED it: costs were built at the SEED's epochs,
and reordering shifts realized epochs so cheap-at-seed edges become
infeasible at the new arrival times (the time-dependent TSP trap).

Fix: a FIXPOINT iteration that stays self-consistent.
  - soft_walk: never rejects — escalating dv caps + waiting always produce
    SOME transfer, so ANY order yields a complete realized-epoch profile
    (and an over-budget-exc count = how far from feasible it is).
  - Build the epoch-aware cost at the order's OWN soft-walk epochs, so each
    edge's cost reflects where it is actually walked.
  - Global GLS open-path solve, seeded from the current order.
  - soft_walk the new order -> fresh epochs; ALSO strict walk_perm_chrono
    to test true feasibility (<=5 exc). Track best STRICT-feasible mk.
  - Iterate; the order is driven toward being cheap at its own epochs.

GUARDED: candidate (best STRICT-feasible) -> /tmp ONLY; banks NOTHING.
"""
import json
import multiprocessing as mp
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
ADJ = "/tmp/ch2_e533_large_adj.npz"
OUT = "/tmp/ch2_large_fixpoint_candidate.json"

BIG = 10_000_000
PENALTY = 60_000
SCALE = 1000.0
TOF_WINDOW = float(os.environ.get("E573_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E573_NSTEPS", "120"))
N_ITERS = int(os.environ.get("E573_NITERS", "10"))
TL = int(os.environ.get("E573_TL", "300"))
WORKERS = int(os.environ.get("E573_WORKERS", "4"))
CURRENT_BANK = 1048.9786

STRICT = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)
SOFT_WIN = 30.0
SOFT_STEPS = 150
SOFT_WAIT = 12
SOFT_DT = 1.0
DV_CAPS = None  # set in main from kt

_KT = [None]
_CHEAP = [None]


def _init(inst, adj):
    _KT[0] = KTTSP(inst)
    _CHEAP[0] = np.load(adj)["cheap"]


def _cost_row(args):
    i, t_i = args
    kt = _KT[0]
    cheap = _CHEAP[0]
    out = []
    for j in np.where(cheap[i])[0]:
        if j == i:
            continue
        tof, dv = find_earliest_transfer(
            kt, int(i), int(j), float(t_i), kt.dv_thr, TOF_WINDOW, N_STEPS)
        out.append((int(j), int(round(tof * SCALE)) if tof is not None
                    else PENALTY))
    return int(i), out


def build_global_cost(pool, epoch, n):
    C = np.full((n, n), BIG, dtype=np.int64)
    np.fill_diagonal(C, 0)
    args = [(i, float(epoch[i])) for i in range(n)]
    t0 = time.time()
    for i, row in pool.imap_unordered(_cost_row, args, chunksize=8):
        for j, c in row:
            C[i, j] = c
    n_forbid = int((C == BIG).sum())
    print(f"  cost {n}x{n}: forbidden={n_forbid/(n*n)*100:.1f}% "
          f"wall={time.time()-t0:.0f}s", flush=True)
    return C


def solve_global_open(C, start_idx, time_limit_s, seed_order):
    m = C.shape[0]
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, :] = BIG
    D[:, depot] = 0
    D[depot, depot] = 0
    D[depot, start_idx] = 0
    D[start_idx, depot] = BIG

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
    p.time_limit.FromSeconds(time_limit_s)

    t0 = time.time()
    routing.CloseModelWithParameters(p)
    init = routing.ReadAssignmentFromRoutes([list(seed_order)], True)
    sol = (routing.SolveFromAssignmentWithParameters(init, p)
           if init is not None else routing.SolveWithParameters(p))
    if sol is None:
        return None
    order, it = [], routing.Start(0)
    while not routing.IsEnd(it):
        node = mgr.IndexToNode(it)
        if node != depot:
            order.append(node)
        it = sol.Value(routing.NextVar(it))
    big = sum(1 for k in range(1, len(order))
              if C[order[k-1]][order[k]] >= BIG)
    print(f"  [solve] {time.time()-t0:.0f}s obj={sol.ObjectiveValue()} "
          f"big_jumps={big} len={len(order)}", flush=True)
    return order


def soft_walk(kt, perm):
    """Never rejects. Returns (times, exc_over, real_mk). exc_over = #legs
    needing dv>dv_exc (over-budget). Uses escalating dv caps + waiting."""
    cur, t = perm[0], 0.0
    times = []
    exc_over = 0
    for k in range(1, len(perm)):
        j = perm[k]
        tof = dv = None
        for cap in DV_CAPS:
            tof, dv = find_earliest_transfer(kt, cur, j, t, cap,
                                             SOFT_WIN, SOFT_STEPS)
            if tof is not None:
                break
        if tof is None:
            for w in range(1, SOFT_WAIT + 1):
                tt = t + w * SOFT_DT
                if tt >= kt.max_time:
                    break
                for cap in DV_CAPS:
                    tof, dv = find_earliest_transfer(kt, cur, j, tt, cap,
                                                     SOFT_WIN, SOFT_STEPS)
                    if tof is not None:
                        break
                if tof is not None:
                    t = tt
                    break
        if tof is None:
            tof, dv = SOFT_WIN, 1e9
        if dv > kt.dv_exc + 1e-6:
            exc_over += 1
        times.append(t)
        t += tof
        cur = j
    times.append(t)  # arrival epoch of last node
    return times, exc_over, t


def strict_walk(kt, perm):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, perm, **STRICT)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return dict(x=x, mk=float(fit[0]), feas=bool(kt.is_feasible(fit)),
                exc=exc, viols=list(fit[1:]))


def epochs_from(perm, times, n):
    ep = np.zeros(n)
    for k in range(len(perm)):
        ep[perm[k]] = times[k] if k < len(times) else times[-1]
    return ep


def main():
    global DV_CAPS
    kt = KTTSP(INST)
    DV_CAPS = [kt.dv_thr, kt.dv_exc, 3000.0, 50000.0]
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    start_node = perm0[0]

    sw = strict_walk(kt, perm0)
    print(f"[BASE] strict mk={sw['mk']:.4f} feas={sw['feas']} exc={sw['exc']}",
          flush=True)
    # seed epochs from a soft walk of the bank (== strict here, feasible)
    t0, eo0, rmk0 = soft_walk(kt, perm0)
    epoch = epochs_from(perm0, t0, n)

    best = dict(mk=sw["mk"], x=sw["x"])
    cur_order = perm0

    with mp.Pool(WORKERS, initializer=_init, initargs=(INST, ADJ)) as pool:
        for it in range(N_ITERS):
            print(f"\n===== FIXPOINT ITER {it} =====", flush=True)
            C = build_global_cost(pool, epoch, n)
            order = solve_global_open(C, start_node, TL, list(cur_order))
            if order is None or len(set(order)) != n:
                print(f"[iter {it}] bad order — stop.", flush=True)
                break
            # soft walk -> realized epochs + how-infeasible
            stimes, exc_over, real_mk = soft_walk(kt, order)
            print(f"[iter {it}] soft: real_mk={real_mk:.1f}d "
                  f"exc_over={exc_over} (budget {kt.n_exc})", flush=True)
            # strict feasibility test
            st = strict_walk(kt, order)
            if st is not None:
                print(f"[iter {it}] STRICT mk={st['mk']:.4f} feas={st['feas']} "
                      f"exc={st['exc']} viols={st['viols']}", flush=True)
                if st["feas"] and st["mk"] < best["mk"]:
                    best = dict(mk=st["mk"], x=st["x"])
                    print(f"[iter {it}] *** NEW BEST STRICT mk={best['mk']:.4f}",
                          flush=True)
            else:
                print(f"[iter {it}] strict walk REJECTED (not <=5-exc walkable)",
                      flush=True)
            epoch = epochs_from(order, stimes, n)
            cur_order = order

    print(f"\n[FINAL] best strict mk={best['mk']:.4f} (bank {CURRENT_BANK})",
          flush=True)
    fit = kt.fitness(best["x"])
    feas = bool(kt.is_feasible(fit))
    perm = [int(round(v)) for v in best["x"][2 * (n - 1):]]
    covered = len(set(perm)) == n
    json.dump([{"decisionVector": best["x"], "problem": "large",
                "challenge": CHALLENGE}], open(OUT, "w"))
    gain = ("BEATS BANK" if (feas and best["mk"] < CURRENT_BANK - 1e-6
                             and covered) else "no gain")
    print(f"[OUT] {OUT} mk={float(fit[0]):.4f} feas={feas} covered={covered} "
          f"-> {gain}", flush=True)


if __name__ == "__main__":
    main()
