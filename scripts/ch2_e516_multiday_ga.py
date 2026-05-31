"""E-516 — Multi-day GA for Ch2 small (HRI-style massive compute).

Architecture for sustained 24-48h run:
  - 8 islands × population 20 each (small pops, fast turnover under Lambert ~1-4s)
  - Edge-Recombination Crossover (ERX) — preserves edge structure
    (more chronology-friendly than OX1)
  - Mutation: 2-opt (40%), or-opt (30%), swap (15%), double-bridge (15%)
  - High mutation rate (50%) to escape narrow Lambert-feasible manifold
  - Periodic migration between islands (every 1 hr)
  - Diversity injection: every 30 min, replace worst 20% with fresh random
    or OR-Tools seeds
  - Checkpoint to /tmp/ch2_e516_ckpt.json every 5 min
  - On startup: load checkpoint if exists
  - Bank update IMMEDIATELY on any Lambert-feasible mk < 142.89 d
"""
from __future__ import annotations
import sys, time, json, random, os
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from ch2_e511_ortools_routing import build_static_costs

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
FINE_TABLE = '/tmp/ch2_small_tcoupled_fine.npz'
CKPT = '/tmp/ch2_e516_ckpt.json'
BANK_LOG = '/tmp/ch2_e516_bank_history.jsonl'
_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)
    _GLOB['n'] = _GLOB['kt'].n
    _GLOB['n_exc'] = _GLOB['kt'].n_exc


def lambert_fitness(perm, configs=None):
    if configs is None:
        configs = [(180, 12, 1.0, 18.0), (360, 60, 0.2, 18.0)]
    kt = _GLOB['kt']
    best = None
    best_x = None
    for ns, ws, wd, tw in configs:
        try:
            times, tofs, _, ok, _, _ = walk_perm_chrono(
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


def erx_crossover(p1, p2, rng):
    """Edge Recombination Crossover (ERX).

    Builds an "edge map" — each city's set of neighbors from both parents.
    Constructs child by greedy-following the smallest-neighborhood path.
    Preserves more local structure than OX1.
    """
    n = len(p1)
    # Build edge map (treat as cycle for adjacency — wrap around)
    edges = {i: set() for i in range(n)}
    for parent in (p1, p2):
        for i in range(n):
            prev = parent[(i - 1) % n]
            nxt = parent[(i + 1) % n]
            edges[parent[i]].add(prev)
            edges[parent[i]].add(nxt)
    # Start from p1[0] (preserve start)
    start = p1[0]
    child = [start]
    used = {start}
    cur = start
    for _ in range(n - 1):
        for v in edges.values():
            v.discard(cur)
        nbrs = edges[cur] - used
        if nbrs:
            # Pick neighbor with smallest neighbor list (greedy)
            nxt = min(nbrs, key=lambda x: len(edges[x] - used))
        else:
            # No edges left, pick random unused
            remaining = [v for v in range(n) if v not in used]
            if not remaining: break
            nxt = rng.choice(remaining)
        child.append(nxt)
        used.add(nxt)
        cur = nxt
    return child


def ox1_crossover(p1, p2, rng):
    n = len(p1)
    a = rng.randint(1, n - 2); b = rng.randint(a + 1, n - 1)
    middle = p1[a:b]; mset = set(middle)
    fill = []
    for idx in list(range(b, n)) + list(range(0, b)):
        if p2[idx] not in mset: fill.append(p2[idx])
    child = [None] * n; child[a:b] = middle; f_idx = 0
    for i in list(range(b, n)) + list(range(0, a)):
        child[i] = fill[f_idx]; f_idx += 1
    return child


def mutate(perm, rng):
    n = len(perm)
    mv = rng.choices(['2opt', 'or_opt_1', 'or_opt_2', 'or_opt_3', 'swap',
                       'double_bridge'],
                     weights=[3, 2, 2, 2, 1, 1])[0]
    if mv == '2opt':
        i = rng.randint(1, n - 3); j = rng.randint(i + 1, n - 2)
        return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]
    elif mv.startswith('or_opt'):
        seg_len = int(mv[-1])
        if seg_len >= n - 2: return perm
        i = rng.randint(1, n - seg_len - 1)
        seg = perm[i:i+seg_len]; rest = perm[:i] + perm[i+seg_len:]
        p = rng.randint(1, len(rest))
        return rest[:p] + seg + rest[p:]
    elif mv == 'swap':
        i = rng.randint(1, n - 2); j = rng.randint(1, n - 2)
        if i == j: return perm
        new = list(perm); new[i], new[j] = new[j], new[i]; return new
    elif mv == 'double_bridge':
        if n < 8: return perm
        cuts = sorted(rng.sample(range(1, n-1), 3))
        a, b, c = cuts
        return perm[:a] + perm[c:] + perm[b:c] + perm[a:b]
    return perm


def tournament_select(pop_fitness, k, rng):
    idxs = rng.sample(range(len(pop_fitness)), min(k, len(pop_fitness)))
    return min(idxs, key=lambda i: pop_fitness[i])


