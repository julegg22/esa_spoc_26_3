"""E-042 (script e572): Ch2 LARGE — GLOBAL epoch-aware re-route.

E-041 proved the 624d gap to r1=424d is ordering/phasing, not physical:
idle=0, and short cheap transfers (median min-tof 0.15d) are abundant at
EVERY epoch with ~37 cheap neighbors/node. The 4-component decomposition
(E-559..E-562b) is a STATIC-snapshot artifact; E-562b froze topology and
plateaued at 1048d.

This drops the decomposition: a SINGLE global epoch-aware open-path solve
over all 1051 nodes. Seed from the current 1048 order, build a global
epoch-aware cost (find_earliest_transfer at each node's walk-epoch over
its static-cheap candidates), one global GLS open-path solve (long
budget), re-walk -> fresh epochs, iterate. The global solve can re-route
across the rich epoch-dependent connectivity that the frozen pieces
could not.

GUARDED: writes candidate to /tmp ONLY; banks NOTHING. (Banking is a
separate verified step by the operator.)
"""
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

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
OUT = "/tmp/ch2_large_global_candidate.json"

BIG = 10_000_000          # truly non-cheap (forbidden) edge
PENALTY = 60_000          # cheap-candidate but no feasible tof at this epoch
SCALE = 1000.0            # tof(days) -> int cost
TOF_WINDOW = float(os.environ.get("E572_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E572_NSTEPS", "120"))
N_ITERS = int(os.environ.get("E572_NITERS", "6"))
STOP_DELTA = float(os.environ.get("E572_STOP", "5.0"))
TL = int(os.environ.get("E572_TL", "1200"))          # OR-Tools secs / iter
WORKERS = int(os.environ.get("E572_WORKERS", "4"))
CURRENT_BANK = 1048.9786

# Walk params identical to E-562b so epochs reproduce the banked walk.
WALK = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)

_KT = [None]
_CHEAP = [None]


def _init(inst, adj):
    _KT[0] = KTTSP(inst)
    _CHEAP[0] = np.load(adj)["cheap"]


def _cost_row(args):
    """Epoch-aware cost row for source node i (global id) at epoch t_i.
    Returns (i, [(j, cost_int), ...]) over i's static-cheap candidates."""
    i, t_i = args
    kt = _KT[0]
    cheap = _CHEAP[0]
    out = []
    for j in np.where(cheap[i])[0]:
        if j == i:
            continue
        tof, dv = find_earliest_transfer(
            kt, int(i), int(j), float(t_i), kt.dv_thr, TOF_WINDOW, N_STEPS)
        if tof is not None:
            out.append((int(j), int(round(tof * SCALE))))
        else:
            out.append((int(j), PENALTY))
    return int(i), out


def build_global_cost(pool, epoch, n):
    """Full n x n epoch-aware cost (BIG default). epoch: array global->day."""
    C = np.full((n, n), BIG, dtype=np.int64)
    np.fill_diagonal(C, 0)
    args = [(i, float(epoch[i])) for i in range(n)]
    t0 = time.time()
    n_pen = 0
    done = 0
    for i, row in pool.imap_unordered(_cost_row, args, chunksize=8):
        for j, c in row:
            C[i, j] = c
            if c == PENALTY:
                n_pen += 1
        done += 1
        if done % 200 == 0:
            print(f"    cost {done}/{n} ({time.time()-t0:.0f}s)", flush=True)
    n_forbid = int((C == BIG).sum())
    print(f"  global cost {n}x{n}: forbidden={n_forbid} "
          f"({n_forbid/(n*n)*100:.1f}%) pen={n_pen} "
          f"wall={time.time()-t0:.0f}s", flush=True)
    return C


