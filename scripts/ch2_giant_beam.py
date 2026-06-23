"""E-669: Ch2-large GIANT from-scratch BEAM search (user-approved global build; after LNS-from-913
confirmed basin-bound, only ~900 vs target ~405). Greedy (beam width 1) corner-paints: it strands the
hard-shell because it myopically picks the single min-arrival hop and paints into a temporal corner.
BEAM keeps the top-W partial giants and expands them SYNCHRONOUSLY (one city/round), pruning by
makespan — so non-greedy paths that AVOID the dead-ends survive even if the locally-greedy ones strand.

Expansion is TABLE-guided (fast, full-horizon cheap windows); each round, every live beam spawns its few
best cheap next-hops, all candidates pooled, top-W kept (with a light completability penalty favoring
beams whose current city still has unvisited cheap-neighbors → fights corner-painting). The best beam to
reach all 601 is FAITHFULLY retimed → true makespan vs bank-giant 913 / target ~405. Usage:
python ch2_giant_beam.py [W=400] [seed=0] [pen=1.0]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
TOF_WINDOW = 40.0; N_STEPS = 2400
DELAY = np.array([0.0, 0.5, 1.0, 1.5])
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def faithful_retime(kt, order, entry, log=None):
    t = entry; t0 = time.time()
    for k in range(len(order) - 1):
        best = None
        for d in DELAY:
            td = t + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof = leg(kt, order[k], order[k + 1], td)
            if tof is not None and (best is None or td + tof < best):
                best = td + tof
        if best is None:
            return None
        t = best
        if log and (k + 1) % 100 == 0:
            log(f"  retime leg {k+1}/{len(order)-1} ep={t:.0f} ({time.time()-t0:.0f}s)")
    return t - entry


def tarr(tab, epochs, a, b, t):
    row = tab.get((a, b))
    if row is None:
        return np.inf
    ne = len(epochs); bi0 = int(np.searchsorted(epochs, t))
    for bi in range(min(bi0, ne - 1), ne):
        tof = row[bi]
        if np.isfinite(tof):
            return max(t, float(epochs[bi])) + tof
    return np.inf


def beam_search(neigh, tab, epochs, start, entry, m, W, pen, log):
    """Synchronous beam over partial giants. Beam = (epoch, order_tuple, visited_frozenset).
    Each round: expand every beam by its best cheap next-hops (table arrival), score successors by
    arrival + pen*urgency(remaining cheap-degree of new city), keep top-W. Returns best full order."""
    # beam state stored as parallel lists for speed
    beams = [(entry, [start], {start}, start)]      # (epoch, order, visited, cur)
    t0 = time.time()
    for step in range(m - 1):
        cands = []  # (score, epoch, order, visited, cur)
        for ep, order, vis, cur in beams:
            succ = []
            for j in neigh[cur]:
                if j in vis:
                    continue
                arr = tarr(tab, epochs, cur, j, ep)
                if np.isfinite(arr):
                    succ.append((arr, j))
            succ.sort()
            for arr, j in succ[:6]:                  # each beam spawns its 6 best hops
                rem_deg = sum(1 for k in neigh[j] if k not in vis) - 1
                score = arr + pen * (1.0 / (rem_deg + 1))
                cands.append((score, arr, order, vis, j))
        if not cands:
            log(f"  beam DEAD at step {step+1}/{m} (all beams stranded)"); return None
        cands.sort(key=lambda x: x[0])
        # build next beams from top-W (dedupe identical (cur,len) to keep diversity)
        beams = []; seen = set()
        for score, arr, order, vis, j in cands:
            key = (j, len(order))
            if key in seen and len(beams) > W // 2:
                continue
            seen.add(key)
            nv = set(vis); nv.add(j)
            beams.append((arr, order + [j], nv, j))
            if len(beams) >= W:
                break
        if (step + 1) % 50 == 0:
            bestep = min(b[0] for b in beams)
            log(f"  beam step {step+1}/{m} live={len(beams)} best_ep={bestep:.0f} "
                f"({bestep/(step+1):.2f} d/leg) [{time.time()-t0:.0f}s]")
    # all beams now length m; return the min-epoch order
    beams.sort(key=lambda b: b[0])
    return beams[0][1]


def main(W=400, seed=0, pen=1.0, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): [int(j) for j in np.where(adj[c])[0] if int(j) in gset] for c in gnodes}
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    log = lambda s: print(f"[W{W}p{pen}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    start = [c for c in bperm if c in gset][0]
    log(f"BEAM from-scratch (W={W} pen={pen} start={start} {m} cities; bank 913@1.53, target ~405@0.68)")
    t0 = time.time()
    order = beam_search(neigh, tab, epochs, start, entry, m, W, pen, log)
    if order is None:
        log("beam stranded"); return
    if len(set(order)) != m:
        log(f"beam incomplete ({len(set(order))}/{m})"); return
    log(f"beam complete ({m} cities, table-epochs) [{time.time()-t0:.0f}s] — faithful retime next")
    mk = faithful_retime(kt, order, entry, log)
    if mk is None:
        log("beam order STRANDS faithfully"); return
    log(f"*** BEAM giant = {mk:.1f}d ({mk/(m-1):.3f} d/leg) [{time.time()-t0:.0f}s] vs bank 913, target ~405 "
        f"-> {'BEATS BANK' if mk < 913 else 'no improvement'}{' ★ RANK-1 REGIME' if mk < 450 else ''}")
    json.dump({'giant_order': order, 'faithful_mk': float(mk), 'W': W, 'pen': pen},
              open(f'/tmp/ch2_beam_giant_W{W}_p{pen}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    # 4 chains sweep penalty (corner-paint fighter) at fixed W
    pens = [0.0, 0.5, 2.0, 8.0]
    ps = [mp.Process(target=main, args=(W, s, pens[s], 0.0)) for s in range(4)]
    for p in ps: p.start()
    for p in ps: p.join()
