"""E-517 — Ch2 small: component-aware bridge enumeration.

See vault/experiments/E-028-ch2-component-aware-bridge-enum.md for the
pre-registered hypothesis and rationale. This script is the runner.

Pipeline:
  1. Build cheap-edge components from /tmp/ch2_small_tcoupled_fine.npz;
     verify {|comp0|=40, comp1={4,11,17}, comp2={16,27,32}, comp3={18,23,34}}.
  2. Enumerate Level-1 (component order) × Level-2 (small-comp interior
     orderings) = 48 configs.
  3. For each config, build OR-Tools cost matrix for comp0 subgraph from
     min-tof table; run top-K (entry, exit) ∈ comp0 Hamilton paths.
  4. Assemble each full perm; Lambert-validate under BOTH wait_dt configs
     (S1: wait_dt=1.0, S2: wait_dt=0.2). Log separately.
  5. Bank-update live on any fmk < 142.8913 d.

Wall-cap: 4 h. Checkpoint every 5 min to /tmp/ch2_e517_ckpt.json.
"""
from __future__ import annotations
import sys, os, json, time, itertools
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260601.e517"
FINE = '/tmp/ch2_small_tcoupled_fine.npz'
CKPT = '/tmp/ch2_e517_ckpt.json'
HIST = '/tmp/ch2_e517_history.jsonl'

BANK_MK = 142.8913

# Substrate configs S1, S2 (audit lever D2 reversal):
SUBSTRATES = [
    ('S1', dict(tof_window=18.0, n_steps=180, wait_steps=12, wait_dt=1.0)),
    ('S2', dict(tof_window=18.0, n_steps=360, wait_steps=60, wait_dt=0.2)),
]

_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)
    _GLOB['n'] = _GLOB['kt'].n
    _GLOB['n_exc'] = _GLOB['kt'].n_exc


def find_components(fine_path):
    """Return list of frozenset of node ids (one per connected component)."""
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    d = np.load(fine_path)
    cheap = d['cheap']  # (n,n,T)
    cheap_min = np.nanmin(cheap, axis=2)
    n = cheap_min.shape[0]
    np.fill_diagonal(cheap_min, np.inf)
    adj = cheap_min < np.inf
    adj_sym = adj | adj.T
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym),
                                       directed=False)
    comps = [frozenset(i for i in range(n) if lbl[i] == c)
             for c in range(nc)]
    return comps, cheap_min


def classify_comps(comps, start_node, end_node):
    """Identify (big_comp, start_comp, end_comp, mid_small_comp)."""
    big = max(comps, key=len)
    start_c = next(c for c in comps if start_node in c)
    end_c = next(c for c in comps if end_node in c)
    smalls = [c for c in comps if c is not big]
    mid_small = [c for c in smalls if c is not start_c and c is not end_c]
    assert len(mid_small) == 1, f"expected 1 middle small comp, got {len(mid_small)}"
    return big, start_c, end_c, mid_small[0]


_ORTOOLS_STRATS = [
    'PATH_CHEAPEST_ARC',
    'PARALLEL_CHEAPEST_INSERTION',
    'LOCAL_CHEAPEST_INSERTION',
    'PATH_MOST_CONSTRAINED_ARC',
    'CHRISTOFIDES',
]


def ortools_subpath(cost_matrix, entry, exit_node, time_limit_s=15,
                    strategy='PATH_CHEAPEST_ARC'):
    """OR-Tools Hamilton path on a subgraph with fixed entry and exit.

    cost_matrix: square int matrix, large entries forbidden.
    Returns: list of node indices (entry ... exit_node) or None.

    NOTE: smoke-tested 2026-06-01 — single-strategy paths are often
    Lambert-infeasible because the min-tof-over-t cost ignores
    chronology. Caller should try multiple strategies via
    `ortools_subpaths_multi`.
    """
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    N = cost_matrix.shape[0]
    DEPOT = N
    mgr = pywrapcp.RoutingIndexManager(N + 1, 1, [DEPOT], [DEPOT])
    routing = pywrapcp.RoutingModel(mgr)
    BIG = int(1e12)

    def transit(i_idx, j_idx, m=mgr):
        i = m.IndexToNode(i_idx); j = m.IndexToNode(j_idx)
        if i == DEPOT and j == entry:
            return 0
        if j == DEPOT and i == exit_node:
            return 0
        if i == DEPOT or j == DEPOT:
            return BIG
        return int(cost_matrix[i, j])

    tcb = routing.RegisterTransitCallback(transit)
    routing.SetArcCostEvaluatorOfAllVehicles(tcb)

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = getattr(
        routing_enums_pb2.FirstSolutionStrategy, strategy)
    sp.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    sp.time_limit.seconds = time_limit_s

    sol = routing.SolveWithParameters(sp)
    if not sol:
        return None
    path = []
    idx = routing.Start(0)
    while not routing.IsEnd(idx):
        node = mgr.IndexToNode(idx)
        if node != DEPOT:
            path.append(node)
        idx = sol.Value(routing.NextVar(idx))
    return path if path and path[0] == entry and path[-1] == exit_node else None


