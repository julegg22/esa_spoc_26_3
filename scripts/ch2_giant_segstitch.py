"""E-667: Ch2-large GIANT segment-stitch completer — uses the proven 0.30 d/leg phasing AND completes.

Established (E-664..666): faithful greedy phases the easy core (~350/601) at 0.30 d/leg (rank-1 level)
but STALLS on the hard-shell tail — its neighbors' cheap windows are FURTHER than the 40d Lambert wait
can see. SA-from-913 is basin-locked. KEY: the epoch TABLE sees the FULL ~1000d horizon (120 buckets),
so it can locate a neighbor's cheap window anywhere ahead — exactly what the bounded Lambert wait misses.

Method: faithful greedy for the cheap core (neighbor cheap-now or short ≤6d wait, ACCURATE Lambert).
On stall → TABLE-STITCH: among unvisited e533-neighbors of cur, find the earliest FUTURE bucket with a
finite table tof (full horizon), FAITHFULLY verify that hop, jump there (a "stitch", = segment boundary),
continue. Completes by construction (giant is one cheap-component). Report final makespan + #stitches.
If makespan ≪ 913 (esp ~300-500) → build full assembly → likely rank-1. Usage: python ch2_giant_segstitch.py [wall] [nseed]
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
WAIT = np.round(np.arange(0.5, 6.01, 0.5), 3)    # short cheap-core wait (accurate Lambert)
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def table_stitch(tab, epochs, cur, unvis_neigh, t):
    """Among cur's unvisited e533-neighbors, earliest FUTURE-bucket cheap window (full horizon).
    Returns (departure_epoch, j) of the min-arrival stitch, or (None, None)."""
    ne = len(epochs); bi0 = int(np.searchsorted(epochs, t)); best = None
    for j in unvis_neigh:
        row = tab.get((cur, j))
        if row is None:
            continue
        for bi in range(min(bi0, ne - 1), ne):
            tof = row[bi]
            if np.isfinite(tof):
                dep = max(t, float(epochs[bi])); arr = dep + tof
                if best is None or arr < best[0]:
                    best = (arr, dep, j)
                break
    return (best[1], best[2]) if best else (None, None)


def build(kt, neigh, gset, tab, epochs, start, entry, log):
    vis = {start}; order = [start]; cur = start; t = entry; t0 = time.time(); m = len(gset)
    stitches = 0
    while len(order) < m:
        best = None  # (arrival, j)  cheap core: neighbor now or short wait
        for j in neigh[cur]:
            if j in vis:
                continue
            tof = leg(kt, cur, j, t)
            if tof is not None and (best is None or t + tof < best[0]):
                best = (t + tof, j)
        if best is None:
            for w in WAIT:
                tw = t + float(w)
                if tw + 0.05 >= kt.max_time:
                    break
                for j in neigh[cur]:
                    if j in vis:
                        continue
                    tof = leg(kt, cur, j, tw)
                    if tof is not None and (best is None or tw + tof < best[0]):
                        best = (tw + tof, j)
                if best is not None:
                    break
        if best is None:                              # STITCH via table (full horizon)
            unv_neigh = [j for j in neigh[cur] if j not in vis]
            dep, j = table_stitch(tab, epochs, cur, unv_neigh, t)
            if dep is not None:
                tof = leg(kt, cur, j, dep)            # faithfully verify the stitch hop
                if tof is not None:
                    best = (dep + tof, j); stitches += 1
            if best is None:                          # neighbors exhausted → table over ALL unvisited
                allunv = [j for j in gset if j not in vis]
                dep, j = table_stitch(tab, epochs, cur, allunv, t)
                if dep is not None:
                    tof = leg(kt, cur, j, dep)
                    if tof is not None:
                        best = (dep + tof, j); stitches += 1
        if best is None:
            log(f"  STRAND at {len(order)}/{m} ep={t:.0f} stitches={stitches}"); return None, None, stitches
        arr, j = best; order.append(j); vis.add(j); t = arr; cur = j
        if len(order) % HB == 0:
            log(f"  build {len(order)}/{m} ep={t:.0f} ({t/max(len(order)-1,1):.2f} d/leg) "
                f"stitch={stitches} [{time.time()-t0:.0f}s c{len(_C)}]")
    return order, t - entry, stitches


def main(seed=0, wall_s=20 * 3600, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): [int(j) for j in np.where(adj[c])[0] if int(j) in gset] for c in gnodes}
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    log = lambda s: print(f"[s{seed}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    bank_g = [c for c in bperm if c in gset]
    rng = random.Random(seed * 41 + 5)
    start = bank_g[0] if seed == 0 else gnodes[rng.randrange(m)]
    log(f"SEG-STITCH build (start {start}, {m} cities; bank-giant 913@1.53; target ~240@0.4)")
    t0 = time.time()
    order, mk, st = build(kt, neigh, gset, tab, epochs, start, entry, log)
    if order is None:
        log("seg-stitch stranded"); return
    log(f"*** SEG-STITCH giant = {mk:.1f}d ({mk/(m-1):.3f} d/leg) stitches={st} [{time.time()-t0:.0f}s] "
        f"vs bank 913 -> {'BEATS BANK, build full assembly' if mk < 913 else 'no improvement'}")
    json.dump({'giant_order': order, 'faithful_mk': float(mk), 'stitches': st, 'start': start},
              open(f'/tmp/ch2_segstitch_giant_s{seed}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    wall = float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    ps = [mp.Process(target=main, args=(s, wall, 0.0)) for s in range(ns)]
    for p in ps: p.start()
    for p in ps: p.join()
