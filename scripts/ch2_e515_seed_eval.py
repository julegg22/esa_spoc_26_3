"""E-515 — Mass OR-Tools seed evaluation under wider Lambert sweep.

For each (strategy, metaheuristic, seed_perturb), generate a hamilton
path via OR-Tools routing. Then Lambert-evaluate with 6 different
parameter configs. Track the best mk per perm; bank if any beats 142.89.

Properly written script (not heredoc) with line-buffered stdout.
"""
from __future__ import annotations
import sys, time, json
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from ch2_e511_ortools_routing import build_static_costs
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from pathlib import Path

# Force line-buffered output
sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
FINE_TABLE = '/tmp/ch2_small_tcoupled_fine.npz'


def or_tools_solve(cost_exc, is_exc_only, n, n_exc_budget,
                    strategy, time_limit=10,
                    metaheuristic='GUIDED_LOCAL_SEARCH'):
    DEPOT = n
    manager = pywrapcp.RoutingIndexManager(n + 1, 1, DEPOT)
    routing = pywrapcp.RoutingModel(manager)
    def transit(i_idx, j_idx):
        i = manager.IndexToNode(i_idx); j = manager.IndexToNode(j_idx)
        if i == DEPOT or j == DEPOT: return 0
        return int(cost_exc[i, j])
    tcb = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(tcb)
    def exc_cb(i_idx, j_idx):
        i = manager.IndexToNode(i_idx); j = manager.IndexToNode(j_idx)
        if i == DEPOT or j == DEPOT: return 0
        return int(is_exc_only[i, j])
    ecb = routing.RegisterTransitCallback(exc_cb)
    routing.AddDimensionWithVehicleCapacity(ecb, 0, [n_exc_budget], True, 'Exception')
    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = getattr(
        routing_enums_pb2.FirstSolutionStrategy, strategy)
    sp.local_search_metaheuristic = getattr(
        routing_enums_pb2.LocalSearchMetaheuristic, metaheuristic)
    sp.time_limit.seconds = time_limit
    sol = routing.SolveWithParameters(sp)
    if not sol: return None
    perm = []; idx = routing.Start(0)
    while not routing.IsEnd(idx):
        node = manager.IndexToNode(idx)
        if node != DEPOT: perm.append(node)
        idx = sol.Value(routing.NextVar(idx))
    return perm


def lambert_eval(kt, perm, configs):
    best = None
    best_x = None
    for ns, ws, wd, tw in configs:
        try:
            times, tofs, _, ok, exc_used, _ = walk_perm_chrono(
                kt, perm, tof_window=tw, n_steps=ns,
                wait_steps=ws, wait_dt=wd)
        except Exception:
            continue
        if not ok: continue
        mk = times[-1] + tofs[-1]
        x = times + tofs + [float(p) for p in perm]
        fit = kt.fitness(x)
        if kt.is_feasible(fit):
            if best is None or mk < best:
                best = mk
                best_x = x
    return best, best_x


def main():
    kt = KTTSP(INST)
    d = np.load(FINE_TABLE)
    cheap, exc, t_starts = d['cheap'], d['exc'], d['t_starts']
    quantum = float(t_starts[1] - t_starts[0])
    cost_cheap, cost_exc, is_exc_only = build_static_costs(cheap, exc, quantum)
    n = kt.n
    bank_mk = 142.8913

    configs = [
        (180, 12, 1.0, 18.0),
        (360, 60, 0.2, 18.0),
        (180, 24, 0.5, 24.0),
        (240, 30, 0.5, 30.0),
        (480, 200, 0.05, 18.0),
        (240, 100, 0.1, 24.0),
    ]
    strategies = ['PATH_CHEAPEST_ARC', 'PATH_MOST_CONSTRAINED_ARC', 'SAVINGS',
                  'CHRISTOFIDES', 'PARALLEL_CHEAPEST_INSERTION',
                  'SEQUENTIAL_CHEAPEST_INSERTION', 'LOCAL_CHEAPEST_INSERTION',
                  'GLOBAL_CHEAPEST_ARC', 'LOCAL_CHEAPEST_ARC',
                  'FIRST_UNBOUND_MIN_VALUE']
    # Skip TABU_SEARCH (slow). Use GREEDY_DESCENT in addition to GLS.
    metas = ['GUIDED_LOCAL_SEARCH', 'GREEDY_DESCENT']

    print(f"E-515: bank_mk={bank_mk:.4f}", flush=True)
    print(f"Strategies: {len(strategies)}  Metas: {len(metas)}  "
          f"Configs: {len(configs)}", flush=True)
    print(f"Expected: {len(strategies)*len(metas)} OR-Tools solves × 10s "
          f"+ Lambert evals", flush=True)
    t0 = time.time()
    results = []
    for strat in strategies:
        for meta in metas:
            t_or = time.time()
            try:
                p = or_tools_solve(cost_exc, is_exc_only, n, kt.n_exc,
                                   strat, time_limit=10, metaheuristic=meta)
            except Exception as e:
                print(f"  {strat}/{meta}: OR error: {e}", flush=True)
                continue
            wall_or = time.time() - t_or
            if p is None or len(p) != n:
                print(f"  {strat}/{meta}: OR no perm ({wall_or:.0f}s)",
                       flush=True)
                continue
            t_l = time.time()
            mk, x = lambert_eval(kt, p, configs)
            wall_l = time.time() - t_l
            if mk is None:
                print(f"  {strat:30s}/{meta:18s}: OR{wall_or:.0f}s "
                      f"INFEASIBLE under all configs ({wall_l:.0f}s)",
                       flush=True)
            else:
                mark = ""
                if mk < bank_mk: mark = " UNDER BANK"
                if mk < 111.76: mark += " UNDER R3"
                if mk < 101.65: mark += " UNDER R1"
                print(f"  {strat:30s}/{meta:18s}: OR{wall_or:.0f}s "
                      f"mk={mk:.4f}d{mark} ({wall_l:.0f}s)", flush=True)
                results.append((mk, p, x))
    wall = time.time() - t0
    print(f"\nWall: {wall:.0f}s. {len(results)} feasible perms", flush=True)
    if results:
        results.sort(key=lambda r: r[0])
        print(f"Best mk: {results[0][0]:.4f}d (bank=142.89d)",
               flush=True)
        for ix, (mk, p, _x) in enumerate(results[:5]):
            print(f"  {ix}: mk={mk:.4f}  perm[:10]={p[:10]}", flush=True)
        if results[0][0] < bank_mk:
            bak = OUT + ".bak.20260530.e515"
            if Path(OUT).exists() and not Path(bak).exists():
                Path(bak).write_bytes(Path(OUT).read_bytes())
            Path(OUT).write_text(json.dumps([{
                "decisionVector": list(results[0][2]),
                "problem": "small",
                "challenge": CHALLENGE}]))
            print(f">>> BANKED: mk={results[0][0]:.4f}d "
                  f"({bank_mk - results[0][0]:.4f}d under prev)", flush=True)


if __name__ == "__main__":
    main()
