"""PART 3 — saturation/regret-aware chrono-walk reconstructor.

From-scratch greedy that builds a 1051-node tour evaluated by the TRUE
chronological walk (departure >= prev arrival; cheap transfer via
find_earliest_transfer; <=5 exceptions). Smarter node selection than pure
earliest-arrival:
  - 'earliest'   : baseline -- pick the unvisited node with the smallest
                   feasible cheap arrival epoch (classic greedy).
  - 'regret'     : among the K cheapest-arrival candidates, pick the one whose
                   *second*-best alternative is much worse (about to lose a good
                   escape) -> regret-style.
  - 'chokepoint' : penalize picking a node that is the UNIQUE near-term cheap
                   neighbor of some still-unvisited node (preserve chokepoints).
  - 'degree'     : tie-break toward visiting low-cheap-degree nodes early.

The expensive primitive is find_earliest_transfer(cur, j, t, ...). To keep the
walk tractable on n=1051 we evaluate cheap transfers from the current node to a
CANDIDATE SET of unvisited nodes (a precomputed cheap-neighbor shortlist),
falling back to a broader scan when the shortlist is exhausted. Exceptions
(dv in (100,600]) are used only when no cheap continuation exists.

Multi-start over policies + RNG seeds. Reports best feasible makespan per
policy; writes the best beating-932.53 candidate to /tmp.
"""
import json, time, sys, os
import numpy as np
from multiprocessing import Pool
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer

INST = ('reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson '
        'Problem/problems/hard.kttsp')
DV_THR = 100.0
DV_EXC = 600.0
N_EXC = 5
WIN_CHEAP = 4.0
NS_CHEAP = 28      # ~0.14d grid for cheap-leg tof (walk arrival probe)
WIN_EXC = 3.0
NS_EXC = 48
CAND_CAP = 18      # cap cheap candidates evaluated per walk step (speed)
BANK_MS = 932.5304126719427

kt = KTTSP(INST)
N = kt.n
MAXT = kt.max_time

# ----- precompute a cheap-neighbor shortlist at a few epochs -----
# We use the Part-1/Part-2 style scan but reuse if available; else build a
# light shortlist: for each node, candidate targets that were cheap at >=1 of
# a few probe epochs. This bounds the per-step candidate set.
SHORTLIST_PATH = '/tmp/ch2_large_p3_shortlist.json'

_sl_kt = None
def _sl_init():
    global _sl_kt
    _sl_kt = KTTSP(INST)

def _sl_node(args):
    i, probe_epochs, ns, win = args
    kt = _sl_kt
    cand = set()
    for ep in probe_epochs:
        for j in range(kt.n):
            if j == i:
                continue
            tof, dv = find_earliest_transfer(kt, i, j, ep, DV_THR, win, ns)
            if tof is not None:
                cand.add(int(j))
    return i, sorted(cand)

def build_shortlist(probe_epochs, ns=24, win=2.5):
    """For each node, the set of targets cheap at >=1 probe epoch (parallel)."""
    print(f'building shortlist (parallel, {len(probe_epochs)} epochs, ns={ns})',
          flush=True)
    t0 = time.time()
    shortlist = {}
    tasks = [(i, probe_epochs, ns, win) for i in range(N)]
    with Pool(4, initializer=_sl_init) as pool:
        for cnt, (i, cand) in enumerate(pool.imap_unordered(_sl_node, tasks)):
            shortlist[i] = cand
            if (cnt + 1) % 50 == 0:
                avg = np.mean([len(v) for v in shortlist.values()])
                print(f'  shortlist {cnt+1}/{N} {time.time()-t0:.0f}s '
                      f'avg_deg={avg:.1f}', flush=True)
                json.dump({str(k): v for k, v in shortlist.items()},
                          open(SHORTLIST_PATH, 'w'))
    json.dump({str(k): v for k, v in shortlist.items()},
              open(SHORTLIST_PATH, 'w'))
    print(f'shortlist done {time.time()-t0:.0f}s', flush=True)
    return shortlist

def load_or_build_shortlist():
    probe = np.linspace(0, MAXT - win_guard(), 2).tolist()
    allow_partial = os.environ.get('ALLOW_PARTIAL', '0') == '1'
    if os.path.exists(SHORTLIST_PATH):
        d = json.load(open(SHORTLIST_PATH))
        sl = {int(k): v for k, v in d.items()}
        if len(sl) == N:
            print('loaded full shortlist from cache', flush=True)
            return sl
        if allow_partial:
            print(f'loaded PARTIAL shortlist ({len(sl)}/{N}); walk uses live '
                  'fallback for missing nodes', flush=True)
            return sl
    return build_shortlist(probe)

