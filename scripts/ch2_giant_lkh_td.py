"""E-744 — Ch2-LARGE global TD-Hamiltonian solver (user-requested rank-2 lever). LKH (ATSP) on the faithful
time-AGGREGATED comp0 cost (dense1d min-over-epochs cheap tof) -> a static-optimal 601-city order; then
CHRONO-WALK it faithfully (fast oracle) to get the real TD makespan. The campaign's E-587 'epoch-shift trap'
(static-optimal inflates on chrono-walk) is the thing to measure; the EPOCH-AWARE ITERATION (update cost to
realized per-leg, re-LKH) is the fix the fast faithful evaluator finally enables.
Stage 1 (this run): LKH static -> chrono-walk -> compare to bank comp0 (818d) + greedy beam (338). Iterate.
Usage: python ch2_giant_lkh_td.py [iters=3]"""
import os, sys, json, time, subprocess
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
LKH = f"{ROOT}/reference/GLKH-1.1/LKH-2.0.9/LKH"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MINTOF = kt.min_tof; DAY = 86400.0
BIG = 9_999_000                                                  # no-cheap-edge penalty (LKH avoids)
ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, 3 * DAY, 0.04 * DAY, THR, 5)


def build_cost():
    """601x601 int cost from dense1d: min cheap tof (days*1000) over epochs; BIG where no cheap edge."""
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); K = d["keys"]; V = d["vals"]
    cities = sorted(set(int(c) for ij in K for c in ij)); idx = {c: k for k, c in enumerate(cities)}
    n = len(cities); C = np.full((n, n), BIG, dtype=np.int64)
    for r, (i, j) in enumerate(K):
        row = V[r]; m = np.isfinite(row)
        if m.any():
            C[idx[int(i)], idx[int(j)]] = int(np.nanmin(row[m]) * 1000)
    np.fill_diagonal(C, 0)
    return cities, idx, C


def lkh_atsp(C, tag, runs=3):
    n = C.shape[0]
    pf = f"{ROOT}/cache/lkh_{tag}.atsp"; pr = f"{ROOT}/cache/lkh_{tag}.par"; tf = f"{ROOT}/cache/lkh_{tag}.tour"
    with open(pf, "w") as f:
        f.write(f"NAME: c{tag}\nTYPE: ATSP\nDIMENSION: {n}\nEDGE_WEIGHT_TYPE: EXPLICIT\n"
                "EDGE_WEIGHT_FORMAT: FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        for r in range(n):
            f.write(" ".join(str(int(x)) for x in C[r]) + "\n")
        f.write("EOF\n")
    with open(pr, "w") as f:
        f.write(f"PROBLEM_FILE = {pf}\nTOUR_FILE = {tf}\nRUNS = {runs}\nTRACE_LEVEL = 0\nSEED = 1\n")
    subprocess.run([LKH, pr], capture_output=True, timeout=900)
    tour = []
    with open(tf) as f:
        inn = False
        for line in f:
            line = line.strip()
            if line == "TOUR_SECTION":
                inn = True; continue
            if inn:
                v = int(line)
                if v == -1:
                    break
                tour.append(v - 1)                              # LKH is 1-indexed
    return tour


def chrono_walk(order_cities, t0=0.0, W=4.0, mr=5, tofhi=3.0):
    """faithful greedy earliest-arrival along a fixed order; returns (makespan_d, n_legs_done)."""
    t = t0
    for k in range(len(order_cities) - 1):
        i, j = order_cities[k], order_cities[k + 1]
        deps = np.arange(t, t + W, 0.04)
        tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, tofhi * DAY, 0.04 * DAY, THR, mr)
        m = tof > 0
        if not m.any():
            return t, k
        arr = deps[m] + tof[m] / DAY; t = float(arr[np.argmin(arr)])
    return t, len(order_cities) - 1


def main():
    t0 = time.time()
    cities, idx, C = build_cost()
    n = len(cities)
    print(f"[E-744] comp0 {n} cities; cost matrix built ({(C<BIG).sum()} finite edges) [{time.time()-t0:.0f}s]", flush=True)
    for it in range(ITERS):
        tour_idx = lkh_atsp(C, f"comp0_{it}", runs=5 if it == 0 else 3)
        if not tour_idx:
            print(f"[E-744] iter {it}: LKH failed", flush=True); break
        order = [cities[t] for t in tour_idx]
        # rotate so the order starts where chrono-walk is best? just walk from t=0 as-is (cycle -> path)
        static_cost = sum(C[idx[order[k]], idx[order[k + 1]]] for k in range(len(order) - 1)) / 1000.0
        mk, nl = chrono_walk(order)
        print(f"[E-744] iter {it}: LKH static comp0 {static_cost:.1f}d; CHRONO-WALK {'COMPLETE' if nl==n-1 else 'STRAND@'+str(nl)} "
              f"makespan {mk:.1f}d ({mk/max(nl,1):.3f} d/leg) [bank comp0 818d, greedy beam 338/601] [{time.time()-t0:.0f}s]", flush=True)
        if nl == n - 1:
            json.dump({"order": order, "makespan": mk}, open(f"{ROOT}/cache/ch2_giant_lkh_comp0.json", "w"))
            print(f"[E-744] *** LKH chrono-walk COMPLETE 601 at {mk:.1f}d -> saved (assemble + validate next)", flush=True)
        # EPOCH-AWARE UPDATE: re-walk and set C[leg] to the realized tof for the tour's legs
        t = 0.0; upd = 0
        for k in range(len(order) - 1):
            i, j = order[k], order[k + 1]
            deps = np.arange(t, t + 4.0, 0.04)
            tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, 3.0 * DAY, 0.04 * DAY, THR, 5)
            m = tof > 0
            if not m.any():
                C[idx[i], idx[j]] = BIG; break
            arr = deps[m] + tof[m] / DAY; q = int(np.argmin(arr))
            C[idx[i], idx[j]] = int((arr[q] - t) * 1000); t = float(arr[q]); upd += 1
        print(f"[E-744] iter {it}: updated {upd} edge costs to realized (epoch-aware) [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-744] DONE [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
