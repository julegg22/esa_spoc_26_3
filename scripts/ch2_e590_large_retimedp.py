"""E-590 — Ch2 LARGE: bounded forward retime-DP on the BANKED perm.

Adapts the E-040 (e568) ultrafine-retime forward Bellman DP to large.
Keeps the banked 1051-perm and 5-exc-bridge assignment EXACTLY; optimizes
ONLY departure times.

Method (scalar-frontier bounded retime-DP — the non-greedy generalization
of the E-588 greedy waiting pass):

  State after leg k = earliest arrival epoch at node perm[k] reachable under
  the fixed permutation + exc-assignment. The per-leg min-arrival is monotone
  non-decreasing in the input epoch (an earlier input epoch's reachable
  departure set is a superset), so the earliest-arrival scalar frontier is
  globally optimal: at every node hold the earliest reachable arrival, and at
  each leg pick the departure delta in [0, WAIT_MAX] that MINIMIZES
  arrival = dep + earliest-feasible-tof(dep). This is the Bellman choice the
  greedy first-feasible pass (0.25d quantum) could not make.

  Dominates greedy via (a) finer time resolution than greedy's 0.25d quantum
  and (b) full delta-window min-arrival scan vs first-feasible.

Two-stage delta scan per leg: coarse grid (DRES_COARSE) then refine
(DRES_FINE) around the coarse argmin. Empirically min-arrival sits at delta=0
at the banked epochs, but the DP departs from EARLIER epochs (upstream idle
removed), where forced waits may move; the scan finds them.

GUARDED: writes a strictly-better feasible candidate to a DISTINCT /tmp path
ONLY. Validates with walk_perm_chrono AND kt.fitness.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import (  # noqa: E402
    find_earliest_transfer)
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = "/tmp/ch2_large_retimedp_cand.json"
CURRENT_BANK = 934.4451854939546

TOF_WINDOW = 40.0
N_STEPS = 2400                 # fine tof grid: 40d/2400 = 0.0167d
WAIT_MAX = float(os.environ.get("E590_WAITMAX", "12.0"))
DRES_COARSE = float(os.environ.get("E590_DCOARSE", "0.1"))
DRES_FINE = float(os.environ.get("E590_DFINE", "0.01"))

EXC_LEGS = {149, 416, 566, 807, 957}


def leg_min_arrival(kt, i, j, a, is_exc):
    """Return (dep, tof, arrival) minimizing arrival over delta in
    [0, WAIT_MAX], two-stage (coarse then refine). None if infeasible."""
    thr = kt.dv_exc if is_exc else kt.dv_thr

    def scan(grid):
        best = None
        for d in grid:
            dep = a + float(d)
            if dep + 0.05 >= kt.max_time:
                break
            tof, dv = find_earliest_transfer(kt, i, j, dep, thr,
                                             TOF_WINDOW, N_STEPS)
            if tof is None:
                continue
            arr = dep + tof
            if best is None or arr < best[2] - 1e-9:
                best = (dep, tof, arr, float(d))
        return best

    coarse = np.arange(0.0, WAIT_MAX + 1e-9, DRES_COARSE)
    bc = scan(coarse)
    if bc is None:
        return None
    d0 = bc[3]
    lo = max(0.0, d0 - DRES_COARSE)
    hi = min(WAIT_MAX, d0 + DRES_COARSE)
    fine = np.arange(lo, hi + 1e-9, DRES_FINE)
    bf = scan(fine)
    best = bf if (bf is not None and bf[2] < bc[2] - 1e-12) else bc
    return best[0], best[1], best[2]


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    bank_mk = float(kt.fitness(bank)[0])
    print(f"[BASE] bank mk={bank_mk:.4f} WAIT_MAX={WAIT_MAX} "
          f"DCOARSE={DRES_COARSE} DFINE={DRES_FINE} N_STEPS={N_STEPS}",
          flush=True)

    # warm up underlying solver (first call pays JIT/import cost)
    find_earliest_transfer(kt, perm[0], perm[1], 0.0, kt.dv_thr,
                           TOF_WINDOW, N_STEPS)

    n_legs = n - 1
    t = 0.0
    times = [0.0] * n_legs
    tofs = [0.0] * n_legs
    n_waited = 0
    total_wait = 0.0
    t0 = time.time()
    for k in range(n_legs):
        i, j = perm[k], perm[k + 1]
        res = leg_min_arrival(kt, i, j, t, k in EXC_LEGS)
        if res is None:
            print(f"  leg {k} {i}->{j}: NO transfer — abort", flush=True)
            return
        dep, tof, arr = res
        d = dep - t
        if d > 1e-6:
            n_waited += 1
            total_wait += d
        times[k] = dep
        tofs[k] = tof
        t = arr
        if k % 100 == 0:
            print(f"  [DP] leg {k}/{n_legs} t={t:.2f} waited={n_waited} "
                  f"idle={total_wait:.2f} ({time.time()-t0:.0f}s)",
                  flush=True)

    print(f"[DP] done in {time.time()-t0:.0f}s | waited {n_waited} legs, "
          f"total idle {total_wait:.2f}d", flush=True)

    x = [float(v) for v in times] + [float(v) for v in tofs] \
        + [float(p) for p in perm]

    wt, wf, wd, wok, wexc, wleg = walk_perm_chrono(kt, perm)
    fit = kt.fitness(x)
    mk = float(fit[0])
    feas = bool(kt.is_feasible(fit))
    print(f"[VERDICT] retime-DP mk={mk:.4f} feas={feas} "
          f"viols={list(fit[1:])} | bank={bank_mk:.4f} "
          f"delta={mk-bank_mk:+.4f}", flush=True)
    print(f"[CHRONO] walk ok={wok} last_leg={wleg} exc={wexc}", flush=True)

    if feas and mk < CURRENT_BANK - 1e-4:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        fit2 = kt.fitness(x)
        print(f"[OUT] BEATS BANK — wrote {OUT} | reval mk={fit2[0]:.4f} "
              f"feas={kt.is_feasible(fit2)} viols={list(fit2[1:])}",
              flush=True)
    else:
        print("[OUT] did NOT beat bank — wrote nothing.", flush=True)


if __name__ == "__main__":
    main()