def win_guard():
    return WIN_CHEAP + 1

# ----- chrono walk with a node-selection policy -----
def cheap_arrival(cur, j, t):
    tof, dv = find_earliest_transfer(kt, cur, j, t, DV_THR, WIN_CHEAP, NS_CHEAP)
    if tof is None:
        return None
    return tof, dv

def exc_transfer(cur, j, t):
    """Earliest transfer with dv<=600 (allow exception)."""
    tof, dv = find_earliest_transfer(kt, cur, j, t, DV_EXC, WIN_EXC, NS_EXC)
    if tof is None:
        return None
    return tof, dv

def build_tour(start, policy, shortlist, regret_k=5, rng=None,
               max_exc=N_EXC, t_max=MAXT):
    """Greedy chrono walk. Returns (perm, times, tofs, ok)."""
    visited = np.zeros(N, dtype=bool)
    perm = [start]; visited[start] = True
    times = []; tofs = []
    t = 0.0
    exc_used = 0
    cur = start
    for step in range(N - 1):
        # candidate set: unvisited nodes in shortlist[cur], capped for speed.
        cands = [j for j in shortlist.get(cur, []) if not visited[j]]
        if len(cands) > CAND_CAP:
            # prefer low-remaining-degree (regret) + some hubs for diversity
            cands_sorted = sorted(cands, key=lambda j: INDEG[j])
            cands = cands_sorted[:CAND_CAP - 6] + cands_sorted[-6:]
        # gather cheap arrivals
        opts = []  # (arrival, tof, dv, j)
        for j in cands:
            r = cheap_arrival(cur, j, t)
            if r is not None:
                tof, dv = r
                opts.append((t + tof, tof, dv, j))
        chosen = None
        if opts:
            opts.sort()  # by arrival epoch
            if policy == 'earliest':
                chosen = opts[0]
            elif policy == 'degree':
                # among the regret_k earliest, prefer low remaining cheap-degree
                head = opts[:regret_k]
                def rem_deg(j):
                    return sum(1 for q in shortlist[j] if not visited[q])
                head.sort(key=lambda o: (rem_deg(o[3]), o[0]))
                chosen = head[0]
            elif policy == 'regret':
                # among the regret_k earliest candidate NODES, compute each
                # node's regret = (2nd best arrival - best arrival) is wrong
                # framing; instead regret = how much WORSE the *next* option
                # for that node would be if we skip now. Approx: prefer the
                # node whose best arrival is small AND whose shortlist of
                # remaining cheap nbrs is small (about to get stranded).
                head = opts[:regret_k]
                def regret(o):
                    j = o[3]
                    rem = sum(1 for q in shortlist[j] if not visited[q])
                    # high regret if few remaining cheap nbrs -> visit now
                    return (rem, o[0])
                head.sort(key=regret)
                chosen = head[0]
            elif policy == 'chokepoint':
                # avoid picking a node that is the UNIQUE near-term cheap
                # in-neighbor of some unvisited node. Penalize candidates that
                # many unvisited nodes depend on; among low-penalty, earliest.
                head = opts[:regret_k * 2]
                # cheap proxy: a node with very high cheap-degree is a hub,
                # safe to consume; a node that is rare in others' shortlists
                # is a chokepoint we should defer. Use global in-degree.
                def penalty(o):
                    j = o[3]
                    # in-degree proxy already precomputed
                    return (-INDEG[j], o[0])  # consume high-indeg (hubs) first
                head.sort(key=penalty)
                chosen = head[0]
            else:
                chosen = opts[0]
        if chosen is None:
            # no cheap continuation -> try exception
            if exc_used >= max_exc:
                return None  # dead end, infeasible
            best_exc = None
            scan_set = ([j for j in shortlist.get(cur, []) if not visited[j]]
                        or [j for j in range(N) if not visited[j]])
            for j in scan_set:
                r = exc_transfer(cur, j, t)
                if r is not None and r[1] > DV_THR:  # genuinely an exception
                    cand = (t + r[0], r[0], r[1], j)
                    if best_exc is None or cand[0] < best_exc[0]:
                        best_exc = cand
            if best_exc is None:
                # broad cheap re-scan as last resort, capped to GLOBAL_POOL
                pool = GLOBAL_POOL if GLOBAL_POOL is not None else range(N)
                for j in pool:
                    if visited[j]:
                        continue
                    r = cheap_arrival(cur, j, t)
                    if r is not None:
                        cand = (t + r[0], r[0], r[1], j)
                        if best_exc is None or cand[0] < best_exc[0]:
                            best_exc = cand
                if best_exc is not None and best_exc[2] > DV_THR:
                    exc_used += 1
                if best_exc is None:
                    return None
            else:
                exc_used += 1
            chosen = best_exc
        arr, tof, dv, j = chosen
        if arr > t_max:
            return None
        times.append(t); tofs.append(tof)
        perm.append(j); visited[j] = True
        t = arr; cur = j
    return perm, times, tofs, True

