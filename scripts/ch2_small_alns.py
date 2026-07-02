"""E-765 — Ch2-small ruin-and-recreate ALNS: a fundamentally different sequencer than or-opt/2-opt LNS
(which is converged at 111.96, E-764). Destroy k cities, greedily re-insert each at the best position
(min makespan via the exact-DP retimer, cheap + <=5 exceptions). SA acceptance. From the 111.96 bank.
Goal: break 111.96 toward rank-1 100.4 by escaping the local-search basin. Official-gated + re-verified.
Usage: python ch2_small_alns.py [iters=40000] [seed=1] [kmax=6]"""
import sys, os, json, time, pickle
import numpy as np
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
import _prov
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
kt = KTTSP(INST); n = kt.n; NEXC = kt.n_exc; INF = float("inf")
_EDGE = pickle.load(open("cache/ch2_small_edgewin_0.05_0.02.pkl", "rb"))   # {(i,j):(cheap_sm, exc_sm)}
_EMPTY = (np.array([0.0]), np.array([INF]), np.array([0.0]), np.array([0.0]))


def ew(i, j):
    v = _EDGE.get((i, j))
    return v if v is not None else (_EMPTY, _EMPTY)


def retime(order):
    """exact labeling DP: min arrival per exception level; returns (makespan, times, tofs, exc)."""
    nl = len(order) - 1; NE = NEXC + 1
    arr = [0.0] + [INF] * NEXC
    bptr = [[None] * NE for _ in range(nl)]
    for k in range(nl):
        (cd, csm, csd, cst), (ed, esm, esd, est) = ew(order[k], order[k + 1])
        new = [INF] * NE
        for e in range(NE):
            t = arr[e]
            if t == INF:
                continue
            q = np.searchsorted(cd, t)
            if q < len(csm):
                a = float(csm[q])
                if a < new[e]:
                    new[e] = a; bptr[k][e] = (float(csd[q]), float(cst[q]), e)
            if e < NEXC:
                q2 = np.searchsorted(ed, t)
                if q2 < len(esm):
                    a2 = float(esm[q2])
                    if a2 < new[e + 1]:
                        new[e + 1] = a2; bptr[k][e + 1] = (float(esd[q2]), float(est[q2]), e)
        arr = new
    be = min((e for e in range(NE) if arr[e] < INF), key=lambda e: arr[e], default=-1)
    if be < 0:
        return INF, None, None, NEXC + 1
    times = [0.0] * nl; tofs = [0.0] * nl; e = be
    for k in range(nl - 1, -1, -1):
        bp = bptr[k][e]
        if bp is None:
            return INF, None, None, NEXC + 1
        times[k] = bp[0]; tofs[k] = bp[1]; e = bp[2]
    return float(arr[be]), times, tofs, be


def mk_of(order):
    m, _, _, _ = retime(order); return m


def repair(partial, removed, rng):
    """greedily insert each removed city at the min-makespan position (best-insertion)."""
    order = list(partial)
    rng.shuffle(removed)
    for c in removed:
        best = None
        for p in range(1, len(order) + 1):        # keep order[0] as fixed start
            cand = order[:p] + [c] + order[p:]
            m = mk_of(cand)
            if m < INF and (best is None or m < best[0]):
                best = (m, cand)
        if best is None:                          # can't place feasibly -> append (will be scored, maybe inf)
            order = order + [c]
        else:
            order = best[1]
    return order


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    kmax = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    _prov.stamp(__file__, iters=iters, seed=seed, kmax=kmax)
    bank = json.load(open("solutions/upload/small.json"))[0]["decisionVector"]
    cur = [int(c) for c in bank[2 * (n - 1):]]
    m0, _, _, _ = retime(cur)
    print(f"[E-765] pos-control bank order retime={m0:.3f}d (bank official 111.96)", flush=True)
    cur_mk = m0; best = m0; best_o = list(cur)
    rng = np.random.default_rng(seed); t0 = time.time()
    T = 0.5                                        # SA temperature (makespan units)
    acc = 0
    for it in range(iters):
        k = int(rng.integers(2, kmax + 1))
        idx = sorted(rng.choice(range(1, n), size=k, replace=False))   # never remove start (pos0)
        rem = [cur[i] for i in idx]
        partial = [cur[i] for i in range(n) if i not in set(idx)]
        cand = repair(partial, rem, rng)
        cmk = mk_of(cand)
        if cmk < INF and (cmk < cur_mk or rng.random() < np.exp(-(cmk - cur_mk) / T)):
            cur, cur_mk = cand, cmk; acc += 1
        if cmk < best - 1e-9:
            best = cmk; best_o = list(cand)
        T = max(0.05, T * 0.9999)
        if it % 1000 == 0:
            print(f"[E-765] it{it} cur {cur_mk:.3f} best {best:.3f} T{T:.3f} acc{acc} [{time.time()-t0:.0f}s]", flush=True)
    # official validate best
    mk, ti, tf, e = retime(best_o)
    dv = list(ti) + list(tf) + [float(o) for o in best_o]
    f = kt.fitness(dv); feas = kt.is_feasible(f)
    json.dump({"order": best_o, "times": ti, "tofs": tf, "makespan": best},
              open("cache/ch2_small_alns_best.json", "w"))
    tg = ("RANK-1(<=100.4)" if f[0] <= 100.4 else "rank-3(<=111.76)" if f[0] <= 111.76 else
          "better-than-bank" if f[0] < 111.96 else "no improvement")
    print(f"[E-765] BEST {best:.3f}d official={f[0]:.3f} feasible={feas} -> {tg} vs bank 111.96 / rank-1 100.4 "
          f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
