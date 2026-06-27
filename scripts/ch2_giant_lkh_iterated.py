"""E-726g — Ch2-large rank-1: EPOCH-AWARE iterated LKH on faithful short-tof windows.

Static LKH order strands 206 faithfully (the cost ignores WHEN windows open). Fixed-point: solve LKH -> greedy
faithful retime (per-city reached epoch) -> re-cost each edge (i,j) by its faithful TOF at city i's reached
epoch (window table lookup; INF if no window near that epoch) -> re-LKH. Iterate; keep the order with the best
faithful retime (fewest strands, then makespan). This is E-562's epoch-aware reorder but on the FAITHFUL
short-tof window table. Risk: may floor (E-562 floored 932 on the table); on faithful short-tof it may go lower.
Usage: python ch2_giant_lkh_iterated.py [iters=5] [runs=5]"""
import sys, os, json, time, subprocess
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_timebeam as tb
ROOT = "/home/julian/Projects/esa_spoc_26_3"
LKH = f"{ROOT}/reference/GLKH-1.1/LKH"; TMP = f"{ROOT}/cache/lkh_it"; os.makedirs(TMP, exist_ok=True)
BIG = 9_000_000
W = np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item()
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(int(c) for c in set(KEYS[:, 0]) | set(KEYS[:, 1])))
idx = {c: k for k, c in enumerate(cities)}; N = len(cities)
EDGES = [(int(i), int(j), float(np.nanmin(VALS[r]))) for r, (i, j) in enumerate(KEYS) if FIN[r].any()]


def tof_at(i, j, epoch):
    """faithful tof for i->j at the window nearest/after `epoch` (from precomputed table); None if none/far."""
    w = W.get((i, j))
    if w is None or len(w[0]) == 0:
        return None
    deps, tofs = w
    q = np.searchsorted(deps, epoch)
    if q < len(deps) and deps[q] <= epoch + 20:
        return float(tofs[q])
    return None


def solve_lkh(cost, runs, tag):
    M = N + 1
    pf = f"{TMP}/g{tag}.atsp"; par = f"{TMP}/g{tag}.par"; tour = f"{TMP}/g{tag}.tour"
    with open(pf, "w") as f:
        f.write(f"NAME: g\nTYPE: ATSP\nDIMENSION: {M}\nEDGE_WEIGHT_TYPE: EXPLICIT\n"
                f"EDGE_WEIGHT_FORMAT: FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        for a in range(M):
            f.write(" ".join(str(int(x)) for x in cost[a]) + "\n")
        f.write("EOF\n")
    with open(par, "w") as f:
        f.write(f"PROBLEM_FILE = {pf}\nOUTPUT_TOUR_FILE = {tour}\nRUNS = {runs}\nTIME_LIMIT = 400\nTRACE_LEVEL = 0\n")
    subprocess.run([LKH, par], capture_output=True, text=True, timeout=800)
    if not os.path.exists(tour):
        return None
    perm = []
    with open(tour) as f:
        on = False
        for line in f:
            s = line.strip()
            if s == "TOUR_SECTION":
                on = True; continue
            if on:
                v = int(s)
                if v == -1:
                    break
                perm.append(v - 1)
    k = perm.index(N)
    oi = perm[k + 1:] + perm[:k]
    return [cities[q] for q in oi if q != N]


def greedy_epochs(order):
    """faithful greedy W=1 retime -> reached epoch per city (and strands)."""
    t = 0.0; ep = {order[0]: 0.0}; strand = 0
    for k in range(len(order) - 1):
        w = tb.windows(order[k], order[k + 1], t, 1, 60)
        if w:
            t = w[0][1]
        else:
            t += 50; strand += 1
        ep[order[k + 1]] = t
    return ep, strand


def build_cost(epoch_of):
    cost = np.full((N + 1, N + 1), BIG, dtype=np.int64)
    for (i, j, mt) in EDGES:
        e = epoch_of.get(i)
        if e is None:
            c = int(round(mt * 1000))                            # not yet placed -> static min-tof
        else:
            tf = tof_at(i, j, e)
            # window at reached epoch -> its faithful tof; else SOFT penalty (static + 3d), NOT BIG
            # (BIG forbade edges based on a bad-retime epoch -> divergence; soft keeps the edge usable)
            c = int(round(tf * 1000)) if tf is not None else int(round(mt * 1000)) + 3000
        cost[idx[i], idx[j]] = c
    cost[N, :] = 0; cost[:, N] = 0; np.fill_diagonal(cost, 0)
    return cost


def main(iters=5, runs=5):
    t0 = time.time()
    epoch_of = {}                                                # iter 0: static cost
    best = None
    for it in range(iters):
        cost = build_cost(epoch_of)
        order = solve_lkh(cost, runs, it % 2)
        if order is None:
            print(f"[E-726g] it{it}: LKH no tour", flush=True); break
        mk, st, _ = tb.timebeam([int(c) for c in order], 4, 200, 60, verbose=False, tolerate=True)
        thr = len(order) - st
        print(f"[E-726g] it{it}: threaded {thr}/{len(order)} makespan {mk:.1f}d strands {st} "
              f"d/leg {mk/max(len(order)-1,1):.3f} [{time.time()-t0:.0f}s]", flush=True)
        if best is None or (st, mk) < (best[1], best[2]):
            best = (order, st, mk)
            json.dump({"order": order, "makespan": mk, "strands": st},
                      open(f"{ROOT}/cache/ch2_giant_lkh_iter_best.json", "w"))
            if st == 0 and mk < 425:
                print(f"[E-726g] *** {thr}/601 @ {mk:.0f}d <425 0-strand -> RANK-1 candidate; verify+escalate",
                      flush=True)
        epoch_of, _ = greedy_epochs(order)                       # re-cost from this order's reached epochs
    print(f"[E-726g] DONE best strands {best[1]} makespan {best[2]:.1f}d [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 5, int(a[2]) if len(a) > 2 else 5)