def ortools_subpaths_multi(cost_matrix, entry, exit_node,
                            time_limit_s=10, strategies=None):
    """Yield distinct Hamilton paths across multiple first-solution strategies.

    Returns: list of path-lists (each entry ... exit_node), deduplicated.
    """
    strategies = strategies or _ORTOOLS_STRATS
    seen = set()
    paths = []
    for strat in strategies:
        try:
            p = ortools_subpath(cost_matrix, entry, exit_node,
                                time_limit_s=time_limit_s, strategy=strat)
        except Exception:
            continue
        if p is None:
            continue
        key = tuple(p)
        if key in seen:
            continue
        seen.add(key)
        paths.append(p)
    return paths


def enumerate_configs(big_comp, start_comp, mid_comp, end_comp,
                      start_node, end_node):
    """Yield (L1_order_label, comp3_path, comp1_path, comp2_path).

    L1 has 2 orderings (interior swap of {big, mid}).
    Each small comp contributes its interior orderings.
    """
    # comp3 (start): {start_node, x, y} → 2 orderings of (x, y)
    others_start = sorted(start_comp - {start_node})
    start_paths = [
        [start_node, others_start[0], others_start[1]],
        [start_node, others_start[1], others_start[0]],
    ]
    # comp2 (end): must end at end_node → 2 orderings
    others_end = sorted(end_comp - {end_node})
    end_paths = [
        [others_end[0], others_end[1], end_node],
        [others_end[1], others_end[0], end_node],
    ]
    # mid_comp: 3! = 6 orderings of all members
    mid_members = sorted(mid_comp)
    mid_paths = [list(p) for p in itertools.permutations(mid_members)]

    for l1_label in ['A_big_then_mid', 'B_mid_then_big']:
        for sp_path in start_paths:
            for mp_path in mid_paths:
                for ep_path in end_paths:
                    yield (l1_label, sp_path, mp_path, ep_path)


def candidate_comp0_endpoints(l1_label, comp3_exit, comp1_path,
                              comp2_entry, exc_table, big_comp, top_k=5):
    """Pick top-k (entry, exit) ∈ big_comp pairs by exception-bridge cost.

    For ordering A (comp3 → big → mid → comp2):
        entry = bridge target from comp3_exit
        exit  = bridge source toward comp1_path[0]  (mid entry)
    For ordering B (comp3 → mid → big → comp2):
        entry = bridge target from comp1_path[-1]   (mid exit)
        exit  = bridge source toward comp2_entry
    """
    big_list = sorted(big_comp)
    # exc_table[i,j,t] — min over t per (i,j); use min as ranking proxy
    exc_min = np.nanmin(exc_table, axis=2)

    if l1_label == 'A_big_then_mid':
        src = comp3_exit
        dst = comp1_path[0]
        # entry candidates: big_comp nodes reachable cheaply via exc from src
        # exit candidates: big_comp nodes reachable cheaply via exc to dst
        entry_costs = [(b, exc_min[src, b]) for b in big_list]
        exit_costs = [(b, exc_min[b, dst]) for b in big_list]
    else:  # B
        src = comp1_path[-1]
        dst = comp2_entry
        entry_costs = [(b, exc_min[src, b]) for b in big_list]
        exit_costs = [(b, exc_min[b, dst]) for b in big_list]

    entry_costs.sort(key=lambda t: t[1] if np.isfinite(t[1]) else 1e18)
    exit_costs.sort(key=lambda t: t[1] if np.isfinite(t[1]) else 1e18)

    # Combine: top_k (entry, exit) by sum of bridge cost, entry != exit
    combos = []
    for e, ce in entry_costs[:top_k * 2]:
        for x, cx in exit_costs[:top_k * 2]:
            if e == x:
                continue
            if not (np.isfinite(ce) and np.isfinite(cx)):
                continue
            combos.append((e, x, ce + cx))
    combos.sort(key=lambda t: t[2])
    seen = set()
    out = []
    for e, x, _ in combos:
        if (e, x) in seen:
            continue
        seen.add((e, x))
        out.append((e, x))
        if len(out) >= top_k:
            break
    return out


def assemble_perm(l1_label, comp3_path, mid_path, comp2_path,
                  big_path):
    """Assemble full perm from sub-paths."""
    if l1_label == 'A_big_then_mid':
        return comp3_path + big_path + mid_path + comp2_path
    else:  # B
        return comp3_path + mid_path + big_path + comp2_path