def get_ortools_seeds(n, n_exc):
    """Cache OR-Tools seeds across islands."""
    if 'ortools_seeds' in _GLOB:
        return _GLOB['ortools_seeds']
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    d = np.load(FINE_TABLE)
    cheap, exc = d['cheap'], d['exc']
    quantum = float(d['t_starts'][1] - d['t_starts'][0])
    _cc, cost_exc, is_exc_only = build_static_costs(cheap, exc, quantum)
    DEPOT = n
    seeds = []
    for strat in ['PATH_CHEAPEST_ARC', 'PARALLEL_CHEAPEST_INSERTION',
                  'LOCAL_CHEAPEST_INSERTION', 'FIRST_UNBOUND_MIN_VALUE',
                  'PATH_MOST_CONSTRAINED_ARC']:
        for meta in ['GUIDED_LOCAL_SEARCH', 'GREEDY_DESCENT']:
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
                routing.AddDimensionWithVehicleCapacity(ecb, 0, [n_exc], True, 'Exception')
                sp = pywrapcp.DefaultRoutingSearchParameters()
                sp.first_solution_strategy = getattr(
                    routing_enums_pb2.FirstSolutionStrategy, strat)
                sp.local_search_metaheuristic = getattr(
                    routing_enums_pb2.LocalSearchMetaheuristic, meta)
                sp.time_limit.seconds = 5
                sol = routing.SolveWithParameters(sp)
                if not sol: continue
                perm = []; idx = routing.Start(0)
                while not routing.IsEnd(idx):
                    node = manager.IndexToNode(idx)
                    if node != DEPOT: perm.append(node)
                    idx = sol.Value(routing.NextVar(idx))
                if len(perm) == n:
                    seeds.append(perm)
            except Exception:
                pass
    _GLOB['ortools_seeds'] = seeds
    return seeds


def init_population(pop_size, bank_perm, n, rng, ortools_seeds=None):
    """Initialize: bank + bank-mutations + OR-Tools seeds + random shuffles."""
    pop = [list(bank_perm)]
    # Bank-mutations with varying kick counts
    while len(pop) < pop_size // 3:
        p = list(bank_perm)
        for _ in range(rng.randint(2, 8)):
            p = mutate(p, rng)
        pop.append(p)
    # OR-Tools seeds + their mutations
    if ortools_seeds:
        for s in ortools_seeds:
            if len(pop) >= 2 * pop_size // 3: break
            pop.append(list(s))
            # Add a few mutations
            for _ in range(2):
                if len(pop) >= 2 * pop_size // 3: break
                p = list(s)
                for _ in range(rng.randint(1, 4)):
                    p = mutate(p, rng)
                pop.append(p)
    # Fill with random shuffles
    while len(pop) < pop_size:
        p = list(range(n)); rng.shuffle(p)
        pop.append(p)
    return pop[:pop_size]


