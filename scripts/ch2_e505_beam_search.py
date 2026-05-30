"""E-505 — Ch2 small time-coupled beam search.

Uses the precomputed time-coupled edge table /tmp/ch2_small_tcoupled.npz:
  cheap[i, j, t] = min tof at t_start=t s.t. dv ≤ 100, or inf
  exc[i, j, t]   = min tof at t_start=t s.t. dv ≤ 600, or inf
  t_starts: 0..199 in 1-day quanta

Beam search:
  state = (cur_node, t_current, exc_used, visited_set_bitmask, makespan_so_far)
  expand: for each unvisited j, scan t' >= ceil(t_current) within window;
    find earliest valid edge (cheap preferred unless exc much faster);
    enqueue child state with arrival = t' + tof.
  beam: keep top K states by (makespan_so_far + admissible heuristic to go)
  admissible heuristic: sum of (n-visited-1) smallest cheap-tof in graph
  (loose but admissible) — actually use 0 to avoid expensive recompute.

Output: best feasible (full-tour) state. Validate via UDP.

Strategy:
  - For each starting node, run beam with K=2000, depth 49
  - Pick best across all 49 starts
  - If best < bank 142.92 → bank update
"""
from __future__ import annotations
import sys, time, json
import heapq
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
TABLE_PATH = '/tmp/ch2_small_tcoupled.npz'
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"


def load_tables():
    data = np.load(TABLE_PATH)
    return data['cheap'], data['exc'], data['t_starts']


_GLOB = {}


def _init(cheap_path, exc_path, n, n_exc):
    data = np.load(TABLE_PATH)
    _GLOB['cheap'] = data['cheap']
    _GLOB['exc'] = data['exc']
    _GLOB['t_starts'] = data['t_starts']
    _GLOB['n'] = n
    _GLOB['n_exc'] = n_exc


def beam_search_from(start, beam_K=2000, wait_lookahead=50):
    """Beam search starting at `start`.

    State: (mk, t_dep_chosen, cur, exc_used, visited_mask, path, dvs_used)
      mk = current makespan = arrival_time at cur
      t_dep_chosen = the t_quantum used for last edge (= arrival of cur)
      visited_mask = bitmask of visited nodes
    """
    cheap = _GLOB['cheap']
    exc = _GLOB['exc']
    n = _GLOB['n']
    n_exc = _GLOB['n_exc']
    t_starts = _GLOB['t_starts']
    T = len(t_starts)

    # Initial state: at start, time=0, no exc used, just start visited
    init_mask = 1 << start
    # (mk, cur, exc_used, mask, path_tuple, edges_tuple)
    beam = [(0.0, start, 0, init_mask, (start,), ())]

    for depth in range(n - 1):
        children = []
        for mk, cur, exc_used, mask, path, edges in beam:
            # Look for j unvisited, find earliest feasible t' >= ceil(mk)
            t_min = int(np.ceil(mk))
            t_max = min(T, t_min + wait_lookahead)
            for j in range(n):
                if mask & (1 << j):
                    continue
                # cheap-search
                cheap_slice = cheap[cur, j, t_min:t_max]
                cheap_idx = np.where(np.isfinite(cheap_slice))[0]
                cheap_best = None
                if len(cheap_idx) > 0:
                    # take earliest arrival = t' + tof
                    earliest_idx = cheap_idx[0]
                    t_dep = t_min + earliest_idx
                    tof = cheap_slice[earliest_idx]
                    arr = t_dep + tof
                    # actually scan a few options — earliest tof may not be earliest arrival
                    # since tof varies with t
                    for k in cheap_idx[:5]:
                        td = t_min + k
                        tf = cheap_slice[k]
                        a = td + tf
                        if cheap_best is None or a < cheap_best[2]:
                            cheap_best = (td, tf, a, False)
                # exc-search if budget allows
                exc_best = None
                if exc_used < n_exc:
                    exc_slice = exc[cur, j, t_min:t_max]
                    exc_idx = np.where(np.isfinite(exc_slice))[0]
                    if len(exc_idx) > 0:
                        # search earliest arrival
                        for k in exc_idx[:5]:
                            td = t_min + k
                            tf = exc_slice[k]
                            a = td + tf
                            # only useful if better than cheap
                            if cheap_best is not None and a >= cheap_best[2]:
                                continue
                            if exc_best is None or a < exc_best[2]:
                                exc_best = (td, tf, a, True)
                # Add up to 2 candidates: cheap (if exists) and exc (if better)
                for best in (cheap_best, exc_best):
                    if best is None:
                        continue
                    td, tf, arr, is_exc = best
                    new_mask = mask | (1 << j)
                    new_exc = exc_used + (1 if is_exc else 0)
                    new_path = path + (j,)
                    new_edges = edges + ((td, tf, is_exc),)
                    children.append((arr, j, new_exc, new_mask,
                                     new_path, new_edges))
        if not children:
            return None
        # Beam selection: by mk (ascending)
        children.sort(key=lambda s: s[0])
        beam = children[:beam_K]
        if depth % 8 == 0:
            best_mk = beam[0][0]
            # depth+1 nodes visited (start + depth additions)
            pass
    # Pick best full-tour state
    if not beam:
        return None
    best = beam[0]
    return best


