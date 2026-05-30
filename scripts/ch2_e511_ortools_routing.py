"""E-511 — OR-Tools Routing solver for Ch2 small.

Approach:
  Build a directed weighted graph from the fine edge table. For each
  (i, j) pair, edge cost = min over t_starts of (t_start + tof) — i.e.,
  the earliest-arrival edge cost ASSUMING we can pick the optimal
  t_start (LB-style relaxation).

  Use OR-Tools RoutingModel to find a hamilton path minimizing total
  "earliest arrival" cost. Add a separate dimension to track the
  exception count (≤5). Use a dummy depot to make it a path (not cycle).

  After solving, re-walk the resulting perm chronologically with full
  Lambert to get the actual makespan. If improvement, bank.

Iterate (Bender's-style): if the Lambert walk shows a leg's actual
arrival much exceeds the routing-cost optimal, the time-coupling is
violated. We could refine costs and resolve, but for a first prototype
we just take the routing result + Lambert walk.

NOTE: routing-cost is a LOOSE lower bound on actual makespan. Routing
solver may find very-low-cost paths that walk to high makespans under
chronology. This is by design — we explore the structural perm space.
"""
from __future__ import annotations
import sys, time, json
import numpy as np
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
FINE_TABLE = '/tmp/ch2_small_tcoupled_fine.npz'


def load_tables():
    d = np.load(FINE_TABLE)
    return d['cheap'], d['exc'], d['t_starts']


def build_static_costs(cheap, exc, quantum):
    """For each (i, j), compute the LB cost: min over t_starts of (t_q + tof).

    Returns:
      cost_cheap[i, j] = LB tof using only cheap (in quanta, or BIG_INF)
      cost_exc[i, j]   = LB tof using cheap+exc (in quanta, or BIG_INF)
      is_exc_only[i, j] = True if no cheap feasibility at all
    """
    n = cheap.shape[0]
    T = cheap.shape[2]
    BIG = 10**9
    cost_cheap = np.full((n, n), BIG, dtype=np.int64)
    cost_exc = np.full((n, n), BIG, dtype=np.int64)
    is_exc_only = np.zeros((n, n), dtype=bool)
    for i in range(n):
        for j in range(n):
            if i == j: continue
            # Min over t_q of (t_q + tof_q) where tof_q = ceil(tof/quantum)
            cs = cheap[i, j]
            cs_q = np.where(np.isfinite(cs), np.ceil(cs / quantum), np.inf)
            arr_cheap = np.arange(T) + cs_q
            min_arr_cheap = arr_cheap.min()
            es = exc[i, j]
            es_q = np.where(np.isfinite(es), np.ceil(es / quantum), np.inf)
            arr_exc = np.arange(T) + es_q
            min_arr_exc = arr_exc.min()
            if np.isfinite(min_arr_cheap):
                cost_cheap[i, j] = int(min_arr_cheap)
            if np.isfinite(min_arr_exc):
                cost_exc[i, j] = int(min_arr_exc)
            if not np.isfinite(min_arr_cheap) and np.isfinite(min_arr_exc):
                is_exc_only[i, j] = True
    return cost_cheap, cost_exc, is_exc_only