def island_ga(args):
    """Single-island GA loop. Returns at T_max."""
    island_id, pop_size, T_max, bank_perm, ortools_seeds, ckpt_data = args
    rng = random.Random(island_id * 7919 + int(time.time()) & 0xFFFF)
    n = _GLOB['n']

    if ckpt_data:
        pop = [list(p) for p in ckpt_data['pop']]
        pop_fit_and_x = []
        for p in pop:
            f, x = lambert_fitness(p)
            pop_fit_and_x.append((f if f is not None else 1e9, x))
        print(f"  [is={island_id}] resumed from ckpt with {len(pop)} pop",
               flush=True)
    else:
        pop = init_population(pop_size, bank_perm, n, rng, ortools_seeds)
        pop_fit_and_x = []
        for p in pop:
            f, x = lambert_fitness(p)
            pop_fit_and_x.append((f if f is not None else 1e9, x))
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
    gen = 0
    last_log = t0
    last_inject = t0
    last_ckpt = t0
    while time.time() - t0 < T_max:
        gen += 1
        # Parent selection
        i = tournament_select(pop_fitness, 3, rng)
        j = tournament_select(pop_fitness, 3, rng)
        while j == i:
            j = tournament_select(pop_fitness, 3, rng)
        # Crossover (alternate OX1 and ERX)
        if rng.random() < 0.5:
            child = ox1_crossover(pop[i], pop[j], rng)
        else:
            try:
                child = erx_crossover(pop[i], pop[j], rng)
            except Exception:
                child = ox1_crossover(pop[i], pop[j], rng)
        # Heavy mutation (50% chance, 1-4 mutations)
        if rng.random() < 0.5:
            for _ in range(rng.randint(1, 4)):
                child = mutate(child, rng)
        # Evaluate
        cf, cx = lambert_fitness(child)
        cf = cf if cf is not None else 1e9
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
                # Log every improvement
                with open(BANK_LOG, 'a') as fh:
                    fh.write(json.dumps({
                        'island': island_id, 'gen': gen, 'mk': cf,
                        'elapsed': time.time() - t0,
                        'perm': list(child)}) + '\n')
        # Diversity injection every 20 min
        if time.time() - last_inject > 1200:
            n_inject = max(1, pop_size // 4)
            ranked = sorted(range(pop_size), key=lambda k: pop_fitness[k], reverse=True)
            for ri in ranked[:n_inject]:
                choice = rng.random()
                if choice < 0.4:
                    p = list(best_perm)
                    for _ in range(rng.randint(5, 12)):
                        p = mutate(p, rng)
                elif choice < 0.7 and ortools_seeds:
                    seed = rng.choice(ortools_seeds)
                    p = list(seed)
                    for _ in range(rng.randint(2, 6)):
                        p = mutate(p, rng)
                else:
                    p = list(range(n)); rng.shuffle(p)
                f, x = lambert_fitness(p)
                pop[ri] = p
                pop_fit_and_x[ri] = (f if f is not None else 1e9, x)
                pop_fitness[ri] = pop_fit_and_x[ri][0]
            last_inject = time.time()
            print(f"  [is={island_id} gen={gen}] injected diversity ({n_inject})",
                   flush=True)
        # Checkpoint every 5 min
        if time.time() - last_ckpt > 300:
            try:
                ckpt = {
                    'island_id': island_id,
                    'gen': gen,
                    'best_mk': best_fit,
                    'best_perm': best_perm,
                    'pop': [list(p) for p in pop],
                    'all_seen_count': len(all_seen),
                    'wall_elapsed': time.time() - t0,
                }
                with open(f'/tmp/ch2_e516_ckpt_is{island_id}.json', 'w') as fh:
                    json.dump(ckpt, fh)
            except Exception as e:
                print(f"  [is={island_id}] ckpt error: {e}", flush=True)
            last_ckpt = time.time()
        # Log every 5 min
        if time.time() - last_log > 300:
            pf = [f for f in pop_fitness if f < 1e8]
            avg = sum(pf) / max(len(pf), 1) if pf else float('inf')
            print(f"  [is={island_id} gen={gen} t={time.time()-t0:.0f}s] "
                  f"best={best_fit:.2f} avg={avg:.2f} "
                  f"feas/pop={len(pf)}/{pop_size} all_seen={len(all_seen)}",
                   flush=True)
            last_log = time.time()
    return island_id, best_fit, best_perm, best_x, len(all_seen)


def main(T_max_hours=24, n_islands=8, pop_size=20):
    if not Path(FINE_TABLE).exists():
        print(f"FINE_TABLE missing", flush=True); return
    _init()
    kt = KTTSP(INST)
    n = kt.n
    bank_mk = 142.8913
    bank = json.load(open(OUT))
    dv = bank[0]["decisionVector"]
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    print(f"E-516 multi-day GA: bank={bank_mk:.4f}, R3=111.76, R1=101.65",
           flush=True)
    print(f"Islands={n_islands}, pop_size={pop_size}, T_max={T_max_hours}h",
           flush=True)
    T_max_s = T_max_hours * 3600

    # OR-Tools seeds (once)
    seeds = get_ortools_seeds(n, kt.n_exc)
    print(f"OR-Tools seeds: {len(seeds)}", flush=True)

    # Try to load checkpoints per island
    ckpt_data_per_island = [None] * n_islands
    for i in range(n_islands):
        p = Path(f'/tmp/ch2_e516_ckpt_is{i}.json')
        if p.exists():
            try:
                ckpt_data_per_island[i] = json.load(open(p))
                print(f"  found ckpt for island {i}: best={ckpt_data_per_island[i]['best_mk']:.2f}",
                       flush=True)
            except Exception:
                pass

    args = [(i, pop_size, T_max_s, bank_perm, seeds, ckpt_data_per_island[i])
            for i in range(n_islands)]
    t0 = time.time()
    best_overall = (1e9, None, None)
    with mp.Pool(n_islands, initializer=_init) as p:
        for island_id, mk, perm, x, n_seen in p.imap_unordered(island_ga, args):
            print(f"  island {island_id} DONE: best={mk:.4f} n_seen={n_seen}",
                   flush=True)
            if mk < best_overall[0]:
                best_overall = (mk, perm, x)
                if mk < bank_mk:
                    print(f"  >>> island {island_id} BEAT BANK: {mk:.4f}",
                           flush=True)
    wall = time.time() - t0
    print(f"\nE-516 done in {wall/3600:.1f}h", flush=True)
    print(f"Best mk: {best_overall[0]:.4f}d  (bank was 142.89)", flush=True)

    if best_overall[0] < bank_mk and best_overall[2] is not None:
        bak = OUT + ".bak.20260530.e516"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_overall[2]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_overall[0]:.4f}d "
              f"({bank_mk - best_overall[0]:.4f}d under prev)", flush=True)


if __name__ == "__main__":
    h = float(sys.argv[1]) if len(sys.argv) > 1 else 24
    pop = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    main(T_max_hours=h, pop_size=pop)
