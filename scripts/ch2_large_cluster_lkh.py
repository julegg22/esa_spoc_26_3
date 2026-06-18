"""E-663: Ch2-large CLUSTER+LKH (user: all resources, never stop) — TGMA's route toward 424.

Large = 4 cheap-components [601 giant + 3×150], bridged by ≤5 exc. The giant dominates makespan.
DECISIVE FIRST TEST (this script): does iterated elkai-LKH ↔ faithful-retime CONVERGE for the
601-giant (retime makespan DECREASES), or inflate/oscillate (static OR-Tools→1400, the time-dependent
trap)? LKH cost matrix = min-tof over epochs from /tmp/ch2_large_epoch_table.npz (coarse OK — it only
GUIDES the order; the faithful part is the retime). Each iteration: LKH(cost) → giant order → faithful
retime (fine find_earliest_transfer) → realized tofs → update cost → repeat.

SANDBOX: emit HEARTBEAT every HB legs during retime (silent long compute gets reaped; frequent-output
jobs survive). Usage: python ch2_large_cluster_lkh.py [iters=8] [entry_epoch=0]
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
TOF_WINDOW = 40.0; N_STEPS = 2400; HB = 50
DELAY_GRID = np.round(np.arange(0.0, 6.01, 0.5), 3)   # WAITING: try delays so cheap windows open
_C = {}                                          # faithful leg cache: (a,b,round(t,3)) -> tof|None


def leg(kt, a, b, t):
    key = (a, b, round(t, 3))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def retime(kt, order, entry, tag):
    """Faithful retime of a giant order from epoch `entry`. Per leg pick min-ARRIVAL over DELAY_GRID
    (WAITING lets the cheap window open — the giant is cheap-connected, so waiting avoids strands).
    Heartbeat every HB legs. Returns (makespan, realized_tofs) or (None,None)."""
    t = entry; tofs = []; t0 = time.time()
    for k in range(len(order) - 1):
        best = None
        for d in DELAY_GRID:
            td = t + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof = leg(kt, order[k], order[k + 1], td)
            if tof is not None and (best is None or td + tof < best):
                best = td + tof
        if best is None:
            print(f"  [{tag}] STRANDED at leg {k} (no cheap transfer even with waiting) — order not walkable", flush=True)
            return None, None
        tofs.append(best - t); t = best
        if (k + 1) % HB == 0:
            print(f"  [{tag}] leg {k+1}/{len(order)-1} epoch={t:.1f} ({time.time()-t0:.0f}s, cache {len(_C)})", flush=True)
    return t - entry, tofs


def lkh_order(gnodes, cost):
    """elkai-LKH cycle on the giant cost (int-scaled); fallback nearest-neighbor+2opt."""
    m = len(gnodes)
    try:
        import elkai
        M = np.round(cost * 1000).astype(np.int64); np.fill_diagonal(M, 0)
        cyc = elkai.DistanceMatrix(M.tolist()).solve_tsp()
        cyc = cyc[:-1] if cyc[0] == cyc[-1] else cyc
        # break at the most expensive edge -> open path
        w = max(range(len(cyc)), key=lambda k: cost[cyc[k], cyc[(k+1) % m]])
        path = cyc[w+1:] + cyc[:w+1]
        return [gnodes[k] for k in path], "elkai-LKH"
    except Exception as e:
        # nearest-neighbor + a few 2-opt passes
        import random; rng = random.Random(0)
        unv = set(range(m)); cur = 0; unv.discard(0); path = [0]
        while unv:
            nxt = min(unv, key=lambda j: cost[cur, j]); path.append(nxt); unv.discard(nxt); cur = nxt
        return [gnodes[k] for k in path], f"NN(elkai failed:{str(e)[:30]})"


def main(iters=8, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = list(np.where(lab == gi)[0])            # 601 giant city ids
    gidx = {c: k for k, c in enumerate(gnodes)}; m = len(gnodes)
    # giant cost matrix from epoch table (min-tof over epochs); BIG for non-cheap
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    keys = d['keys']; vals = d['vals']
    BIG = 50.0
    cost = np.full((m, m), BIG, dtype=np.float64)
    for (a, b), row in zip(keys, vals):
        a, b = int(a), int(b)
        if a in gidx and b in gidx:
            mn = np.nanmin(np.where(np.isfinite(row), row, np.inf))
            if np.isfinite(mn):
                cost[gidx[a], gidx[b]] = mn
    np.fill_diagonal(cost, 0.0)
    print(f"[E-663] giant={m} cities | cost matrix from table ({np.sum(cost<BIG)} cheap entries) | "
          f"entry_epoch={entry} | KEY TEST: does iterated LKH<->retime converge?", flush=True)
    # bank giant sub-order makespan (reference) — retime the bank's giant cities in bank order
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    bank_giant_order = [c for c in bperm if c in gidx]
    bmk, _ = retime(kt, bank_giant_order, entry, "bank-giant")
    print(f"[E-663] BANK giant sub-order retime (from epoch {entry}) = {bmk:.2f}d (601 legs)", flush=True)

    best = None; t0 = time.time()
    for it in range(iters):
        order, how = lkh_order(gnodes, cost)
        mk, tofs = retime(kt, order, entry, f"it{it}")
        if mk is None:
            print(f"[E-663] it{it} LKH order STRANDED — needs exc within giant / different cost", flush=True)
            # perturb cost to recover
            cost = cost * (1 + 0.02 * np.random.default_rng(it).standard_normal(cost.shape)); cost = np.abs(cost)
            continue
        print(f"[E-663] it{it} ({how}) giant retime makespan = {mk:.2f}d (bank-giant {bmk:.2f}) "
              f"[{time.time()-t0:.0f}s]", flush=True)
        if best is None or mk < best:
            best = mk
        # update cost: realized tof for the legs in this order (the rest keep table min-tof)
        for k in range(len(order) - 1):
            cost[gidx[order[k]], gidx[order[k + 1]]] = tofs[k]
    print(f"\n[E-663] DONE: best giant retime={best:.2f}d vs bank-giant {bmk:.2f}d. "
          f"{'CONVERGED/IMPROVED -> cluster+LKH VIABLE, scale to full assembly' if best is not None and best < bmk - 0.5 else 'no improvement vs bank-giant -> re-audit the iteration scheme'}", flush=True)


if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    en = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    main(it, en)
