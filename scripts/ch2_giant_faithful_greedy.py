"""E-666: Ch2-large GIANT faithful time-aware greedy — the DECISIVE rank-1 test.

Root error found in E-664/665: the 120-bucket epoch TABLE (global-min-tof per pair) drastically
UNDERCOUNTS cheap transfers. Table-with-waiting gave ~7.7 d/leg (50 cities at ep~384) — far worse
than the bank's FAITHFUL 1.53 d/leg. The faithful find_earliest_transfer (scans tof at the actual
departure, early-exits on the first cheap one) finds cheap hops at almost ANY departure ⇒ no waiting
needed, cheap edges abundant. So construction MUST use the faithful evaluator, not the sparse table.

This: faithful nearest-arrival greedy restricted to the e533 cheap-NEIGHBORS of the current city
(likely-cheap pairs ⇒ find_earliest_transfer early-exits fast; non-neighbors would waste a full
2400-step None-scan). Per step pick the unvisited giant neighbor with EARLIEST faithful arrival at
the current departure. If none cheap, widen to all unvisited / small wait. Multi-start, heartbeats.
Decisive: does it phase the 601-giant well below the bank-giant 913 (target ~240 = TGMA 0.4 d/leg)?

Usage: python ch2_giant_faithful_greedy.py [wall_s] [n_seeds]
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
TOF_WINDOW = 40.0; N_STEPS = 2400; HB = 25
WAIT = np.round(np.arange(0.5, 40.01, 1.0), 3)    # extended: giant is 1 cheap-comp ⇒ a neighbor
# becomes cheap within ~orbital-period waiting → completes WITHOUT the catastrophic all-601 widen
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def faithful_greedy(kt, neigh, gset, start, entry, log, lam=0.0):
    """At (cur,t): among cheap-reachable unvisited NEIGHBORS, pick by score = arrival + lam*deg[j]
    where deg[j] = # of j's still-unvisited cheap-neighbors. lam=0 = pure min-arrival (corner-paints
    the low-degree tail). lam>0 = URGENCY: prefer soon-to-be-isolated (low-degree) cities first so
    they don't strand the endgame. If no neighbor cheap-now, bounded wait, then widen to unvisited."""
    vis = {start}; order = [start]; cur = start; t = entry; t0 = time.time(); m = len(gset)
    deg = {j: sum(1 for k in neigh[j] if k not in vis) for j in gset}
    while len(order) < m:
        best = None  # (score, arrival, j)
        for j in neigh[cur]:
            if j in vis:
                continue
            tof = leg(kt, cur, j, t)
            if tof is not None:
                sc = (t + tof) + lam * deg[j]
                if best is None or sc < best[0]:
                    best = (sc, t + tof, j)
        if best is None:                              # no neighbor cheap-now → bounded wait
            for w in WAIT:
                tw = t + float(w)
                if tw + 0.05 >= kt.max_time:
                    break
                for j in neigh[cur]:
                    if j in vis:
                        continue
                    tof = leg(kt, cur, j, tw)
                    if tof is not None:
                        sc = (tw + tof) + lam * deg[j]
                        if best is None or sc < best[0]:
                            best = (sc, tw + tof, j)
                if best is not None:
                    break
        if best is None:                              # last resort: ALL unvisited over extended wait
            for j in gset:
                if j in vis:
                    continue
                for w in WAIT:
                    tw = t + float(w)
                    if tw + 0.05 >= kt.max_time:
                        break
                    tof = leg(kt, cur, j, tw)
                    if tof is not None:
                        if best is None or tw + tof < best[1]:
                            best = (tw + tof, tw + tof, j)
                        break
        if best is None:
            log(f"  STRAND at {len(order)}/{m} ep={t:.0f}"); return None, None
        _, arr, j = best; order.append(j); vis.add(j); t = arr; cur = j
        for k in neigh[j]:                            # j now visited → drop its neighbors' degree
            if k in deg:
                deg[k] -= 1
        if len(order) % HB == 0:
            log(f"  greedy {len(order)}/{m} ep={t:.0f} ({t/max(len(order)-1,1):.2f} d/leg) "
                f"lam={lam} [{time.time()-t0:.0f}s c{len(_C)}]")
    return order, t - entry


def main(seed=0, wall_s=20 * 3600, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): [int(j) for j in np.where(adj[c])[0] if int(j) in gset] for c in gnodes}
    log = lambda s: print(f"[s{seed}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    bank_g = [c for c in bperm if c in gset]
    rng = random.Random(seed * 41 + 5)
    LAMS = {0: 0.0, 1: 0.05, 2: 0.15, 3: 0.4}        # urgency weight per chain (d per degree-unit)
    lam = LAMS[seed % 4]
    start = bank_g[0]                                 # all chains start at bank-giant's first city
    log(f"FAITHFUL greedy (start {start}, {m} cities, lam={lam}; bank 913@1.53; target ~240@0.4)")
    t0 = time.time()
    order, mk = faithful_greedy(kt, neigh, gset, start, entry, log, lam)
    if order is None:
        log("greedy stranded"); return
    log(f"*** FAITHFUL giant = {mk:.1f}d ({mk/(m-1):.3f} d/leg) [{time.time()-t0:.0f}s] vs bank 913 "
        f"-> {'BEATS BANK, build full assembly' if mk < 913 else 'no improvement'}")
    json.dump({'giant_order': order, 'faithful_mk': float(mk), 'start': start},
              open(f'/tmp/ch2_faithgreedy_giant_s{seed}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    wall = float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    ps = [mp.Process(target=main, args=(s, wall, 0.0)) for s in range(ns)]
    for p in ps: p.start()
    for p in ps: p.join()
