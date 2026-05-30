"""E-514 — GA with FULL LAMBERT fitness for Ch2 small.

E-513 found: fast-walker fitness is too restrictive — all random / OR-Tools
seeds get fmk=infeasible. GA converges to bank basin trivially.

E-514 uses walk_perm_chrono (full Lambert) as fitness. Slower per eval
(~4s) but accepts MANY more perms. With multiple parameter configs
per eval, can recover good Lambert mk even for perms fast walker rejects.

Compute budget:
  - 1 walk = 1s × 2 configs = 2s per fitness eval
  - 8 workers × 60 min × 30 evals/min = ~14k evals total
  - Small population GA: pop=30, ~500 generations of steady-state
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
from ch2_e513_ga_ox import ox1_crossover, mutate, tournament_select
from ch2_e511_ortools_routing import build_static_costs, load_tables

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


def lambert_fitness(perm):
    """Full Lambert walk with 2 param configs, return best feasible mk."""
    kt = _GLOB['kt']
    best = None
    best_x = None
    for ns, ws, wd in [(180, 12, 1.0), (360, 60, 0.2)]:
        times, tofs, _, ok, _, _ = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=ns, wait_steps=ws, wait_dt=wd)
        if not ok: continue
        mk = times[-1] + tofs[-1]
        x = times + tofs + [float(p) for p in perm]
        fit = kt.fitness(x)
        if kt.is_feasible(fit):
            if best is None or mk < best:
                best = mk
                best_x = x
    return (best, best_x) if best is not None else (1e9, None)


def get_ortools_diverse_seeds(n, cheap, exc, quantum, n_exc_budget):
    """Reuse from E-513."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    cost_cheap, cost_exc, is_exc_only = build_static_costs(cheap, exc, quantum)
    DEPOT = n
    seeds = []
    strategies = ['PATH_CHEAPEST_ARC', 'PATH_MOST_CONSTRAINED_ARC', 'SAVINGS',
                  'CHRISTOFIDES', 'PARALLEL_CHEAPEST_INSERTION',
                  'SEQUENTIAL_CHEAPEST_INSERTION', 'LOCAL_CHEAPEST_INSERTION',
                  'GLOBAL_CHEAPEST_ARC', 'LOCAL_CHEAPEST_ARC',
                  'FIRST_UNBOUND_MIN_VALUE']
    for strat in strategies:
        try:
            manager = pywrapcp.RoutingIndexManager(n + 1, 1, DEPOT)
            routing = pywrapcp.RoutingModel(manager)
            def transit(i_idx, j_idx, mgr=manager):
                i = mgr.IndexToNode(i_idx); j = mgr.IndexToNode(j_idx)
                if i == DEPOT or j == DEPOT: return 0
                return int(cost_exc[i, j])
            tcb = routing.RegisterTransitCallback(transit)
            routing.SetArcCostEvaluatorOfAllVehicles(tcb)
            def exc_cb(i_idx, j_idx, mgr=manager):
                i = mgr.IndexToNode(i_idx); j = mgr.IndexToNode(j_idx)
                if i == DEPOT or j == DEPOT: return 0
                return int(is_exc_only[i, j])
            ecb = routing.RegisterTransitCallback(exc_cb)
            routing.AddDimensionWithVehicleCapacity(
                ecb, 0, [n_exc_budget], True, 'Exception')
            sp = pywrapcp.DefaultRoutingSearchParameters()
            sp.first_solution_strategy = getattr(
                routing_enums_pb2.FirstSolutionStrategy, strat)
            sp.time_limit.seconds = 5
            sol = routing.SolveWithParameters(sp)
            if not sol: continue
            perm = []
            idx = routing.Start(0)
            while not routing.IsEnd(idx):
                node = manager.IndexToNode(idx)
                if node != DEPOT: perm.append(node)
                idx = sol.Value(routing.NextVar(idx))
            if len(perm) == n:
                seeds.append(perm)
        except Exception:
            pass
    return seeds


def init_population(pop_size, bank_perm, n, rng, extra_seeds=None):
    pop = [list(bank_perm)]
    while len(pop) < pop_size // 3:
        p = list(bank_perm)
        for _ in range(rng.randint(3, 10)):
            p = mutate(p, rng)
        pop.append(p)
    if extra_seeds:
        for s in extra_seeds:
            if len(pop) >= 2 * pop_size // 3: break
            pop.append(list(s))
    while len(pop) < pop_size:
        p = list(range(n)); rng.shuffle(p)
        pop.append(p)
    return pop


