"""E-664: Ch2-large GIANT time-aware search (pivot after cluster+LKH static failed, E-663b).

Re-audit finding: bank-giant flies 1.53 d/leg vs min-tof 0.15 — BADLY phased; static-LKH is worse
(1519). r1 (TGMA) flies 0.4 d/leg = well phased. The giant is ONE cheap-component (no exc, won't
strand), so a TIME-AWARE greedy (shortest cheap tof AT the current epoch) should phase far better.
This script: (1) build a time-aware greedy-NN giant order (decisive — does it beat bank-giant 913?),
(2) SA local search (2-opt/or-opt) from the best seed, faithful retime w/ waiting, heartbeats.
4 mp chains. Usage: python ch2_giant_sa.py [seed=0] [wall_s] [entry=0]
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
TOF_WINDOW = 40.0; N_STEPS = 2400; HB = 100
DELAY = np.array([0.0, 0.5, 1.0, 1.5])           # minimal waiting → ~10-15s/giant-retime (vs ~88s)
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def best_hop(kt, a, b, t):
    """min-arrival tof for a->b departing >= t (over DELAY); returns arrival or None."""
    best = None
    for d in DELAY:
        td = t + float(d)
        if td + 0.05 >= kt.max_time:
            break
        tof = leg(kt, a, b, td)
        if tof is not None and (best is None or td + tof < best):
            best = td + tof
    return best


def retime(kt, order, entry, tag=""):
    t = entry; tofs = []; t0 = time.time()
    for k in range(len(order) - 1):
        arr = best_hop(kt, order[k], order[k + 1], t)
        if arr is None:
            return None, None
        tofs.append(arr - t); t = arr
        if tag and (k + 1) % HB == 0:
            print(f"  [{tag}] leg {k+1}/{len(order)-1} ep={t:.0f} ({time.time()-t0:.0f}s c{len(_C)})", flush=True)
    return t - entry, tofs


def greedy_nn(kt, neigh, start, entry, n, tab, epochs, log):
    """Time-aware greedy using the FAST epoch table to RANK candidates (min-tof at the current
    epoch bucket), then commit with the table tof. Heartbeat every 50 steps. Fast seed for SA."""
    ne = len(epochs); vis = set([start]); order = [start]; cur = start; t = entry; t0 = time.time()
    for step in range(n - 1):
        cands = [j for j in neigh[cur] if j not in vis and (cur, j) in tab]
        if not cands:
            cands = [j for j in range(n) if j not in vis and (cur, j) in tab]
        # WAITING: scan epoch buckets forward from now; take the EARLIEST-ARRIVAL cheap hop
        bestj = None; besta = None; bi0 = int(np.searchsorted(epochs, t))
        for bi in range(min(bi0, ne - 1), ne):
            dep = max(t, float(epochs[bi]))
            for j in cands:
                tof = tab[(cur, j)][bi]
                if np.isfinite(tof) and (besta is None or dep + tof < besta):
                    besta = dep + tof; bestj = j
            if bestj is not None and float(epochs[bi]) > besta:
                break                            # later buckets can't improve arrival
        if bestj is None or besta >= kt.max_time - 0.05:
            return None                          # strand / would exceed horizon
        order.append(bestj); vis.add(bestj); t = besta; cur = bestj
        if (step + 1) % 50 == 0:
            log(f"  greedy step {step+1}/{n-1} ep={t:.0f} ({time.time()-t0:.0f}s)")
    return order if len(set(order)) == n else None


def main(seed=0, wall_s=20 * 3600, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = list(np.where(lab == gi)[0]); gset = set(gnodes); m = len(gnodes)
    neigh = {int(c): [int(j) for j in np.where(adj[c])[0] if int(j) in gset] for c in gnodes}
    log = lambda s: print(f"[s{seed}] {s}", flush=True)
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]
    bank_g = [c for c in bperm if c in gset]
    rng = random.Random(seed * 17 + 3)
    # seed 0 reports the bank-giant baseline + a greedy-NN from the bank start
    if seed == 0:
        bmk, _ = retime(kt, bank_g, entry, "bank")
        log(f"bank-giant baseline = {bmk:.1f}d ({m} legs, 1.53d/leg; min-tof~0.15)")
    # time-aware greedy-NN seed (start varies by chain)
    start = bank_g[0] if seed == 0 else gnodes[rng.randrange(m)]
    t0 = time.time()
    g_order = greedy_nn(kt, neigh, start, entry, m, tab, epochs, log)
    gmk = 1e9
    if g_order is not None:
        r, _ = retime(kt, g_order, entry)
        if r is not None:
            gmk = r; log(f"greedy-NN giant (start {start}) = {gmk:.1f}d [{time.time()-t0:.0f}s]")
        else:
            g_order = None; log("greedy-NN order STRANDS in faithful retime (wait>6d) — discarding")
    else:
        log("greedy-NN failed to complete")
    # pick best seed (greedy-NN vs bank-giant)
    bmk2, _ = retime(kt, bank_g, entry)
    if g_order is not None and gmk < bmk2:
        cur, cur_mk = g_order, gmk
    else:
        cur, cur_mk = bank_g[:], bmk2
    best, best_mk = cur[:], cur_mk
    log(f"SA start from {'greedy-NN' if cur is g_order else 'bank-giant'} mk={cur_mk:.1f}")
    T = 8.0; it = 0; t1 = time.time()
    while time.time() - t1 < wall_s:
        it += 1
        cand = cur[:]
        a, b = sorted(rng.sample(range(m), 2))
        if rng.random() < 0.6:
            cand[a:b + 1] = cand[a:b + 1][::-1]           # 2-opt
        else:
            L = rng.randint(1, 6); seg = cand[a:a + L]; del cand[a:a + L]
            j = rng.randint(0, len(cand)); cand[j:j] = seg  # or-opt
        mk, _ = retime(kt, cand, entry)
        if mk is None:
            continue
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / max(T, 1e-3)):
            cur, cur_mk = cand, mk
        if mk < best_mk - 1e-3:
            best, best_mk = cand[:], mk
            log(f"NEW BEST giant={best_mk:.1f}d ({best_mk-cur_mk:+.1f}) it={it} [{time.time()-t1:.0f}s]")
            json.dump({'giant_order': best, 'mk': best_mk}, open(f'/tmp/ch2_giant_best_s{seed}.json', 'w'))
        T *= 0.99995
        if it % 5 == 0:
            log(f"it={it} cur={cur_mk:.1f} best={best_mk:.1f} T={T:.2f} [{time.time()-t1:.0f}s]")
    log(f"done it={it} best_giant={best_mk:.1f}")


if __name__ == "__main__":
    import multiprocessing as mp
    wall = float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600
    procs = [mp.Process(target=main, args=(s, wall, 0.0)) for s in range(4)]
    for p in procs: p.start()
    for p in procs: p.join()
