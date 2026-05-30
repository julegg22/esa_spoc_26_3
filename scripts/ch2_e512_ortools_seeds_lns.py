"""E-512 — Use OR-Tools routing as seed generator + LNS each + Lambert validation.

Insight from E-511: OR-Tools routing CAN produce complete hamilton paths
(unlike our table-greedy / beam search which die on dead-ends). It uses
a metaheuristic (Guided Local Search) over the static LB cost matrix.

Strategy:
  1. Run OR-Tools with each of multiple first_solution_strategies to get
     5-8 different starting perms.
  2. Also include bank as a seed.
  3. Run LNS on each seed in parallel (each ~10 min).
  4. Validate top 1500 unique with Lambert.

If OR-Tools seeds explore new permutation regions, LNS may find better
locally-optimal mk values than the bank's 142.89 basin.
"""
from __future__ import annotations
import sys, time, json, random
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from ch2_fast_walker import fast_walk
from ch2_e509_diverse_lns import make_random_move
from ch2_e511_ortools_routing import (
    load_tables, build_static_costs,
)
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
FINE_TABLE = '/tmp/ch2_small_tcoupled_fine.npz'
_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)
    d = np.load(FINE_TABLE)
    _GLOB['cheap'] = d['cheap']
    _GLOB['exc'] = d['exc']
    _GLOB['quantum'] = float(d['t_starts'][1] - d['t_starts'][0])
    _GLOB['n_exc'] = _GLOB['kt'].n_exc
    _GLOB['n'] = _GLOB['kt'].n


def solve_routing_with_strategy(cost_exc, is_exc_only, n_exc_budget,
                                  strategy_name, time_limit_s=30):
    """Solve routing with a specific first_solution_strategy and return perm."""
    n = cost_exc.shape[0]
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
    sp.first_solution_strategy = getattr(routing_enums_pb2.FirstSolutionStrategy,
                                          strategy_name)
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    sp.time_limit.seconds = time_limit_s

    sol = routing.SolveWithParameters(sp)
    if not sol: return None
    perm = []
    idx = routing.Start(0)
    while not routing.IsEnd(idx):
        node = manager.IndexToNode(idx)
        if node != DEPOT:
            perm.append(node)
        idx = sol.Value(routing.NextVar(idx))
    return perm


def lns_worker(args):
    seed_id, start_perm, init_fmk, T_max = args
    rng = random.Random(hash(seed_id) % (2**31))
    cheap = _GLOB['cheap']; exc = _GLOB['exc']
    quantum = _GLOB['quantum']; n_exc = _GLOB['n_exc']
    walk_kwargs = {'n_exc_budget': n_exc, 'window_q': 300,
                   'exc_policy': 'cheap_unless_infeasible'}
    cur_perm = list(start_perm); cur_mk = init_fmk
    best_mk = init_fmk; best_perm = list(start_perm)
    top_perms = []
    t0 = time.time(); n_walks = n_feas = n_acc = 0
    T = 8.0; T_min = 0.3; T_decay = 0.9998
    it = 0; last_log = t0
    while time.time() - t0 < T_max:
        it += 1
        cand = make_random_move(cur_perm, rng)
        if cand == cur_perm: continue
        mk, _, _, _, ok = fast_walk(cand, cheap, exc, quantum, **walk_kwargs)
        n_walks += 1
        if not ok: continue
        n_feas += 1
        if mk < init_fmk + 30:
            top_perms.append((mk, list(cand)))
        delta = mk - cur_mk
        if delta < 0 or rng.random() < (2.718 ** (-delta / max(T, 0.1))):
            cur_mk = mk; cur_perm = cand; n_acc += 1
            if mk < best_mk: best_mk = mk; best_perm = list(cand)
        T = max(T_min, T * T_decay)
        if it > 0 and it % 8000 == 0:
            cur_perm = list(best_perm); cur_mk = best_mk; T = 8.0
        if time.time() - last_log > 90:
            elapsed = time.time() - t0
            print(f"  [{seed_id} it={it} t={elapsed:.0f}s] cur={cur_mk:.2f} "
                  f"best={best_mk:.2f} walks={n_walks} feas={n_feas} top={len(top_perms)}",
                   flush=True)
            last_log = time.time()
    print(f"  [{seed_id} DONE] best={best_mk:.2f} feas={n_feas} top={len(top_perms)}",
           flush=True)
    return seed_id, best_mk, best_perm, top_perms


