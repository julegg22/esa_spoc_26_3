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
    """Arrival a->b departing >= t. CHEAP-NOW: if the floor/current bucket is cheap, depart at the
    ACTUAL epoch t (tof ~ const within the 4d bucket) — avoids baking in ~2d discretization wait per
    hop. Only WAIT (to a grid epoch) when no near bucket is cheap."""
    row = tab.get((a, b))
    if row is None:
        return np.inf
    ne = len(epochs); bi = int(np.searchsorted(epochs, t))
    for c in (bi - 1, bi):                            # cheap-now: floor or current bucket
        if 0 <= c < ne and np.isfinite(row[c]):
            return t + float(row[c])
    for c in range(bi + 1, ne):                       # else genuine wait to next cheap bucket
        if np.isfinite(row[c]):
            return float(epochs[c]) + float(row[c])
    return np.inf


def tbl_epochs(tab, epochs, order, entry):
    """Table-walk epochs along an order (approx; faithful retime is the judge). inf-leg → carry."""
    t = entry; ep = [entry]
    for k in range(len(order) - 1):
        a = tarr(tab, epochs, order[k], order[k + 1], t)
        t = a if np.isfinite(a) else t + 8.0
        ep.append(t)
    return ep


def repair_insert(order, missing, neigh, tab, epochs, entry, log):
    """Insert each stranded city at its cheapest TIME-FEASIBLE slot (dense-table arrival), restricted
    to cheap-neighbor positions ⇒ a hard-tail city can land EARLY where its window is open. Order
    missing by FEWEST feasible slots first (most-constrained). Returns completed order (best effort)."""
    cur = order[:]
    pending = list(missing)
    for _ in range(len(pending) + 2):
        if not pending:
            break
        ep = tbl_epochs(tab, epochs, cur, entry)
        placed = []
        # most-constrained-first: compute each pending city's best slot, insert the tightest
        scored = []
        for u in pending:
            nb = neigh[u]
            best = None
            for p in range(1, len(cur)):
                if cur[p - 1] not in nb and cur[p] not in nb:
                    continue
                arr_au = tarr(tab, epochs, cur[p - 1], u, ep[p - 1])
                if not np.isfinite(arr_au):
                    continue
                arr_ub = tarr(tab, epochs, u, cur[p], arr_au)
                if not np.isfinite(arr_ub):
                    continue
                cost = arr_ub - ep[p]
                if best is None or cost < best[0]:
                    best = (cost, p)
            if best is not None:
                scored.append((best[0], best[1], u))
        if not scored:
            log(f"  repair: {len(pending)} cities have NO feasible cheap slot — left out"); break
        scored.sort()
        # insert the cheapest-cost placement this round, then recompute epochs
        cost, p, u = scored[0]
        cur.insert(p, u); pending.remove(u)
    return cur, pending


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
            for arr, j in succ[:10]:                 # each beam spawns its 10 best hops (diversity)
                rem_deg = sum(1 for k in neigh[j] if k not in vis)   # unvisited nbrs of j
                score = arr + pen * (1.0 / (rem_deg + 1))
                cands.append((score, arr, order, vis, j))
        if not cands:
            best = min(beams, key=lambda b: b[0])     # deepest partial reached (rank-1 phased)
            log(f"  beam DEAD at step {step+1}/{m} — return best partial len={len(best[1])} ep={best[0]:.0f}")
            return best[1]
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
    d = np.load('/tmp/ch2_giant_dense.npz', allow_pickle=True)   # E-670 ACCURATE cheap-window data
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
    if len(set(order)) != m:                          # repair stranded tail by cheap-window insertion
        missing = [c for c in gnodes if c not in set(order)]
        pmk = faithful_retime(kt, order, entry) or -1  # faithful makespan of the WELL-PHASED partial
        json.dump({'partial_order': order, 'missing': missing, 'partial_mk': float(pmk),
                   'pen': pen}, open(f'/tmp/ch2_beam_partial_p{pen}.json', 'w'))
        log(f"beam partial {len(set(order))}/{m} (faithful_mk={pmk:.0f}); repairing {len(missing)} via cheap-window insertion")
        order, still = repair_insert(order, missing, neigh, tab, epochs, entry, log)
        if len(set(order)) != m:
            log(f"after repair still {len(set(order))}/{m} ({len(still)} unplaceable) — faithful retime of partial+placed anyway")
    log(f"order len={len(set(order))}/{m} [{time.time()-t0:.0f}s] — faithful retime next")
    mk = faithful_retime(kt, order, entry, log)
    L = len(order)
    if mk is None:
        log("beam order STRANDS faithfully"); return
    tag = ' ★ RANK-1 REGIME' if (mk < 450 and L == m) else ('' if L == m else f' (PARTIAL {L}/{m})')
    log(f"*** BEAM giant = {mk:.1f}d ({mk/(L-1):.3f} d/leg, {L}/{m} cities) [{time.time()-t0:.0f}s] "
        f"vs bank 913, target ~405 -> {'BEATS BANK' if (mk < 913 and L == m) else 'partial/no-improve'}{tag}")
    if L == m:
        json.dump({'giant_order': order, 'faithful_mk': float(mk), 'W': W, 'pen': pen},
                  open(f'/tmp/ch2_beam_giant_W{W}_p{pen}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    pens = [150.0, 200.0, 250.0, 300.0]              # sweet-spot; dump well-phased partials + faithful mk
    ps = [mp.Process(target=main, args=(W, s, pens[s], 0.0)) for s in range(4)]
    for p in ps: p.start()
    for p in ps: p.join()