def assemble_dv(times, tofs, perm):
    return np.array(list(times) + list(tofs) + [float(p) for p in perm])

# global in-degree (built once from shortlist)
INDEG = None
GLOBAL_POOL = None
def build_indeg(shortlist):
    indeg = np.zeros(N)
    for i, nbrs in shortlist.items():
        for j in nbrs:
            indeg[j] += 1
    return indeg

def main():
    global INDEG, GLOBAL_POOL
    shortlist = load_or_build_shortlist()
    INDEG = build_indeg(shortlist)
    # bound fallback scans to the union of all known cheap targets + sources
    pool = set(shortlist.keys())
    for nbrs in shortlist.values():
        pool.update(nbrs)
    GLOBAL_POOL = sorted(pool)
    avg_deg = np.mean([len(v) for v in shortlist.values()])
    print(f'shortlist avg cheap-degree={avg_deg:.1f} '
          f'global_pool={len(GLOBAL_POOL)}', flush=True)

    import os
    policies = os.environ.get('POLICIES', 'earliest,regret,degree,chokepoint'
                              ).split(',')
    rng = np.random.default_rng(2026)
    # multi-start: a few start nodes (high-degree hubs + random)
    deg_order = np.argsort(-INDEG)
    nstarts = int(os.environ.get('NSTARTS', '2'))
    starts = [int(deg_order[i]) for i in [0, 10, 25, 50][:nstarts]]
    starts = list(dict.fromkeys(int(s) for s in starts))

    best_overall = None
    summary = {}
    t0 = time.time()
    for policy in policies:
        best_ms = None; best_dv = None; n_feas = 0; n_attempt = 0
        for st in starts:
            n_attempt += 1
            res = build_tour(st, policy, shortlist, rng=rng)
            if res is None:
                print(f'  [{policy}] start={st}: dead-end (infeasible)',
                      flush=True)
                continue
            perm, times, tofs, ok = res
            if len(perm) != N:
                print(f'  [{policy}] start={st}: incomplete len={len(perm)}',
                      flush=True)
                continue
            dv = assemble_dv(times, tofs, perm)
            f = kt.fitness(dv)
            feas = kt.is_feasible(f)
            ms = f[0]
            print(f'  [{policy}] start={st}: ms={ms:.2f} feas={feas}',
                  flush=True)
            if feas:
                n_feas += 1
                if best_ms is None or ms < best_ms:
                    best_ms = ms; best_dv = dv
        summary[policy] = {'best_ms': best_ms, 'n_feas': n_feas,
                           'n_attempt': n_attempt}
        if best_ms is not None and (best_overall is None
                                    or best_ms < best_overall[0]):
            best_overall = (best_ms, best_dv, policy)
        json.dump(summary, open('/tmp/ch2_large_part3_summary.json', 'w'))

    print('\n=== PART 3 RESULTS ===', flush=True)
    for p, s in summary.items():
        bm = s['best_ms']
        print(f'  {p:11s}: best feasible ms = '
              f'{("%.2f d" % bm) if bm else "NONE"}  '
              f'({s["n_feas"]}/{s["n_attempt"]} feasible starts)')
    print(f'  BANK = {BANK_MS:.2f} d', flush=True)
    if best_overall and best_overall[0] < BANK_MS:
        ms, dv, pol = best_overall
        cand = [{'decisionVector': [float(x) for x in dv],
                 'problem': 'large',
                 'challenge': 'spoc-4-keplerian-tomato-traveling-salesperson'}]
        json.dump(cand, open('/tmp/ch2_large_reconstruct_cand.json', 'w'))
        # re-verify
        f = kt.fitness(np.array(dv))
        print(f'\n*** BEAT BANK: {ms:.2f} d via {pol} '
              f'(bank {BANK_MS:.2f}); wrote /tmp candidate; '
              f'reverify feas={kt.is_feasible(f)} viols={f[1:]}', flush=True)
    else:
        bo = best_overall[0] if best_overall else None
        print(f'\nNo feasible reconstruction beat bank. best='
              f'{("%.2f" % bo) if bo else "NONE"} d (bank {BANK_MS:.2f}).',
              flush=True)
    print('total', f'{time.time()-t0:.0f}s', flush=True)

if __name__ == '__main__':
    main()