def main(T_max_per_worker=900, workers=8):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE missing", flush=True); return
    kt = KTTSP(INST)
    _init()
    bank_mk = 142.8913
    cheap, exc, t_starts = load_tables()
    quantum = float(t_starts[1] - t_starts[0])
    cost_cheap, cost_exc, is_exc_only = build_static_costs(cheap, exc, quantum)
    n = kt.n

    print(f"E-512: bank={bank_mk:.4f}d", flush=True)
    print(f"\nPhase 1: OR-Tools seed generation with multiple strategies",
           flush=True)
    strategies = [
        'PATH_CHEAPEST_ARC',
        'PATH_MOST_CONSTRAINED_ARC',
        'EVALUATOR_STRATEGY',  # might fail without callback
        'SAVINGS',
        'SWEEP',
        'CHRISTOFIDES',
        'PARALLEL_CHEAPEST_INSERTION',
        'SEQUENTIAL_CHEAPEST_INSERTION',
        'LOCAL_CHEAPEST_INSERTION',
        'GLOBAL_CHEAPEST_ARC',
        'LOCAL_CHEAPEST_ARC',
        'FIRST_UNBOUND_MIN_VALUE',
    ]
    seed_perms = {}
    # Bank seed
    bank = json.load(open(OUT))
    bank_perm = [int(x) for x in bank[0]["decisionVector"][2*(n-1):]]
    seed_perms['bank'] = bank_perm
    print(f"  bank: ok ({len(bank_perm)} nodes)", flush=True)

    for strat in strategies:
        try:
            p = solve_routing_with_strategy(
                cost_exc, is_exc_only, kt.n_exc, strat, time_limit_s=20)
            if p is not None and len(p) == n:
                fmk, _, _, _, ok = fast_walk(p, cheap, exc, quantum,
                                              n_exc_budget=kt.n_exc,
                                              window_q=300,
                                              exc_policy='cheap_unless_infeasible')
                if ok:
                    seed_perms[strat] = (p, fmk)
                    print(f"  {strat}: ok fmk={fmk:.2f}d", flush=True)
                else:
                    print(f"  {strat}: ok but fast_walk infeasible", flush=True)
            else:
                print(f"  {strat}: failed (no path)", flush=True)
        except Exception as e:
            print(f"  {strat}: error {e}", flush=True)

    # Bank fmk
    bank_fmk, _, _, _, _ = fast_walk(bank_perm, cheap, exc, quantum,
                                      n_exc_budget=kt.n_exc, window_q=300,
                                      exc_policy='cheap_unless_infeasible')
    print(f"  bank fmk = {bank_fmk:.2f}d", flush=True)

    # Build args list — pick distinct seed perms
    args = []
    args.append(('bank', bank_perm, bank_fmk, T_max_per_worker))
    for strat, (p, fmk) in seed_perms.items():
        if strat == 'bank': continue
        if tuple(p) == tuple(bank_perm): continue
        args.append((strat, p, fmk, T_max_per_worker))
    args = args[:workers]
    print(f"\nUsing {len(args)} seeds for LNS:", flush=True)
    for sid, _, fmk, _ in args:
        print(f"  {sid}: fmk={fmk:.2f}", flush=True)

    # Phase 2: LNS
    print(f"\nPhase 2: LNS ({T_max_per_worker}s each, {len(args)} workers)",
           flush=True)
    t0 = time.time()
    all_top = []
    best_overall = (1e9, None)
    with mp.Pool(len(args), initializer=_init) as p:
        for sid, mk, perm, tops in p.imap_unordered(lns_worker, args):
            all_top.extend(tops)
            if mk < best_overall[0]:
                best_overall = (mk, perm)
    print(f"\nLNS done in {time.time()-t0:.0f}s. all_top: {len(all_top)}",
           flush=True)
    # Dedup
    seen = set(); uniq = []
    for mk, p in sorted(all_top, key=lambda x: x[0]):
        key = tuple(p)
        if key in seen: continue
        seen.add(key); uniq.append((mk, p))
    print(f"Unique: {len(uniq)}", flush=True)

    # Phase 3: Validate top 2000 with Lambert
    K = min(2000, len(uniq))
    print(f"\nPhase 3: Lambert validation top {K}", flush=True)
    best_lambert = None
    t_val = time.time(); last_print = t_val
    for ix, (fmk, perm) in enumerate(uniq[:K]):
        best_for_perm = None
        for ns, ws, wd in [(180, 12, 1.0), (360, 60, 0.2)]:
            times, tofs, _, ok, _, _ = walk_perm_chrono(
                kt, perm, tof_window=18.0, n_steps=ns,
                wait_steps=ws, wait_dt=wd)
            if not ok: continue
            mk_l = times[-1] + tofs[-1]
            x = times + tofs + [float(p) for p in perm]
            fit = kt.fitness(x)
            if kt.is_feasible(fit):
                if best_for_perm is None or mk_l < best_for_perm[0]:
                    best_for_perm = (mk_l, x)
        if best_for_perm is None: continue
        if best_lambert is None or best_for_perm[0] < best_lambert[0]:
            best_lambert = best_for_perm
            mark = ""
            if best_for_perm[0] < bank_mk: mark = " UNDER BANK"
            if best_for_perm[0] < 111.76: mark += " UNDER R3"
            if best_for_perm[0] < 101.65: mark += " UNDER R1"
            print(f"  [{ix:4d}] fmk={fmk:.2f} → lambert={best_for_perm[0]:.4f}d{mark}",
                   flush=True)
        if time.time() - last_print > 60:
            print(f"  ... [{ix}/{K}] best={best_lambert[0]:.4f}", flush=True)
            last_print = time.time()
    print(f"\nValidation wall: {time.time()-t_val:.0f}s", flush=True)

    if best_lambert and best_lambert[0] < bank_mk:
        bak = OUT + ".bak.20260530.e512"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_lambert[1]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_lambert[0]:.4f}d "
              f"({bank_mk - best_lambert[0]:.4f}d under prev)", flush=True)


if __name__ == "__main__":
    tw = int(sys.argv[1]) if len(sys.argv) > 1 else 900
    main(T_max_per_worker=tw)