def _worker(args):
    start, beam_K, wait_lookahead = args
    t0 = time.time()
    result = beam_search_from(start, beam_K, wait_lookahead)
    wall = time.time() - t0
    if result is None:
        return start, None, wall
    return start, result, wall


def main(beam_K=2000, wait_lookahead=50, workers=8):
    kt = KTTSP(INST)
    n = kt.n
    print(f"E-505 beam search: n={n}, beam_K={beam_K}, "
          f"wait_lookahead={wait_lookahead}d, workers={workers}", flush=True)
    print(f"Bank=142.9183d, R3=111.76d, R1=101.65d (Team HRI)", flush=True)

    args_list = [(s, beam_K, wait_lookahead) for s in range(n)]
    t_start = time.time()
    best_overall = None  # (mk, start, path, edges)
    results = []
    with mp.Pool(workers, initializer=_init,
                 initargs=(None, None, n, kt.n_exc)) as p:
        for start, result, wall in p.imap_unordered(_worker, args_list):
            if result is None:
                print(f"  start={start:2d}: INFEASIBLE  ({wall:.0f}s)", flush=True)
                results.append((start, None))
                continue
            mk, _cur, exc_used, _mask, path, edges = result
            results.append((start, mk))
            if best_overall is None or mk < best_overall[0]:
                best_overall = (mk, start, path, edges, exc_used)
                marker = " ★ NEW BEST"
                if mk < 142.9183:
                    marker += " (UNDER BANK!)"
                if mk < 111.76:
                    marker += " (UNDER R3!)"
                if mk < 101.65:
                    marker += " (UNDER R1!)"
                print(f"  start={start:2d}: mk={mk:.3f}d  exc={exc_used}  "
                      f"({wall:.0f}s){marker}", flush=True)
            else:
                print(f"  start={start:2d}: mk={mk:.3f}d  exc={exc_used}  "
                      f"({wall:.0f}s)", flush=True)
    wall = time.time() - t_start
    print(f"\n=== E-505 complete: wall={wall:.0f}s ===", flush=True)

    if best_overall is None:
        print("FAIL: no feasible tour found", flush=True)
        return None

    mk, start, path, edges, exc_used = best_overall
    print(f"\nBest: start={start}, mk={mk:.4f}d, exc={exc_used}, "
          f"perm={list(path)}", flush=True)

    # VALIDATE via UDP
    times = [e[0] for e in edges]
    tofs = [e[1] for e in edges]
    perm = list(path)
    x = times + tofs + [float(p) for p in perm]
    fit = kt.fitness(x)
    feas = kt.is_feasible(fit)
    print(f"UDP fitness: {list(fit)}  feas={feas}", flush=True)

    if not feas:
        print("Beam result NOT feasible under UDP; re-walking chronologically",
              flush=True)
        times, tofs, dvs, ok, exc, k = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
        if ok:
            mk_walk = times[-1] + tofs[-1]
            x = times + tofs + [float(p) for p in perm]
            fit = kt.fitness(x)
            feas = kt.is_feasible(fit)
            print(f"Re-walk: mk={mk_walk:.4f}d, fitness={list(fit)}, feas={feas}",
                  flush=True)

    if feas and mk < 142.9183:
        bak = OUT + ".bak.20260530"
        from pathlib import Path
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"Backed up bank to {bak}", flush=True)
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(x),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f"\n>>> BANKED: {OUT}  mk={mk:.4f}d ({142.9183 - mk:.4f}d under prev)",
              flush=True)

    return {"best_mk_d": mk, "best_start": start, "best_perm": perm,
            "best_exc_used": exc_used, "wall_s": wall, "udp_feasible": feas}


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    L = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    res = main(beam_K=K, wait_lookahead=L, workers=W)
    if res:
        print(json.dumps({k: v for k, v in res.items() if k != 'best_perm'},
                          indent=2))
