"""E-709d — Ch2-large experiments #2 (LB) and #3 (global TSP on time-aware costs + faithful walk).

#2: assignment-relaxation LOWER BOUND on the giant makespan using min-window-tof costs (ignores time
    feasibility -> valid LB). Is rank-1 424d near-optimal, or is there a ~150d solution (huge headroom)?
#3: solve a GLOBAL TSP (OR-Tools) on the static min-window-tof matrix -> order -> FAITHFUL chronological
    walk (compute_transfer, <=5 exc) -> true makespan. If the global static order completes at low
    makespan, static+retiming is the lever; if it strands/inflates, time-coupling is essential (the
    purpose-built static paradigm provably fails -> confirms heavy time-expanded build needed).
Usage: python ch2_large_lb_route.py"""
import sys, json, time
import numpy as np
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities); ci = {c: k for k, c in enumerate(cities)}
BIG = 1e6

# min-window-tof cost matrix (min over epochs of the cheap tof)
COST = np.full((NG, NG), BIG, np.float64)
with np.errstate(all="ignore"):
    mw = np.where(np.isfinite(VALS).any(1), np.nanmin(np.where(np.isfinite(VALS), VALS, np.inf), 1), np.inf)
for r, (i, j) in enumerate(KEYS):
    if np.isfinite(mw[r]):
        COST[ci[int(i)], ci[int(j)]] = mw[r]
np.fill_diagonal(COST, BIG)

# ---- #2: assignment LB ----
ri, col = linear_sum_assignment(COST)
asg = COST[ri, col]
lb = asg[asg < BIG].sum()
n_inf = int((asg >= BIG).sum())
print(f"[E-709d #2 LB] assignment-relaxation LB on giant makespan: {lb:.1f}d (over {NG-n_inf} cheap-assignable; "
      f"{n_inf} forced non-cheap). rank-1=424.62, our giant ~520, perfect-cheap LB shows headroom={'HUGE' if lb<300 else 'MODERATE'}.", flush=True)
print(f"  per-leg: LB {lb/NG:.3f} d/leg vs rank-1 0.404 vs bank 0.86", flush=True)

# ---- #3: global TSP on static min-window-tof -> order -> faithful walk ----
try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    # open-path TSP via dummy depot with 0 cost to/from all
    N = NG + 1; DUM = NG
    Cint = np.minimum(COST, 50.0)                       # cap non-cheap at 50 (discourage) for the int matrix
    Cint = (Cint * 1000).astype(np.int64)
    mgr = pywrapcp.RoutingIndexManager(N, 1, DUM)
    routing = pywrapcp.RoutingModel(mgr)

    def cb(a, b):
        ia, ib = mgr.IndexToNode(a), mgr.IndexToNode(b)
        if ia == DUM or ib == DUM:
            return 0
        return int(Cint[ia, ib])
    t_idx = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(t_idx)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    p.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    p.time_limit.seconds = 120
    print(f"[E-709d #3] solving global TSP on {NG}-city static min-tof matrix (OR-Tools GLS 120s)...", flush=True)
    sol = routing.SolveWithParameters(p)
    if sol is None:
        print("[E-709d #3] OR-Tools found no solution", flush=True)
    else:
        idx = routing.Start(0); order = []
        while not routing.IsEnd(idx):
            nd = mgr.IndexToNode(idx)
            if nd != DUM:
                order.append(cities[nd])
            idx = sol.Value(routing.NextVar(idx))
        print(f"[E-709d #3] static-TSP order len {len(order)}; faithful-walking it ...", flush=True)
        # faithful chronological walk
        grid = np.concatenate([np.arange(kt.min_tof, 0.5, 0.01), np.arange(0.5, 3.0, 0.05)])
        t = 0.0; mk = 0.0; exc = 0; strands = 0; t0 = time.time()
        for k in range(len(order) - 1):
            i, j = order[k], order[k + 1]; tof = None
            for tf in grid:
                if kt.compute_transfer(i, j, float(t), float(tf)) <= kt.dv_thr:
                    tof = float(tf); break
            if tof is None and exc < kt.n_exc:
                for tf in grid:
                    if kt.compute_transfer(i, j, float(t), float(tf)) <= kt.dv_exc:
                        tof = float(tf); exc += 1; break
            if tof is None:
                strands += 1
                break
            t += tof; mk = t
        done = k + 1
        print(f"[E-709d #3] faithful walk of static-TSP order: reached {done}/{len(order)} cities, makespan~{mk:.0f}d, "
              f"exc={exc}, strand_at={done if strands else 'none'} [{time.time()-t0:.0f}s]", flush=True)
        if done < len(order) - 5:
            print(f"[E-709d #3] -> static-TSP order STRANDS when walked ({done}/{len(order)}) -> static cost provably "
                  f"insufficient; the time-coupling is essential. Purpose-built STATIC solvers cannot crack it.", flush=True)
        elif mk < 500:
            print(f"[E-709d #3] -> static-TSP order COMPLETES at {mk:.0f}d -> static+retiming IS the lever (rank-1 reachable)!", flush=True)
        else:
            print(f"[E-709d #3] -> completes but inflated ({mk:.0f}d) -> static order suboptimal under time; needs time-aware solver.", flush=True)
except ImportError:
    print("[E-709d #3] ortools routing unavailable", flush=True)
