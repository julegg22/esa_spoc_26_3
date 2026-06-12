"""E-045 PART B — Ch2 LARGE: re-walk bank order on a FINE tof grid,
respecting the bank's exact exception placement.

E-582 found the bank's 0.1d tof grid leaves ~0.12 d/leg vs a 0.01d grid
(156/300 legs improve). The generic walk_perm_chrono re-walk fails
because it greedily spends the 5-exc budget on different legs than the
bank, then strands. Here we (1) recover the bank's exc legs from its
stored decision vector (legs with realised dv>dv_thr), then (2) re-walk
the bank perm chronologically with a fine grid, allowing the exc dv
threshold ONLY on those exact legs and requiring cheap elsewhere.

Guard: candidate -> /tmp ONLY if feasible AND strictly < 1041.3340.
"""
import json
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = "/tmp/ch2_large_finegrid_cand.json"
INCUMBENT = 1041.3340
WAIT_STEPS = 8
WAIT_DT = 0.25


def bank_exc_legs(kt, perm, times, tofs):
    """Return set of leg indices k (transfer perm[k]->perm[k+1]) whose
    bank-stored transfer needs dv>dv_thr (i.e. is an exception leg)."""
    exc = set()
    for k in range(len(perm) - 1):
        i, j = perm[k], perm[k + 1]
        dv = kt.compute_transfer(i, j, times[k], tofs[k])
        if dv > kt.dv_thr + 1e-9:
            exc.add(k)
    return exc


def rewalk(kt, perm, exc_legs, nsteps, win=12.0):
    t = 0.0
    cur = perm[0]
    times, tofs, dvs = [], [], []
    for k in range(len(perm) - 1):
        j = perm[k + 1]
        allow_exc = k in exc_legs
        thr = kt.dv_exc if allow_exc else kt.dv_thr
        tof, dv = find_earliest_transfer(kt, cur, j, t, thr, win, nsteps)
        if tof is None:
            for w in range(1, WAIT_STEPS + 1):
                t_try = t + w * WAIT_DT
                if t_try >= kt.max_time - kt.min_tof:
                    break
                tof, dv = find_earliest_transfer(kt, cur, j, t_try, thr,
                                                 win, nsteps)
                if tof is not None:
                    t = t_try
                    break
        if tof is None:
            return None, k
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        t = t + tof
        cur = j
        if t > kt.max_time:
            return None, k
    return (times, tofs, dvs), len(perm) - 1


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    times_b = [float(v) for v in bank[:n - 1]]
    tofs_b = [float(v) for v in bank[n - 1:2 * (n - 1)]]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    print(f"[E-583] incumbent={INCUMBENT} n={n}", flush=True)

    t0 = time.time()
    exc_legs = bank_exc_legs(kt, perm0, times_b, tofs_b)
    print(f"[E-583] bank exc legs (k): {sorted(exc_legs)} "
          f"({len(exc_legs)} of budget {kt.n_exc}) [{time.time()-t0:.0f}s]",
          flush=True)

    best = None
    for nsteps in [120, 300, 600, 1200]:
        t0 = time.time()
        res, last = rewalk(kt, perm0, exc_legs, nsteps)
        dt = time.time() - t0
        if res is None:
            print(f"  nsteps={nsteps}: REJECTED at leg {last} ({dt:.0f}s)",
                  flush=True)
            continue
        times, tofs, dvs = res
        mk = times[-1] + tofs[-1]
        x = list(map(float, times)) + list(map(float, tofs)) + \
            [float(v) for v in perm0]
        fit = kt.fitness(x)
        feas = kt.is_feasible(fit)
        n_exc = sum(1 for d in dvs if d > kt.dv_thr)
        print(f"  nsteps={nsteps}: walk_mk={mk:.4f} official={fit[0]:.4f} "
              f"feas={feas} viol={fit[1:]} exc={n_exc} ({dt:.0f}s)",
              flush=True)
        if feas and (best is None or fit[0] < best[0]):
            best = (fit[0], x, nsteps)

    if best and best[0] < INCUMBENT - 1e-6:
        json.dump([{"decisionVector": best[1], "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        print(f"\n[E-583] CANDIDATE WRITTEN {OUT} mk={best[0]:.4f} "
              f"(nsteps={best[2]}, -{INCUMBENT-best[0]:.4f}d vs bank)",
              flush=True)
    else:
        b = best[0] if best else float('nan')
        print(f"\n[E-583] no improvement (best feasible={b:.4f} vs "
              f"{INCUMBENT}) — nothing written", flush=True)


if __name__ == "__main__":
    main()
