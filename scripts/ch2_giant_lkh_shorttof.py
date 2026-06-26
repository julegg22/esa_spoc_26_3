"""E-726f — Ch2-large rank-1: LKH on the faithful short-TOF cost matrix (competitor's inferred method).

Greedy/beam/GRASP cap at ~191-216 (phasing corner-paint). LKH-2.0.9 is a strong TSP solver. Build a 601-city
open-path ATSP whose edge cost = the (faithful-validated) min-TOF per giant cheap edge — i.e. minimise total
flight time on the short-TOF graph — solve with LKH, then FAITHFULLY retime the LKH order (timebeam W=200) to
get the real makespan + strands. The static->time-dependent phasing gap is the risk; LKH finds the globally
short order a greedy front cannot, which is the prerequisite for a phased rank-1 tour.
Usage: python ch2_giant_lkh_shorttof.py [runs=10] [maxtof=2.0]"""
import sys, os, json, time, subprocess
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
LKH = f"{ROOT}/reference/GLKH-1.1/LKH"
TMP = f"{ROOT}/cache/lkh_st"
os.makedirs(TMP, exist_ok=True)
BIG = 9_000_000


def main(runs=10, maxtof=2.0):
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
    cities = sorted(set(int(c) for c in set(KEYS[:, 0]) | set(KEYS[:, 1])))
    idx = {c: k for k, c in enumerate(cities)}; N = len(cities)
    cost = np.full((N + 1, N + 1), BIG, dtype=np.int64)           # N real + 1 dummy (open path)
    ne = 0
    for r, (i, j) in enumerate(KEYS):
        if FIN[r].any():
            mt = float(np.nanmin(VALS[r]))
            if mt <= maxtof:
                cost[idx[int(i)], idx[int(j)]] = int(round(mt * 1000)); ne += 1
    cost[N, :] = 0; cost[:, N] = 0; np.fill_diagonal(cost, 0)     # dummy connects all at 0 -> Hamiltonian PATH
    print(f"[E-726f] {N} giant cities, {ne} short-tof edges (min-tof<= {maxtof}d); building LKH ATSP", flush=True)
    M = N + 1
    pf = f"{TMP}/giant.atsp"
    with open(pf, "w") as f:
        f.write(f"NAME: giant\nTYPE: ATSP\nDIMENSION: {M}\nEDGE_WEIGHT_TYPE: EXPLICIT\n"
                f"EDGE_WEIGHT_FORMAT: FULL_MATRIX\nEDGE_WEIGHT_SECTION\n")
        for a in range(M):
            f.write(" ".join(str(int(x)) for x in cost[a]) + "\n")
        f.write("EOF\n")
    par = f"{TMP}/giant.par"; tour = f"{TMP}/giant.tour"
    with open(par, "w") as f:
        f.write(f"PROBLEM_FILE = {pf}\nOUTPUT_TOUR_FILE = {tour}\nRUNS = {runs}\nTIME_LIMIT = 1200\n"
                f"TRACE_LEVEL = 1\n")
    t0 = time.time()
    print(f"[E-726f] running LKH (RUNS={runs}, 1200s limit)...", flush=True)
    r = subprocess.run([LKH, par], capture_output=True, text=True, timeout=2000)
    print(r.stdout[-600:], flush=True)
    if not os.path.exists(tour):
        print("[E-726f] LKH produced no tour", flush=True); return
    perm = []
    with open(tour) as f:
        started = False
        for line in f:
            s = line.strip()
            if s == "TOUR_SECTION":
                started = True; continue
            if started:
                v = int(s)
                if v == -1:
                    break
                perm.append(v - 1)                                # LKH is 1-indexed
    dummy = N
    k = perm.index(dummy)
    order_idx = perm[k + 1:] + perm[:k]                           # rotate so path starts after dummy
    order = [cities[q] for q in order_idx if q != dummy]
    print(f"[E-726f] LKH tour: {len(order)} cities [{time.time()-t0:.0f}s]; faithful retime...", flush=True)
    json.dump({"order": order}, open(f"{ROOT}/cache/ch2_giant_lkh_order.json", "w"))
    import ch2_giant_timebeam as tb
    mk, st, depth = tb.timebeam([int(c) for c in order], 4, 200, 60, verbose=False, tolerate=True)
    threaded = len(order) - st
    print(f"[E-726f] LKH order faithful retime: makespan {mk:.1f}d strands {st} (threaded {threaded}/{len(order)}) "
          f"d/leg {mk/max(len(order)-1,1):.3f} [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order, "makespan": mk, "strands": st},
              open(f"{ROOT}/cache/ch2_giant_lkh_retimed.json", "w"))
    if threaded >= 599 and mk < 425:
        print(f"[E-726f] *** {threaded}/601 @ {mk:.0f}d < 425 -> RANK-1 candidate; OFFICIAL verify + stitch + escalate",
              flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 10, float(a[2]) if len(a) > 2 else 2.0)
