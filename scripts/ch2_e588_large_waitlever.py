"""E-588 — Ch2 LARGE departure-time (waiting) lever on the BANKED perm.

Orthogonal to node-reorder (E-587 LKH): keep the banked 1051-perm EXACTLY,
but on each leg choose a departure delay δ>=0 that minimises (δ + tof) where
tof is the earliest-feasible cheap transfer at the delayed epoch. The
evaluator's time constraint is times[i]+tofs[i] <= times[i+1], so inserting
idle (waiting) is LEGAL. The banked walk uses zero idle (immediate
departure); E-588 tests whether trading idle for a much shorter transfer on
the 18 locally-improvable expensive legs lowers the makespan.

Greedy forward pass (epoch-consistent: each δ propagates downstream exactly).
For each leg, scan δ on a fine grid; also keep the cheap exc bridges as exc
(use dv_exc on the 5 known bridge legs so the 5-bridge topology is preserved).

GUARDED: writes a strictly-better feasible candidate to /tmp ONLY. Validates
with kt.fitness (feasible, viols=[0,0,0,0]).
"""
import json
import os
import sys

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = os.environ.get("E588_OUT", "/tmp/ch2_large_cand.json")
CURRENT_BANK = 942.0744268445161

TOF_WINDOW = 40.0
N_STEPS = 2400
WAIT_MAX = float(os.environ.get("E588_WAITMAX", "12.0"))
WAIT_STEPS = int(os.environ.get("E588_WAITSTEPS", "49"))  # 0..12 in 0.25d


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    bank_dvs = []
    # which legs are exc bridges in the banked walk? recompute dv at banked
    # times/tofs to classify
    bt = bank[:n - 1]
    bf = bank[n - 1:2 * (n - 1)]
    for i in range(n - 1):
        dv = kt.compute_transfer(perm[i], perm[i + 1], bt[i], bf[i])
        bank_dvs.append(dv)
    bank_dvs = np.array(bank_dvs)
    exc_legs = set(int(k) for k in np.where(bank_dvs > kt.dv_thr + 1e-9)[0])
    print(f"[E-588] n={n} banked exc legs {sorted(exc_legs)} "
          f"(bank {CURRENT_BANK})", flush=True)

    deltas = np.linspace(0.0, WAIT_MAX, WAIT_STEPS)
    times = [0.0]
    tofs = []
    t = 0.0
    n_waited = 0
    total_wait = 0.0
    for i in range(n - 1):
        a, b = perm[i], perm[i + 1]
        # dv threshold for this leg: exc bridges may use exc budget
        thr = kt.dv_exc if i in exc_legs else kt.dv_thr
        best = None  # (arrival = t+delta+tof, delta, tof)
        for d in deltas:
            td = t + d
            if td + 0.05 >= kt.max_time:
                break
            tof, dv = find_earliest_transfer(kt, a, b, td, thr,
                                             TOF_WINDOW, N_STEPS)
            if tof is None:
                continue
            arr = td + tof
            if best is None or arr < best[0] - 1e-9:
                best = (arr, d, tof)
        if best is None:
            print(f"  leg {i} {a}->{b}: NO transfer in wait window — abort",
                  flush=True)
            return
        arr, d, tof = best
        if d > 1e-6:
            n_waited += 1
            total_wait += d
        # times[i] is departure epoch of leg i = t + d (after waiting)
        times[i] = t + d
        tofs.append(tof)
        times.append(arr)   # arrival = next node's earliest departure
        t = arr
    # times has n entries (departures + final arrival); evaluator wants
    # times[:n-1] = departures, tofs[:n-1]. Last "arrival" is times[-1] but
    # evaluator uses times[-1]+tofs[-1]; build x with n-1 departures.
    dep = times[:n - 1]
    x = [float(v) for v in dep] + [float(v) for v in tofs] \
        + [float(p) for p in perm]
    fit = kt.fitness(x)
    mk = float(fit[0])
    feas = bool(kt.is_feasible(fit))
    print(f"[E-588] waited on {n_waited} legs, total idle {total_wait:.1f}d",
          flush=True)
    print(f"[E-588] mk={mk:.4f} feas={feas} viols={list(fit[1:])} "
          f"(bank {CURRENT_BANK})", flush=True)
    if feas and mk < CURRENT_BANK - 1e-4:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        # independent reval
        fit2 = kt.fitness(x)
        print(f"[REVAL] mk={fit2[0]:.4f} feas={kt.is_feasible(fit2)} "
              f"viols={list(fit2[1:])} -> WROTE {OUT}", flush=True)
    else:
        print("[E-588] did NOT beat bank — wrote nothing.", flush=True)


if __name__ == "__main__":
    main()