def ga_island_lambert(args):
    island_id, pop_size, T_max, init_seed_perm, extra_seeds = args
    rng = random.Random(island_id * 1000 + 7)
    n = _GLOB['n']
    pop = init_population(pop_size, init_seed_perm, n, rng, extra_seeds)
    pop_fit_and_x = [lambert_fitness(p) for p in pop]
    pop_fitness = [f[0] for f in pop_fit_and_x]
    n_feas_init = sum(1 for f in pop_fitness if f < 1e8)
    print(f"  [is={island_id}] init pop={pop_size} feas={n_feas_init} "
          f"best={min(pop_fitness):.2f}", flush=True)

    best_idx = int(np.argmin(pop_fitness))
    best_perm = list(pop[best_idx])
    best_fit = pop_fitness[best_idx]
    best_x = pop_fit_and_x[best_idx][1]
    all_seen = {}
    for p, (f, x) in zip(pop, pop_fit_and_x):
        if f < 1e8:
            all_seen[tuple(p)] = (f, x)

    t0 = time.time()
    gen = 0; last_log = t0
    while time.time() - t0 < T_max:
        gen += 1
        i = tournament_select(pop_fitness, 3, rng)
        j = tournament_select(pop_fitness, 3, rng)
        while j == i:
            j = tournament_select(pop_fitness, 3, rng)
        if rng.random() < 0.7:
            child = ox1_crossover(pop[i], pop[j], rng)
        else:
            child = list(pop[i])
        if rng.random() < 0.4:
            for _ in range(rng.randint(1, 3)):
                child = mutate(child, rng)
        cf, cx = lambert_fitness(child)
        if cf < 1e8:
            all_seen[tuple(child)] = (cf, cx)
        # Replace worst in 4-sample tournament
        rs = rng.sample(range(len(pop)), 4)
        worst = max(rs, key=lambda k: pop_fitness[k])
        if cf < pop_fitness[worst]:
            pop[worst] = child
            pop_fit_and_x[worst] = (cf, cx)
            pop_fitness[worst] = cf
            if cf < best_fit:
                best_fit = cf; best_perm = list(child); best_x = cx
        if gen % 100 == 0 and time.time() - last_log > 60:
            pf = [f for f in pop_fitness if f < 1e8]
            avg = sum(pf) / max(len(pf), 1)
            print(f"  [is={island_id} gen={gen} t={time.time()-t0:.0f}s] "
                  f"best={best_fit:.2f} avg={avg:.2f} feas/pop={len(pf)}/{pop_size} "
                  f"all_seen={len(all_seen)}", flush=True)
            last_log = time.time()
    print(f"  [is={island_id} DONE gen={gen}] best={best_fit:.2f} "
          f"all_seen={len(all_seen)}", flush=True)
    return island_id, best_fit, best_perm, best_x, list(all_seen.items())


def main(T_max=2400, n_islands=8, pop_size=30):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE missing", flush=True); return
    kt = KTTSP(INST)
    _init()
    bank_mk = 142.8913
    bank = json.load(open(OUT))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    print(f"E-514 GA-Lambert: bank={bank_mk:.4f}, R3=111.76, R1=101.65", flush=True)
    print(f"Islands={n_islands}, pop_size={pop_size}, T_max={T_max}s", flush=True)

    # Diverse seeds via OR-Tools
    print(f"\nGenerating OR-Tools seeds...", flush=True)
    seeds = get_ortools_diverse_seeds(
        n, _GLOB['cheap'], _GLOB['exc'], _GLOB['quantum'], kt.n_exc)
    print(f"  Got {len(seeds)} OR-Tools seeds", flush=True)

    args = [(i, pop_size, T_max, bank_perm, seeds) for i in range(n_islands)]
    t0 = time.time()
    best_overall = (1e9, None, None)
    all_x = {}
    with mp.Pool(n_islands, initializer=_init) as p:
        for island_id, best_fit, best_perm, best_x, seen in p.imap_unordered(
                ga_island_lambert, args):
            if best_fit < best_overall[0]:
                best_overall = (best_fit, best_perm, best_x)
                mark = " UNDER BANK" if best_fit < bank_mk else ""
                mark += " UNDER R3" if best_fit < 111.76 else ""
                mark += " UNDER R1" if best_fit < 101.65 else ""
                print(f"  island {island_id}: BEST mk={best_fit:.4f}{mark}",
                       flush=True)
            for p_tuple, (f, x) in seen:
                if p_tuple not in all_x or f < all_x[p_tuple][0]:
                    all_x[p_tuple] = (f, x)
    wall = time.time() - t0
    print(f"\nGA-Lambert done in {wall:.0f}s. unique={len(all_x)}", flush=True)
    print(f"Best mk: {best_overall[0]:.4f}d", flush=True)

    if best_overall[0] < bank_mk and best_overall[2] is not None:
        bak = OUT + ".bak.20260530.e514"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_overall[2]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_overall[0]:.4f}d "
              f"({bank_mk - best_overall[0]:.4f}d under prev)", flush=True)


if __name__ == "__main__":
    tm = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    ps = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    main(T_max=tm, pop_size=ps)