def solve_routing(cost_cheap, cost_exc, is_exc_only, n_exc_budget=5,
                  time_limit_s=120):
    """Build OR-Tools RoutingModel and solve.

    Model:
      - n+1 nodes (n original + dummy depot)
      - Vehicle starts and ends at depot
      - Arc cost = cost_cheap (preferred); use cost_exc as fallback but
        ALLOW up to n_exc_budget exception arcs via a "Exception" dimension.
      - Minimize total arc cost (LB on makespan).
    """
    n = cost_cheap.shape[0]
    BIG = 10**9
    DEPOT = n  # dummy depot index in routing
    n_routing = n + 1

    manager = pywrapcp.RoutingIndexManager(n_routing, 1, DEPOT)
    routing = pywrapcp.RoutingModel(manager)

    # Choose: use exc-allowing cost matrix (any pair with exc-only is via exc; cost = cost_exc)
    # We'll use cost_exc (which is min(cheap, exc)) as the actual cost
    # And use is_exc_only to determine which arcs count toward exception
    def transit(i_idx, j_idx):
        i = manager.IndexToNode(i_idx)
        j = manager.IndexToNode(j_idx)
        if i == DEPOT or j == DEPOT:
            return 0  # depot has zero cost (path enters/exits free)
        return int(cost_exc[i, j])

    transit_cb = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    # Exception dimension: increments by 1 when using exc-only arc
    def exc_cb(i_idx, j_idx):
        i = manager.IndexToNode(i_idx)
        j = manager.IndexToNode(j_idx)
        if i == DEPOT or j == DEPOT:
            return 0
        # Count an exception if cheap is BIG (unreachable cheap) OR if the
        # cost we use is strictly via exc — for simplicity, count if cheap=BIG
        return int(is_exc_only[i, j])
    exc_callback = routing.RegisterTransitCallback(exc_cb)
    routing.AddDimensionWithVehicleCapacity(
        exc_callback, 0, [n_exc_budget], True, 'Exception')

    # Search params
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_params.time_limit.seconds = time_limit_s
    search_params.log_search = True

    print(f"Solving routing with {time_limit_s}s limit...", flush=True)
    t0 = time.time()
    solution = routing.SolveWithParameters(search_params)
    wall = time.time() - t0
    print(f"Solver done in {wall:.0f}s", flush=True)

    if not solution:
        print("No solution found", flush=True)
        return None

    # Extract path
    path = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index)
        if node != DEPOT:
            path.append(node)
        index = solution.Value(routing.NextVar(index))
    print(f"Path: {path}", flush=True)
    return path, solution.ObjectiveValue()


def main(time_limit_s=120):
    kt = KTTSP(INST)
    cheap, exc, t_starts = load_tables()
    quantum = float(t_starts[1] - t_starts[0])
    print(f"Loaded fine table: T={cheap.shape[2]}, quantum={quantum}d",
           flush=True)

    cost_cheap, cost_exc, is_exc_only = build_static_costs(cheap, exc, quantum)
    print(f"Cost matrix built. Cheap-only edges: "
          f"{((cost_cheap < 10**9) & ~is_exc_only).sum()}, "
          f"exc-only edges: {is_exc_only.sum()}",
           flush=True)

    res = solve_routing(cost_cheap, cost_exc, is_exc_only,
                        n_exc_budget=kt.n_exc, time_limit_s=time_limit_s)
    if res is None:
        return
    perm, obj = res
    print(f"\nRouting objective (LB-cost): {obj} quanta = {obj * quantum:.3f} d",
           flush=True)
    print(f"Path length: {len(perm)} (expected {kt.n})", flush=True)

    if len(perm) != kt.n:
        print(f"WARN: incomplete path", flush=True)
        return

    # Re-walk with full Lambert
    print(f"\n--- Lambert validation of routing path ---", flush=True)
    bank_mk = 142.8913
    best = None
    for ns, ws, wd in [(180, 12, 1.0), (360, 60, 0.2), (480, 200, 0.05)]:
        times, tofs, _dv, ok, _exc, _k = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=ns, wait_steps=ws, wait_dt=wd)
        if not ok:
            print(f"  ns={ns} wd={wd}: INFEASIBLE", flush=True)
            continue
        mk_l = times[-1] + tofs[-1]
        x = times + tofs + [float(p) for p in perm]
        fit = kt.fitness(x)
        feas = kt.is_feasible(fit)
        mark = ""
        if feas:
            if mk_l < bank_mk: mark = " UNDER BANK"
            if mk_l < 111.76: mark += " UNDER R3"
            if mk_l < 101.65: mark += " UNDER R1"
        print(f"  ns={ns} wd={wd}: mk={mk_l:.4f}d feas={feas}{mark}",
               flush=True)
        if feas and (best is None or mk_l < best[0]):
            best = (mk_l, x)

    if best and best[0] < bank_mk:
        bak = OUT + ".bak.20260530.e511"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best[1]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best[0]:.4f}d "
              f"({bank_mk - best[0]:.4f}d under prev)", flush=True)
    else:
        print(f"\n(Routing path didn't beat bank under Lambert.)", flush=True)
    return perm, best


if __name__ == "__main__":
    tl = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    res = main(time_limit_s=tl)
    print(json.dumps({"completed": res is not None}, indent=2))
