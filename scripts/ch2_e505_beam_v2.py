"""E-505 v2 — component-aware beam search with reserved exception budget.

Insight from audit: cheap-edge graph has 4 components {40, 3, 3, 3}. Need
K-1 = 3 exception bridges to connect components into a hamilton path.
Budget is 5. So 2 spare exceptions can be used in-component for shortening.

Strategy:
  1. Identify each node's component (BFS on cheap-edges).
  2. Constraint: at any state, count UNVISITED components.
     reserved = max(0, unvisited_components - 1)
     allowed_exc = budget - reserved
     If exc_used >= allowed_exc: skip exc transitions
  3. Beam search; expand cheap freely, exc only when allowed.

This forces the beam to PRESERVE exc budget for late-stage inter-component
jumps.
"""
from __future__ import annotations
import sys, time, json
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
TABLE_PATH = '/tmp/ch2_small_tcoupled.npz'
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"


def compute_components(cheap):
    """Undirected cheap-edge components."""
    n = cheap.shape[0]
    # i--j if EITHER direction has any feasible cell
    adj = [set() for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                if np.isfinite(cheap[i, j]).any() or np.isfinite(cheap[j, i]).any():
                    adj[i].add(j)
                    adj[j].add(i)
    comp_of = [-1] * n
    cid = 0
    for s in range(n):
        if comp_of[s] >= 0:
            continue
        stack = [s]
        comp_of[s] = cid
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if comp_of[v] < 0:
                    comp_of[v] = cid
                    stack.append(v)
        cid += 1
    return comp_of, cid


_GLOB = {}


def _init():
    data = np.load(TABLE_PATH)
    _GLOB['cheap'] = data['cheap']
    _GLOB['exc'] = data['exc']
    n = _GLOB['cheap'].shape[0]
    _GLOB['n'] = n
    comp_of, n_comp = compute_components(_GLOB['cheap'])
    _GLOB['comp_of'] = comp_of
    _GLOB['n_comp'] = n_comp
    # Pre-build per-component node masks
    _GLOB['comp_mask'] = [
        sum(1 << i for i in range(n) if comp_of[i] == c)
        for c in range(n_comp)
    ]


def beam_search_comp_aware(start, beam_K=5000, wait_lookahead=150,
                            n_exc_budget=5):
    """Component-aware beam search with separate in-comp vs inter-comp
    exception accounting.

    Policy:
      - inter-comp exc: ALWAYS allowed if exc_used < budget (needed to bridge)
      - in-comp exc: allowed only if exc_used + future_inter_comp_needed
        < budget (where future_inter_comp_needed = unvisited_comps - 1 if
        currently in an unvisited comp, else = unvisited_comps)

    State: (mk, cur, exc_used, mask, path, edges)
    """
    cheap = _GLOB['cheap']
    exc = _GLOB['exc']
    n = _GLOB['n']
    n_comp = _GLOB['n_comp']
    comp_of = _GLOB['comp_of']
    comp_mask = _GLOB['comp_mask']
    T = 200

    init_mask = 1 << start
    beam = [(0.0, start, 0, init_mask, (start,), ())]

    for depth in range(n - 1):
        children = []
        for mk, cur, exc_used, mask, path, edges in beam:
            t_min = int(np.ceil(mk))
            t_max = min(T, t_min + wait_lookahead)
            if t_min >= T:
                continue
            # Count unvisited components AFTER visiting any candidate j
            unvis_comps_now = sum(
                1 for c in range(n_comp)
                if (comp_mask[c] & ~mask) != 0
            )
            cur_comp = comp_of[cur]
            # If cur_comp still has unvisited, future inter-comp = unvis_comps - 1
            # If cur_comp fully visited (rare), future inter-comp = unvis_comps
            if (comp_mask[cur_comp] & ~mask) != 0:
                future_inter = unvis_comps_now - 1
            else:
                future_inter = unvis_comps_now

            for j in range(n):
                if mask & (1 << j):
                    continue
                j_comp = comp_of[j]
                is_inter = (j_comp != cur_comp)
                # cheap-search
                cheap_slice = cheap[cur, j, t_min:t_max]
                cheap_idx = np.where(np.isfinite(cheap_slice))[0]
                cheap_best = None
                if len(cheap_idx) > 0:
                    for k in cheap_idx[:5]:
                        td = t_min + k
                        tf = cheap_slice[k]
                        a = td + tf
                        if cheap_best is None or a < cheap_best[2]:
                            cheap_best = (td, tf, a, False)
                # exc-search policy:
                #   - if is_inter: always allow if exc_used < budget
                #   - else (in-comp): allow only if exc_used+future_inter < budget
                exc_best = None
                if is_inter:
                    can_exc = exc_used < n_exc_budget
                else:
                    can_exc = (exc_used + future_inter) < n_exc_budget
                if can_exc:
                    exc_slice = exc[cur, j, t_min:t_max]
                    exc_idx = np.where(np.isfinite(exc_slice))[0]
                    if len(exc_idx) > 0:
                        for k in exc_idx[:5]:
                            td = t_min + k
                            tf = exc_slice[k]
                            a = td + tf
                            if cheap_best is not None and a >= cheap_best[2]:
                                continue
                            if exc_best is None or a < exc_best[2]:
                                exc_best = (td, tf, a, True)
                for best in (cheap_best, exc_best):
                    if best is None:
                        continue
                    td, tf, arr, is_exc = best
                    new_mask = mask | (1 << j)
                    new_exc = exc_used + (1 if is_exc else 0)
                    children.append((arr, j, new_exc, new_mask,
                                     path + (j,),
                                     edges + ((td, tf, is_exc),)))
        if not children:
            return None
        children.sort(key=lambda s: s[0])
        beam = children[:beam_K]
    if beam:
        return beam[0]
    return None


def _worker(args):
    start, beam_K, wait_lookahead = args
    t0 = time.time()
    result = beam_search_comp_aware(start, beam_K, wait_lookahead)
    wall = time.time() - t0
    return start, result, wall


def main(beam_K=5000, wait_lookahead=150, workers=8):
    kt = KTTSP(INST)
    _init()
    n = _GLOB['n']
    print(f"E-505 v2: n={n}, comps={_GLOB['n_comp']} {[bin(m).count('1') for m in _GLOB['comp_mask']]}",
           flush=True)
    print(f"beam_K={beam_K}, wait_lookahead={wait_lookahead}d, workers={workers}",
           flush=True)
    print(f"Bank=142.9183d, R3=111.76d, R1=101.65d (Team HRI)", flush=True)

    args_list = [(s, beam_K, wait_lookahead) for s in range(n)]
    t_start = time.time()
    best_overall = None
    results = []
    with mp.Pool(workers, initializer=_init) as p:
        for start, result, wall in p.imap_unordered(_worker, args_list):
            if result is None:
                print(f"  start={start:2d}: INFEASIBLE  ({wall:.0f}s)", flush=True)
                results.append((start, None))
                continue
            mk, _cur, exc_used, _mask, path, edges = result
            results.append((start, mk))
            if best_overall is None or mk < best_overall[0]:
                best_overall = (mk, start, path, edges, exc_used)
                marker = " ★"
                if mk < 142.9183: marker += " UNDER BANK"
                if mk < 111.76:   marker += " UNDER R3"
                if mk < 101.65:   marker += " UNDER R1"
                print(f"  start={start:2d}: mk={mk:.3f}d exc={exc_used} "
                      f"({wall:.0f}s){marker}", flush=True)
            else:
                print(f"  start={start:2d}: mk={mk:.3f}d exc={exc_used} "
                      f"({wall:.0f}s)", flush=True)
    wall = time.time() - t_start
    print(f"\n=== E-505 v2 complete: wall={wall:.0f}s ===", flush=True)

    if best_overall is None:
        print("FAIL: no feasible tour found", flush=True)
        return None

    mk, start, path, edges, exc_used = best_overall
    print(f"Best: start={start} mk={mk:.4f}d exc={exc_used} perm={list(path)}",
          flush=True)

    times = [float(e[0]) for e in edges]
    tofs = [float(e[1]) for e in edges]
    perm = [int(p) for p in path]
    x = times + tofs + [float(p) for p in perm]
    fit = kt.fitness(x)
    feas = kt.is_feasible(fit)
    print(f"UDP fitness: {list(fit)}  feas={feas}", flush=True)
    if not feas:
        print("Beam result NOT feasible under UDP; re-walking chronologically",
              flush=True)
        times, tofs, dvs, ok, exc_w, kw = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
        if ok:
            mk_walk = times[-1] + tofs[-1]
            x = times + tofs + [float(p) for p in perm]
            fit = kt.fitness(x)
            feas = kt.is_feasible(fit)
            print(f"Re-walk: mk={mk_walk:.4f}d fitness={list(fit)} feas={feas}",
                   flush=True)
            mk = mk_walk

    if feas and mk < 142.9183:
        from pathlib import Path
        bak = OUT + ".bak.20260530"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"Backed up bank to {bak}", flush=True)
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(x),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f"\n>>> BANKED: {OUT}  mk={mk:.4f}d ({142.9183-mk:.4f}d under prev)",
              flush=True)

    return {"best_mk_d": mk, "best_start": start, "best_perm": perm,
            "best_exc_used": exc_used, "wall_s": wall, "udp_feasible": feas}


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    L = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 4  # E-504 still using cores
    res = main(beam_K=K, wait_lookahead=L, workers=W)
    if res:
        print(json.dumps({k: v for k, v in res.items() if k != 'best_perm'},
                          indent=2))