def solve_global_open(C, start_idx, time_limit_s, seed_order):
    """Open Hamilton path, fixed start, free end. Seeded with seed_order."""
    m = C.shape[0]
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, :] = BIG
    D[:, depot] = 0            # free end: any node -> depot costs 0
    D[depot, depot] = 0
    D[depot, start_idx] = 0    # path must start at start_idx
    D[start_idx, depot] = BIG  # ...and not immediately end

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
    p.log_search = False

    t0 = time.time()
    routing.CloseModelWithParameters(p)
    init = routing.ReadAssignmentFromRoutes([list(seed_order)], True)
    if init is None:
        print("  [global] seed REJECTED — cold solve", flush=True)
        sol = routing.SolveWithParameters(p)
    else:
        sol = routing.SolveFromAssignmentWithParameters(init, p)
    if sol is None:
        print("  [global] NO SOLUTION", flush=True)
        return None
    order, it = [], routing.Start(0)
    while not routing.IsEnd(it):
        node = mgr.IndexToNode(it)
        if node != depot:
            order.append(node)
        it = sol.Value(routing.NextVar(it))
    big = pen = 0
    csum = 0
    for k in range(1, len(order)):
        c = C[order[k - 1]][order[k]]
        if c >= BIG:
            big += 1
        elif c >= PENALTY:
            pen += 1
        else:
            csum += c
    print(f"  [global] {time.time()-t0:.0f}s obj={sol.ObjectiveValue()} "
          f"path~{csum/SCALE:.1f}d big_jumps={big} pen_used={pen} "
          f"len={len(order)} start={order[0]} end={order[-1]}", flush=True)
    return order


def walk_stats(kt, full):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, full, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in full]
    fit = kt.fitness(x)
    return dict(times=times, tofs=tofs, x=x, fit=fit,
                feas=bool(kt.is_feasible(fit)), mk=float(fit[0]),
                exc=exc, ok=ok)


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    start_node = perm0[0]

    w0 = walk_stats(kt, perm0)
    print(f"[BASE] mk={w0['mk']:.4f} feas={w0['feas']} exc={w0['exc']} "
          f"start={start_node}", flush=True)

    best_mk = w0["mk"]
    best_x = w0["x"]
    cur_order = perm0
    epoch = np.zeros(n)
    for k in range(len(w0["times"])):
        epoch[perm0[k]] = w0["times"][k]
    epoch[perm0[-1]] = w0["times"][-1]
    prev_mk = w0["mk"]

    with mp.Pool(WORKERS, initializer=_init, initargs=(INST, ADJ)) as pool:
        for it in range(N_ITERS):
            print(f"\n===== GLOBAL EPOCH-AWARE ITER {it} =====", flush=True)
            C = build_global_cost(pool, epoch, n)
            # position-in-order index list for the seed (depot handled inside)
            seed_idx = list(cur_order)
            order = solve_global_open(C, start_node, TL, seed_idx)
            if order is None or len(set(order)) != n:
                print(f"[iter {it}] bad order — stop.", flush=True)
                break
            w = walk_stats(kt, order)
            if w is None:
                print(f"[iter {it}] walk REJECTED (infeasible order) — "
                      f"keep previous, stop.", flush=True)
                break
            tof = np.array(w["tofs"])
            print(f"[iter {it}] mk={w['mk']:.4f} feas={w['feas']} exc={w['exc']} "
                  f"viols={list(w['fit'][1:])} tof_sum={tof.sum():.1f} "
                  f">0.5d={int((tof>0.5).sum())}", flush=True)
            if w["feas"] and w["mk"] < best_mk:
                best_mk = w["mk"]
                best_x = w["x"]
                print(f"[iter {it}] NEW BEST mk={best_mk:.4f}", flush=True)
            improve = prev_mk - w["mk"]
            print(f"[iter {it}] improvement vs prev = {improve:.2f}d", flush=True)
            # refresh epochs from this walk for the next iteration
            epoch = np.zeros(n)
            for k in range(len(w["times"])):
                epoch[order[k]] = w["times"][k]
            epoch[order[-1]] = w["times"][-1]
            cur_order = order
            prev_mk = w["mk"]
            if w["feas"] and 0 <= improve < STOP_DELTA:
                print(f"[iter {it}] <{STOP_DELTA}d improvement — stop.",
                      flush=True)
                break

    print(f"\n[FINAL] best_mk={best_mk:.4f} (bank {CURRENT_BANK})", flush=True)
    fit = kt.fitness(best_x)
    feas = bool(kt.is_feasible(fit))
    perm = [int(round(v)) for v in best_x[2 * (n - 1):]]
    covered = len(set(perm)) == n
    json.dump([{"decisionVector": best_x, "problem": "large",
                "challenge": CHALLENGE}], open(OUT, "w"))
    gain = "BEATS BANK" if (feas and best_mk < CURRENT_BANK - 1e-6
                            and covered) else "no gain"
    print(f"[OUT] {OUT} mk={float(fit[0]):.4f} feas={feas} covered={covered} "
          f"viols={list(fit[1:])} -> {gain}", flush=True)


if __name__ == "__main__":
    main()
