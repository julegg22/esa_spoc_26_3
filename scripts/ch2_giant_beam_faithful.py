"""E-671: Ch2-large GIANT FAITHFUL beam (dense-table PRE-FILTER + Lambert VERIFY) — fixes overfitting.

E-669/670 finding: a beam guided purely by the dense table OVERFITS its residual inaccuracy (240-epoch
/4d grid → tof sampled at the bucket epoch, used at the actual departure). Beam orders looked 0.6 d/leg
on the table but retimed FAITHFULLY to ~1000-1130 (1.7-2.0 d/leg, worse than bank 913). The faithful
greedy, by contrast, gets a REAL 0.30 d/leg (it scans tof at the exact departure) but corner-paints.

This beam = faithful greedy's accuracy + beam diversity to avoid corner-painting. Per beam expansion:
the dense table PRE-FILTERS to the few candidate neighbors cheap at/near the current epoch (fast, no
Lambert), then find_earliest_transfer VERIFIES the real cheap-now arrival (accurate). Score = faithful
arrival + pen*urgency. Keep top-W. The makespan is thus FAITHFUL throughout (no overfitting). Stranded
tail repaired by faithful insertion. Usage: python ch2_giant_beam_faithful.py [W=40]
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
            log(f"  retime {k+1}/{len(order)-1} ep={t:.0f} ({time.time()-t0:.0f}s)")
    return t - entry


def cheap_now(kt, a, b, t):
    """faithful earliest cheap arrival a->b departing AT t (no wait); None if not cheap now."""
    tof = leg(kt, a, b, t)
    return None if tof is None else t + tof


def prefilter(tab, epochs, a, b, t):
    """does the dense table say (a,b) is cheap at the CURRENT bucket (floor/ceil of t)? Tight gate so
    the faithful verify mostly early-exits on genuinely cheap-now pairs (avoids full None-scans)."""
    row = tab.get((a, b))
    if row is None:
        return False
    bi = int(np.searchsorted(epochs, t)); ne = len(epochs)
    return (bi - 1 >= 0 and np.isfinite(row[bi - 1])) or (bi < ne and np.isfinite(row[bi]))


def beam_search(kt, neigh, tab, epochs, start, entry, m, W, pen, log):
    beams = [(entry, [start], {start}, start)]
    t0 = time.time()
    for step in range(m - 1):
        cands = []
        for ep, order, vis, cur in beams:
            succ = []
            for j in neigh[cur]:
                if j in vis or not prefilter(tab, epochs, cur, j, ep):
                    continue
                arr = cheap_now(kt, cur, j, ep)        # FAITHFUL verify
                if arr is not None:
                    succ.append((arr, j))
            succ.sort()
            for arr, j in succ[:8]:
                rem = sum(1 for k in neigh[j] if k not in vis)
                cands.append((arr + pen * (1.0 / (rem + 1)), arr, order, vis, j))
        if not cands:
            best = min(beams, key=lambda b: b[0])
            log(f"  beam DEAD step {step+1}/{m} — best partial len={len(best[1])} ep={best[0]:.0f}")
            return best[1]
        cands.sort(key=lambda x: x[0])
        beams = []; seen = set()
        for score, arr, order, vis, j in cands:
            key = (j, len(order))
            if key in seen and len(beams) > W // 2:
                continue
            seen.add(key); nv = set(vis); nv.add(j)
            beams.append((arr, order + [j], nv, j))
            if len(beams) >= W:
                break
        if (step + 1) % 50 == 0:
            be = min(b[0] for b in beams)
            log(f"  beam {step+1}/{m} live={len(beams)} ep={be:.0f} ({be/(step+1):.3f} d/leg FAITHFUL) "
                f"[{time.time()-t0:.0f}s c{len(_C)}]")
    beams.sort(key=lambda b: b[0])
    return beams[0][1]


def repair(kt, order, missing, neigh, entry, log):
    """faithful insertion of stranded cities: place each at the cheap-neighbor slot minimizing the
    realized arrival at the following city (Lambert-verified)."""
    cur = order[:]
    for u in list(missing):
        # epochs along cur (faithful)
        ep = [entry]; t = entry
        for k in range(len(cur) - 1):
            a = None
            for d in DELAY:
                td = t + float(d); tof = leg(kt, cur[k], cur[k + 1], td)
                if tof is not None:
                    a = td + tof; break
            t = a if a is not None else t + 4.0; ep.append(t)
        nb = neigh[u]; best = None
        for p in range(1, len(cur)):
            if cur[p - 1] not in nb and cur[p] not in nb:
                continue
            au = cheap_now(kt, cur[p - 1], u, ep[p - 1])
            if au is None:
                continue
            ub = cheap_now(kt, u, cur[p], au)
            if ub is None:
                continue
            cost = ub - ep[p]
            if best is None or cost < best[0]:
                best = (cost, p)
        if best is not None:
            cur.insert(best[1], u)
    return cur


def main(seed=0, W=40, pen=2.0, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): [int(j) for j in np.where(adj[c])[0] if int(j) in gset] for c in gnodes}
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz", allow_pickle=True)   # 1d table = TIGHT prefilter
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    log = lambda s: print(f"[s{seed}W{W}p{pen}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    start = [c for c in [int(round(x)) for x in bank[2 * (n - 1):]] if c in gset][0]
    log(f"FAITHFUL beam (W={W} pen={pen} {m} cities; bank 913@1.53, target ~405@0.68)")
    t0 = time.time()
    order = beam_search(kt, neigh, tab, epochs, start, entry, m, W, pen, log)
    miss = [c for c in gnodes if c not in set(order)]
    pmk = faithful_retime(kt, order, entry)
    log(f"partial {len(set(order))}/{m} faithful_mk={pmk if pmk is None else f'{pmk:.0f}'} "
        f"miss={len(miss)} [{time.time()-t0:.0f}s]")
    if miss:
        order = repair(kt, order, miss, neigh, entry, log)
    mk = faithful_retime(kt, order, entry, log); L = len(set(order))
    if mk is None:
        log("STRANDS faithfully"); return
    star = ' ★ RANK-1' if (mk < 450 and L == m) else (f' PARTIAL{L}/{m}' if L != m else '')
    log(f"*** FAITHFUL beam giant = {mk:.1f}d ({mk/(L-1):.3f} d/leg, {L}/{m}) [{time.time()-t0:.0f}s] "
        f"vs 913 -> {'BEATS' if (mk<913 and L==m) else 'no'}{star}")
    if L == m and mk < 913:
        json.dump({'giant_order': order, 'faithful_mk': float(mk)},
                  open(f'/tmp/ch2_fbeam_giant_s{seed}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    nch = int(sys.argv[2]) if len(sys.argv) > 2 else 4    # number of chains (cores)
    allp = [8.0, 30.0, 2.0, 0.5]
    pens = allp[:nch]
    ps = [mp.Process(target=main, args=(s, W, pens[s], 0.0)) for s in range(nch)]
    for p in ps: p.start()
    for p in ps: p.join()
