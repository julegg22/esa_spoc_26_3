"""E-513 — Population GA with Order Crossover for Ch2 small.

The key primitive we've been missing: CROSSOVER between perms.

Our LNS used only mutation (2-opt, or-opt, swap, double-bridge) — these
explore a small neighborhood of one parent. GA crossover (OX1) takes
chunks from TWO parents to produce children in genuinely new perm
regions, allowing escape from local-opt basins.

Architecture:
  - Population of N (e.g., 100) perms
  - Each perm scored by fast_walker (cheap, ~3000/s/worker)
  - Each generation:
    - Tournament select parents
    - Order crossover (OX1) to produce children
    - Mutation: random 2-opt or or-opt with low rate (10%)
    - Replace worst N/2 of population with children
  - Island model: K parallel populations, periodic migration

Time-budget: 30-60 min for a smoke test; if promising, run for hours.
Output: top-K perms validated with Lambert; bank if any beats 142.89.
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


def fitness(perm):
    """Return makespan via fast walker (INF if infeasible)."""
    res = fast_walk(perm, _GLOB['cheap'], _GLOB['exc'], _GLOB['quantum'],
                    n_exc_budget=_GLOB['n_exc'], window_q=300,
                    exc_policy='cheap_unless_infeasible')
    if not res[4]:
        return 1e9
    return res[0]


def ox1_crossover(p1, p2, rng):
    """Order Crossover (OX1).

    1. Pick random cut positions [a, b)
    2. Child = parent1[a:b] in same positions
    3. Fill remaining positions with parent2's elements in order, skipping
       those already in child.
    """
    n = len(p1)
    a = rng.randint(1, n - 2)
    b = rng.randint(a + 1, n - 1)
    middle = p1[a:b]
    middle_set = set(middle)
    # Walk p2 starting after b, wrap around
    fill = []
    for idx in list(range(b, n)) + list(range(0, b)):
        v = p2[idx]
        if v not in middle_set:
            fill.append(v)
    # Place fill[:n-b] after b, fill[n-b:n-b+a] before a
    child = [None] * n
    child[a:b] = middle
    f_idx = 0
    for i in list(range(b, n)) + list(range(0, a)):
        child[i] = fill[f_idx]
        f_idx += 1
    return child


def mutate(perm, rng):
    """Random 2-opt or or-opt with low rate."""
    n = len(perm)
    mv = rng.choice(['2opt', 'or_opt_1', 'or_opt_2', 'swap'])
    if mv == '2opt':
        i = rng.randint(1, n - 3); j = rng.randint(i + 1, n - 2)
        return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]
    elif mv == 'or_opt_1':
        i = rng.randint(1, n - 2)
        seg = [perm[i]]
        rest = perm[:i] + perm[i+1:]
        p = rng.randint(1, len(rest))
        return rest[:p] + seg + rest[p:]
    elif mv == 'or_opt_2':
        if n < 5: return perm
        i = rng.randint(1, n - 3)
        seg = perm[i:i+2]
        rest = perm[:i] + perm[i+2:]
        p = rng.randint(1, len(rest))
        return rest[:p] + seg + rest[p:]
    elif mv == 'swap':
        i = rng.randint(1, n - 2); j = rng.randint(1, n - 2)
        if i == j: return perm
        new = list(perm); new[i], new[j] = new[j], new[i]; return new
    return perm


def tournament_select(pop_fitness, k, rng):
    """Tournament selection: pick k random, return best."""
    idxs = rng.sample(range(len(pop_fitness)), k)
    return min(idxs, key=lambda i: pop_fitness[i])


def init_population(pop_size, bank_perm, n, rng, extra_seeds=None):
    """Initialize population: bank + heavy mutations + OR-Tools seeds + random."""
    pop = [list(bank_perm)]
    # Heavy bank-mutations (5-15 kicks) for more diversity
    while len(pop) < pop_size // 3:
        p = list(bank_perm)
        for _ in range(rng.randint(5, 15)):
            p = mutate(p, rng)
        pop.append(p)
    # Inject OR-Tools / structurally-different seeds (even if infeasible initially)
    if extra_seeds:
        for s in extra_seeds:
            if len(pop) >= 2 * pop_size // 3: break
            pop.append(list(s))
        # And their mutations
        for s in extra_seeds:
            for _ in range(3):
                if len(pop) >= 2 * pop_size // 3: break
                p = list(s)
                for _ in range(rng.randint(2, 5)):
                    p = mutate(p, rng)
                pop.append(p)
    # Fill rest with random shuffles
    while len(pop) < pop_size:
        p = list(range(n))
        rng.shuffle(p)
        pop.append(p)
    return pop


def ga_island(args):
    """One island: run GA for T_max seconds.

    Returns best perm and a list of all unique perms with fmk < threshold.
    """
    island_id, pop_size, T_max, init_seed_perm, extra_seeds = args
    rng = random.Random(island_id * 1000 + 7)
    n = _GLOB['n']
    # Initialize population
    pop = init_population(pop_size, init_seed_perm, n, rng,
                           extra_seeds=extra_seeds)
    pop_fitness = [fitness(p) for p in pop]
    n_feas_init = sum(1 for f in pop_fitness if f < 1e8)
    print(f"  [is={island_id}] init pop_size={pop_size} feasible={n_feas_init} "
          f"best={min(pop_fitness):.2f}", flush=True)

    best_perm = pop[int(np.argmin(pop_fitness))]
    best_fit = min(pop_fitness)
    all_seen = {}  # perm tuple -> fitness
    for p, f in zip(pop, pop_fitness):
        if f < 1e8:
            all_seen[tuple(p)] = f

    t0 = time.time()
    gen = 0
    last_log = t0
    while time.time() - t0 < T_max:
        gen += 1
        # Produce 1 child per loop (steady-state GA)
        # tournament size 3 for selection pressure
        i = tournament_select(pop_fitness, 3, rng)
        j = tournament_select(pop_fitness, 3, rng)
        while j == i:
            j = tournament_select(pop_fitness, 3, rng)
        # 70% crossover, 30% mutate-only of best parent
        if rng.random() < 0.7:
            child = ox1_crossover(pop[i], pop[j], rng)
        else:
            child = list(pop[i])
        # Mutate child with 30% rate (and 1-3 mutations per occurrence)
        if rng.random() < 0.3:
            for _ in range(rng.randint(1, 3)):
                child = mutate(child, rng)
        cf = fitness(child)
        if cf < 1e8:
            all_seen[tuple(child)] = cf
        # Replace worst in tournament of 5
        replace_set = rng.sample(range(len(pop)), 5)
        worst = max(replace_set, key=lambda k: pop_fitness[k])
        if cf < pop_fitness[worst]:
            pop[worst] = child
            pop_fitness[worst] = cf
            if cf < best_fit:
                best_fit = cf
                best_perm = list(child)
        # Diversity injection: every 100k gens, replace 20% with fresh diverse seeds
        if gen % 100000 == 0:
            n_inject = max(1, pop_size // 5)
            # Pick worst N positions to replace
            ranked = sorted(range(pop_size), key=lambda k: pop_fitness[k], reverse=True)
            for ri in ranked[:n_inject]:
                # Either: heavily-mutated bank, or random shuffle, or crossover of two random
                choice = rng.random()
                if choice < 0.5:
                    p = list(best_perm)
                    for _ in range(rng.randint(8, 20)):
                        p = mutate(p, rng)
                elif choice < 0.8 and extra_seeds:
                    seed = rng.choice(extra_seeds)
                    p = list(seed)
                    for _ in range(rng.randint(2, 6)):
                        p = mutate(p, rng)
                else:
                    p = list(range(n)); rng.shuffle(p)
                pop[ri] = p
                pop_fitness[ri] = fitness(p)
        if time.time() - last_log > 60:
            elapsed = time.time() - t0
            pf_finite = [f for f in pop_fitness if f < 1e8]
            avg = sum(pf_finite) / max(len(pf_finite), 1)
            print(f"  [is={island_id} gen={gen} t={elapsed:.0f}s] "
                  f"best={best_fit:.2f} avg={avg:.2f} feas/pop={len(pf_finite)}/{pop_size} "
                  f"all_seen={len(all_seen)}", flush=True)
            last_log = time.time()
    elapsed = time.time() - t0
    print(f"  [is={island_id} DONE gen={gen}] best={best_fit:.2f} all_seen={len(all_seen)}",
           flush=True)
    return island_id, best_fit, best_perm, list(all_seen.items())


def get_ortools_diverse_seeds(n, cheap, exc, quantum, n_exc_budget):
    """Use OR-Tools routing with multiple first-solution strategies to
    generate structurally-diverse hamilton paths.

    Even if not fast-walk-feasible, they're hamilton paths whose gene
    sequences can recombine with bank's via crossover.
    """
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
    from ch2_e511_ortools_routing import build_static_costs
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
                print(f"  OR-Tools {strat}: ok", flush=True)
        except Exception as e:
            print(f"  OR-Tools {strat}: error", flush=True)
    return seeds


def main(T_max=2400, n_islands=8, pop_size=80):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE missing", flush=True); return
    kt = KTTSP(INST)
    _init()
    bank_mk = 142.8913
    bank = json.load(open(OUT))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    print(f"E-513 GA: bank={bank_mk:.4f}, R3=111.76, R1=101.65", flush=True)
    print(f"Islands={n_islands}, pop_size={pop_size}, T_max={T_max}s", flush=True)

    # Generate diverse seeds via OR-Tools
    print(f"\nGenerating diverse OR-Tools seeds...", flush=True)
    diverse_seeds = get_ortools_diverse_seeds(
        n, _GLOB['cheap'], _GLOB['exc'], _GLOB['quantum'], kt.n_exc)
    print(f"Got {len(diverse_seeds)} diverse seeds", flush=True)

    args = [(i, pop_size, T_max, bank_perm, diverse_seeds)
            for i in range(n_islands)]
    t0 = time.time()
    all_seen = []
    best_overall = (1e9, None)
    with mp.Pool(n_islands, initializer=_init) as p:
        for island_id, best_fit, best_perm, seen in p.imap_unordered(ga_island, args):
            all_seen.extend(seen)
            if best_fit < best_overall[0]:
                best_overall = (best_fit, best_perm)
                print(f"  island {island_id}: BEST fmk={best_fit:.2f}",
                       flush=True)
    print(f"\nGA done in {time.time()-t0:.0f}s. all_seen: {len(all_seen)}",
           flush=True)

    # Dedup; sort by fmk
    seen_d = {}
    for p_tuple, f in all_seen:
        if p_tuple not in seen_d or f < seen_d[p_tuple]:
            seen_d[p_tuple] = f
    uniq = sorted(seen_d.items(), key=lambda kv: kv[1])
    print(f"Unique perms: {len(uniq)}, fmk range: "
          f"{uniq[0][1]:.2f} - {uniq[-1][1]:.2f}", flush=True)

    # Phase 3: Lambert validation of top K
    K = min(2500, len(uniq))
    print(f"\nValidating top {K} via Lambert", flush=True)
    best_lambert = None
    t_val = time.time(); last_print = t_val
    for ix, (perm_t, fmk) in enumerate(uniq[:K]):
        perm = list(perm_t)
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
            print(f"  ... [{ix}/{K}] elapsed={time.time()-t_val:.0f}s "
                  f"best_lambert={best_lambert[0]:.4f}", flush=True)
            last_print = time.time()
    print(f"\nValidation wall: {time.time()-t_val:.0f}s", flush=True)

    if best_lambert and best_lambert[0] < bank_mk:
        bak = OUT + ".bak.20260530.e513"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_lambert[1]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_lambert[0]:.4f}d "
              f"({bank_mk - best_lambert[0]:.4f}d under prev)", flush=True)
    return best_overall


if __name__ == "__main__":
    tm = int(sys.argv[1]) if len(sys.argv) > 1 else 2400
    ps = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    main(T_max=tm, pop_size=ps)