def count_exc_breakdown(kt, perm, times, tofs, dvs, components):
    """Return (n_inter, n_intra) exc count."""
    # map node -> comp index
    node_comp = {}
    for ci, comp in enumerate(components):
        for v in comp:
            node_comp[v] = ci
    n_inter = n_intra = 0
    for k in range(len(perm) - 1):
        if dvs[k] > 100.0 + 1e-3:
            if node_comp[perm[k]] != node_comp[perm[k + 1]]:
                n_inter += 1
            else:
                n_intra += 1
    return n_inter, n_intra


def evaluate_candidate(args):
    """Lambert-validate one perm under both substrates. Return list of records."""
    cand_id, perm, components = args
    kt = _GLOB['kt']
    results = []
    for label, kwargs in SUBSTRATES:
        try:
            times, tofs, dvs, ok, exc, last_leg = walk_perm_chrono(
                kt, perm, **kwargs)
        except Exception as e:
            results.append({'cand_id': cand_id, 'substrate': label,
                            'ok': False, 'err': str(e)[:80]})
            continue
        if not ok:
            results.append({'cand_id': cand_id, 'substrate': label,
                            'ok': False, 'last_leg': last_leg,
                            'exc_used': exc})
            continue
        mk = times[-1] + tofs[-1]
        x = list(times) + list(tofs) + [float(p) for p in perm]
        fit = kt.fitness(x)
        feas = bool(kt.is_feasible(fit))
        n_inter, n_intra = count_exc_breakdown(kt, perm, times, tofs, dvs,
                                                components)
        results.append({
            'cand_id': cand_id, 'substrate': label, 'ok': True,
            'feas': feas, 'mk': float(mk), 'exc_total': int(exc),
            'exc_inter': int(n_inter), 'exc_intra': int(n_intra),
            'perm': list(perm), 'x': x,
        })
    return results


def maybe_update_bank(rec):
    """Atomic bank update if rec is feasible and beats BANK_MK."""
    if not rec.get('feas'):
        return False
    if rec['mk'] >= BANK_MK:
        return False
    # Back up if first time
    if Path(OUT).exists() and not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    # Atomic write
    payload = [{
        'decisionVector': rec['x'],
        'problem': 'small',
        'challenge': CHALLENGE,
    }]
    tmp = OUT + '.tmp'
    Path(tmp).write_text(json.dumps(payload))
    os.replace(tmp, OUT)
    return True


