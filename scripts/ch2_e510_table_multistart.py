"""E-510 — Table-based multi-start greedy construction + per-start LNS.

Construct tours from all 49 start nodes using the fine edge table (fast
table greedy), then LNS each in parallel. This produces structurally
different starting perms than the bank.

For each start s:
  perm = [s], cur = s, t = 0, exc = 0
  while unvisited:
    find earliest-arrival cheap edge (or exc if no cheap and budget left)
    append j, update t = arrival
  return perm if complete

Then LNS each perm for ~2 min and validate top 50 from each with Lambert.
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


def table_greedy(start, cheap, exc, quantum, n_exc_budget=5, window_q=300):
    """Construct a tour greedily using fine table.

    At each step, evaluate ALL unvisited j's earliest-arrival across cheap
    and exc. Pick j with minimum arrival (prefer cheap unless infeasible).
    """
    n = cheap.shape[0]
    T = cheap.shape[2]
    visited = {start}
    perm = [start]
    cur = start
    t_d = 0.0
    exc_used = 0
    while len(visited) < n:
        t_min_q = int(np.ceil(t_d / quantum))
        if t_min_q >= T:
            return None
        t_max_q = min(T, t_min_q + window_q)
        best_arr = np.inf
        best_pick = None  # (j, t_dep_q, tof, is_exc)
        for j in range(n):
            if j in visited: continue
            cs = cheap[cur, j, t_min_q:t_max_q]
            cmask = np.isfinite(cs)
            if cmask.any():
                idxs = np.arange(t_min_q, t_max_q)
                arrs = idxs * quantum + cs
                k = int(np.argmin(np.where(cmask, arrs, np.inf)))
                a = float(arrs[k])
                if a < best_arr:
                    best_arr = a
                    best_pick = (j, t_min_q + k, float(cs[k]), False)
            elif exc_used < n_exc_budget:
                es = exc[cur, j, t_min_q:t_max_q]
                emask = np.isfinite(es)
                if emask.any():
                    idxs = np.arange(t_min_q, t_max_q)
                    arrs = idxs * quantum + es
                    k = int(np.argmin(np.where(emask, arrs, np.inf)))
                    a = float(arrs[k])
                    if a < best_arr:
                        best_arr = a
                        best_pick = (j, t_min_q + k, float(es[k]), True)
        if best_pick is None:
            return None
        j, td_q, tof, ie = best_pick
        perm.append(j)
        visited.add(j)
        cur = j
        t_d = best_arr
        if ie:
            exc_used += 1
    return perm


def _construct(args):
    start = args
    cheap = _GLOB['cheap']; exc = _GLOB['exc']
    quantum = _GLOB['quantum']
    p = table_greedy(start, cheap, exc, quantum, n_exc_budget=5)
    if p is None or len(p) != _GLOB['n']:
        return start, None
    mk, _td, _tof, _eu, ok = fast_walk(p, cheap, exc, quantum,
                                       n_exc_budget=5, window_q=300,
                                       exc_policy='cheap_unless_infeasible')
    if not ok:
        return start, None
    return start, (mk, p)


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
    it = 0
    while time.time() - t0 < T_max:
        it += 1
        cand = make_random_move(cur_perm, rng)
        if cand == cur_perm: continue
        mk, _, _, _, ok = fast_walk(cand, cheap, exc, quantum, **walk_kwargs)
        n_walks += 1
        if not ok: continue
        n_feas += 1
        if mk < init_fmk + 25:
            top_perms.append((mk, list(cand)))
        delta = mk - cur_mk
        if delta < 0 or rng.random() < (2.718 ** (-delta / max(T, 0.1))):
            cur_mk = mk; cur_perm = cand; n_acc += 1
            if mk < best_mk: best_mk = mk; best_perm = list(cand)
        T = max(T_min, T * T_decay)
        if it > 0 and it % 8000 == 0:
            cur_perm = list(best_perm); cur_mk = best_mk; T = 8.0
    return seed_id, best_mk, best_perm, top_perms


def main(T_max_per_worker=600, workers=8):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE missing", flush=True); return
    kt = KTTSP(INST)
    n = kt.n
    _init()
    bank_mk = 142.8913

    # Phase 1: construct 49 tours
    print(f"Phase 1: constructing tours from {n} starts via table-greedy",
           flush=True)
    constructions = {}
    with mp.Pool(workers, initializer=_init) as p:
        for start, result in p.imap_unordered(_construct, list(range(n))):
            if result is not None:
                fmk, perm = result
                constructions[start] = (fmk, perm)
                print(f"  start={start:2d}: fmk={fmk:.2f}d", flush=True)
            else:
                print(f"  start={start:2d}: failed", flush=True)
    print(f"\nConstructed {len(constructions)}/{n} feasible tours",
           flush=True)
    if not constructions:
        return

    # Pick top 8 by fmk for LNS
    sorted_starts = sorted(constructions.items(), key=lambda kv: kv[1][0])
    print(f"\nTop 10 constructed (start, fmk):")
    for s, (fmk, _) in sorted_starts[:10]:
        print(f"  start={s}: fmk={fmk:.2f}d", flush=True)

    # Phase 2: LNS from top 8
    print(f"\nPhase 2: LNS from top {workers} (each {T_max_per_worker}s)",
           flush=True)
    args = [(f"s{s}", p, fmk, T_max_per_worker)
            for s, (fmk, p) in sorted_starts[:workers]]
    t0 = time.time()
    all_top = []
    best_overall = (1e9, None)
    with mp.Pool(workers, initializer=_init) as p:
        for sid, mk, perm, tops in p.imap_unordered(lns_worker, args):
            print(f"  [{sid}] best fmk={mk:.2f} ({len(tops)} top)",
                   flush=True)
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
    print(f"Unique: {len(uniq)} fmk range: {uniq[0][0]:.2f} - {uniq[-1][0]:.2f}",
           flush=True)

    # Phase 3: Validate top 1500
    K = min(1500, len(uniq))
    print(f"\nPhase 3: Lambert validation of top {K}", flush=True)
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
            mark = " UNDER BANK" if best_for_perm[0] < bank_mk else ""
            print(f"  [{ix:4d}] fmk={fmk:.2f} → lambert={best_for_perm[0]:.4f}d{mark}",
                   flush=True)
        if time.time() - last_print > 60:
            print(f"  ... [{ix}/{K}] best={best_lambert[0]:.4f}", flush=True)
            last_print = time.time()
    print(f"\nValidation wall: {time.time() - t_val:.0f}s", flush=True)

    if best_lambert and best_lambert[0] < bank_mk:
        bak = OUT + ".bak.20260530.v3"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_lambert[1]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_lambert[0]:.4f}d "
              f"({bank_mk - best_lambert[0]:.4f}d under prev)", flush=True)


if __name__ == "__main__":
    tw = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    main(T_max_per_worker=tw)