def main(wall_cap_h=4.0, top_k_comp0=5, ortools_seconds=5):
    # ortools_seconds is per-strategy; with 5 strategies × top_k × 48 configs
    # we keep total OR-Tools wall under ~1.5 h on 1 core.
    if not Path(FINE).exists():
        print(f"ERR: fine table missing at {FINE}", flush=True)
        return
    _init()
    kt = KTTSP(INST)
    n = kt.n

    # ── load bank perm for reference (start/end fixing) ──────────────
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2 * (n - 1):]]
    start_node, end_node = bank_perm[0], bank_perm[-1]
    print(f"E-517 bridge enumeration. bank mk={BANK_MK} start={start_node} "
          f"end={end_node}", flush=True)

    # ── components ────────────────────────────────────────────────────
    comps, cheap_min = find_components(FINE)
    print(f"Components: {len(comps)}", flush=True)
    for i, c in enumerate(comps):
        print(f"  comp {i}: {len(c)} nodes  members={sorted(c)[:5]}...",
              flush=True)
    big, start_c, end_c, mid_c = classify_comps(comps, start_node, end_node)
    print(f"big=|{len(big)}|, start_c=|{len(start_c)}|, mid_c=|{len(mid_c)}|, "
          f"end_c=|{len(end_c)}|", flush=True)

    # ── load fine table for OR-Tools cost matrices ────────────────────
    d = np.load(FINE)
    cheap_t = d['cheap']  # (n,n,T)
    exc_t = d['exc']      # (n,n,T)
    # min-tof per pair (used as OR-Tools edge cost on comp0)
    # We want the cheapest cheap dv across t; if no cheap exists, BIG.
    cheap_min_pair = np.nanmin(cheap_t, axis=2)  # (n,n)

    big_list = sorted(big)
    big_to_idx = {v: i for i, v in enumerate(big_list)}
    N0 = len(big_list)
    # Build cost matrix for comp0 subgraph (cheap-only; non-cheap → BIG)
    BIG_COST = 10 ** 9
    sub_cost = np.full((N0, N0), BIG_COST, dtype=np.int64)
    for i, vi in enumerate(big_list):
        for j, vj in enumerate(big_list):
            if i == j:
                sub_cost[i, j] = 0
                continue
            c = cheap_min_pair[vi, vj]
            if np.isfinite(c):
                # Scale to int (dv in m/s × 100 → int)
                sub_cost[i, j] = int(c * 100.0)
    n_cheap_arcs = int(np.sum(sub_cost < BIG_COST) - N0)
    print(f"comp0 cheap arc count = {n_cheap_arcs} / {N0*(N0-1)} = "
          f"{n_cheap_arcs/(N0*(N0-1))*100:.1f}%", flush=True)

    # ── enumerate configs and build candidate perms ──────────────────
    candidates = []  # list of (cand_id, perm)
    cand_id = 0
    config_log = []
    for l1, comp3_path, mid_path, comp2_path in enumerate_configs(
            big, start_c, mid_c, end_c, start_node, end_node):
        # determine endpoints for comp0 sub-Hamilton based on L1 ordering
        if l1 == 'A_big_then_mid':
            comp3_exit_node = comp3_path[-1]
            comp1_entry_node = mid_path[0]
            comp2_entry_node = comp2_path[0]
            top_pairs = candidate_comp0_endpoints(
                l1, comp3_exit_node, mid_path, comp2_entry_node,
                exc_t, big, top_k=top_k_comp0)
        else:  # B
            comp1_exit_node = mid_path[-1]
            comp2_entry_node = comp2_path[0]
            top_pairs = candidate_comp0_endpoints(
                l1, comp3_path[-1], mid_path, comp2_entry_node,
                exc_t, big, top_k=top_k_comp0)

        for (entry_v, exit_v) in top_pairs:
            entry_idx = big_to_idx[entry_v]
            exit_idx = big_to_idx[exit_v]
            big_paths_idx = ortools_subpaths_multi(
                sub_cost, entry_idx, exit_idx,
                time_limit_s=ortools_seconds)
            for big_path_idx in big_paths_idx:
                big_path = [big_list[i] for i in big_path_idx]
                if len(big_path) != N0:
                    continue
                perm = assemble_perm(l1, comp3_path, mid_path,
                                      comp2_path, big_path)
                if len(perm) != n or len(set(perm)) != n:
                    continue
                candidates.append((cand_id, perm, comps))
                config_log.append({
                    'cand_id': cand_id, 'l1': l1,
                    'comp3_path': comp3_path,
                    'mid_path': mid_path, 'comp2_path': comp2_path,
                    'big_entry': entry_v, 'big_exit': exit_v,
                    'or_strat_idx': big_paths_idx.index(big_path_idx),
                })
                cand_id += 1
    print(f"Enumerated {len(candidates)} candidate perms.", flush=True)
    Path('/tmp/ch2_e517_configs.jsonl').write_text(
        '\n'.join(json.dumps(c) for c in config_log) + '\n')

    # ── parallel Lambert validation ─────────────────────────────────
    t0 = time.time()
    best = {'S1': (1e9, None), 'S2': (1e9, None)}
    n_feas = {'S1': 0, 'S2': 0}
    n_three_inter = 0
    hist_fh = open(HIST, 'w')

    with mp.Pool(8, initializer=_init) as pool:
        for results in pool.imap_unordered(evaluate_candidate, candidates):
            for rec in results:
                # write history line
                slim = {k: v for k, v in rec.items() if k != 'x'}
                hist_fh.write(json.dumps(slim) + '\n')
                if rec.get('ok') and rec.get('feas'):
                    n_feas[rec['substrate']] += 1
                    if rec['exc_inter'] == 3:
                        n_three_inter += 1
                    if rec['mk'] < best[rec['substrate']][0]:
                        best[rec['substrate']] = (rec['mk'], rec)
                    if maybe_update_bank(rec):
                        print(f"  >>> BANKED cand={rec['cand_id']} "
                              f"sub={rec['substrate']} mk={rec['mk']:.4f}d "
                              f"({BANK_MK - rec['mk']:.4f}d under prev)",
                              flush=True)
            # periodic log + checkpoint
            elapsed = time.time() - t0
            if elapsed > wall_cap_h * 3600:
                print("Wall cap reached.", flush=True)
                break
        hist_fh.close()

    wall = time.time() - t0
    print(f"\nE-517 done in {wall/60:.1f} min", flush=True)
    print(f"feas counts: S1={n_feas['S1']} S2={n_feas['S2']}", flush=True)
    print(f"perms with exactly 3 inter-comp exc: {n_three_inter}", flush=True)
    for label in ('S1', 'S2'):
        mk, rec = best[label]
        if rec is None:
            print(f"  best {label}: no feasible", flush=True)
        else:
            print(f"  best {label}: mk={mk:.4f}d "
                  f"exc(inter/intra)={rec['exc_inter']}/{rec['exc_intra']} "
                  f"cand_id={rec['cand_id']}", flush=True)


if __name__ == '__main__':
    wh = float(sys.argv[1]) if len(sys.argv) > 1 else 4.0
    main(wall_cap_h=wh)
