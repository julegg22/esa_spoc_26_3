"""E-589 — Ch2 LARGE non-greedy departure-time DP on the FIXED banked order.

Extends E-588 (greedy wait pass, banked 934.4452 d). The greedy pass departs
as early as possible at every leg. This script tests whether a NON-greedy
timing policy (wait earlier to unlock a shorter downstream transfer) beats it.

Method:
1. Build, per leg, the map dep_delay -> earliest-feasible tof at the delayed
   epoch (relative to that leg's *incoming* arrival epoch). Parallelized over
   legs (both cores). This profiles arr_off(dep) = (dep_delay + tof) - tof0.
2. STRUCTURAL TEST: count legs whose arr(dep) is NON-monotone (a launch-window
   valley). If arr(dep) is monotone non-decreasing for every leg, the global
   arrival-minimizing solution IS the greedy walk and no DP can beat it.
3. If any valleys exist, run a forward DP over arrival-epoch states along the
   fixed order to minimise final makespan, then re-validate by the TRUE chrono
   walk (find_earliest_transfer) + kt.fitness and write to /tmp if it beats.

GUARDED: writes only to /tmp/ch2_large_cand.json, only if strictly better &
feasible. No git, no solutions/upload/.
"""
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = "/tmp/ch2_large_cand.json"
CURRENT_BANK = 934.4451854939546

TOF_WINDOW = 40.0
N_STEPS = 2400
EXC_LEGS = {149, 416, 566, 807, 957}

# Per-leg departure-delay grid (relative to the leg's incoming arrival epoch).
DELAY_GRID = np.round(np.arange(0.0, 16.01, 0.5), 3)

_kt = None


def _init():
    global _kt
    _kt = KTTSP(INST)


def _profile_leg(args):
    """For leg i (a->b) with incoming arrival epoch t0 and banked tof0,
    return list of (delay, tof, arr_off) over DELAY_GRID. arr_off = arrival
    relative to banked-arrival (t0 + tof0)."""
    i, a, b, t0, tof0 = args
    thr = _kt.dv_exc if i in EXC_LEGS else _kt.dv_thr
    out = []
    for d in DELAY_GRID:
        tof, dv = find_earliest_transfer(_kt, a, b, t0 + float(d), thr,
                                         TOF_WINDOW, N_STEPS)
        if tof is None:
            out.append((float(d), None, None))
            continue
        arr_off = (float(d) + tof) - tof0
        out.append((float(d), tof, arr_off))
    return i, out


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    bt = np.array(bank[:n - 1])
    bf = np.array(bank[n - 1:2 * (n - 1)])
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    fit = kt.fitness(bank)
    print(f"[E-589] bank mk={float(fit[0]):.4f} feas={bool(kt.is_feasible(fit))}"
          f" viols={list(fit[1:])}", flush=True)

    # Profile every leg at its BANKED incoming arrival epoch bt[i].
    tasks = [(i, perm[i], perm[i + 1], float(bt[i]), float(bf[i]))
             for i in range(n - 1)]
    profiles = {}
    workers = int(os.environ.get("E589_WORKERS", "2"))
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
        for i, out in ex.map(_profile_leg, tasks, chunksize=8):
            profiles[i] = out
    print("[E-589] profiling done", flush=True)

    # STRUCTURAL TEST: legs whose arr(dep) dips below banked arrival (arr_off<0).
    valley_legs = []
    for i in range(n - 1):
        prof = profiles[i]
        best = min((p[2] for p in prof if p[2] is not None), default=0.0)
        if best < -1e-4:
            bd = min((p for p in prof if p[2] is not None),
                     key=lambda p: p[2])
            valley_legs.append((i, bd[0], bd[2]))
    print(f"[E-589] legs with arr_off<0 (waiting => EARLIER arrival): "
          f"{len(valley_legs)}", flush=True)
    for v in sorted(valley_legs, key=lambda x: x[1])[:30]:
        print(f"    leg{v[0]} wait={v[1]:.2f} arr_off={v[2]:+.3f}", flush=True)

    # Also measure NON-monotonicity that helps DOWNSTREAM even if local arr_off>0
    # (a later departure could still net-help if the downstream curve drops more
    # steeply). Build the forward DP regardless.
    run_dp(kt, n, perm, bt, bf, profiles)


def run_dp(kt, n, perm, bt, bf, profiles):
    """Forward DP / beam over arrival-epoch states on the fixed order.

    State at node k = arrival epoch t. Transition leg k: choose delay d from a
    candidate set (banked-relative re-profiled at the ACTUAL t, not bt[k]),
    arrive at t' = (t+d) + tof. Minimise final makespan.

    Because the profiled curves were taken at BANKED epochs bt[k] (not the
    actual DP epoch), we re-profile the chosen leg at the true epoch during the
    final validation chrono walk. The DP here uses an *epoch-shift-corrected*
    approximation: shifting the whole tail by Δ (current - banked arrival) is
    only exact if the transfer geometry is locally epoch-invariant, which it is
    NOT in general. So we use the DP only to PROPOSE per-leg delay vectors, and
    validate each proposal by the true chrono walk below.
    """
    # Candidate delays worth trying: union of {0} and any per-leg delay whose
    # local arr_off is within +2d of 0 (small idle that might pay off via a
    # genuinely shorter tof). Concentrate search on the expensive legs.
    cand_delays = {}
    for i in range(n - 1):
        prof = profiles[i]
        ds = [0.0]
        tof0 = bf[i]
        for d, tof, arr_off in prof:
            if tof is None:
                continue
            # a delay that yields a strictly shorter tof than banked AND modest
            # arrival penalty is a candidate for non-greedy improvement
            if tof < tof0 - 0.02 and arr_off < 3.0:
                ds.append(round(d, 3))
        cand_delays[i] = sorted(set(ds))
    interesting = [i for i in range(n - 1) if len(cand_delays[i]) > 1]
    print(f"[E-589] legs with a shorter-tof delay candidate: "
          f"{len(interesting)}", flush=True)
    tot_shorter = 0.0
    for i in interesting[:40]:
        best = min((p for p in profiles[i]
                    if p[1] is not None and p[0] > 0), key=lambda p: p[1])
        gain = bf[i] - best[1]
        tot_shorter += max(0.0, gain)
    print(f"[E-589] (sample) sum tof-reduction available on interesting legs "
          f"(ignoring idle cost) ~{tot_shorter:.2f}d", flush=True)

    # Iterated local search: greedily try, for each interesting leg, replacing
    # its delay and re-running the TRUE chrono walk from that leg forward; keep
    # only strict improvements (validated). This captures non-greedy gains
    # without trusting the epoch-shift approximation.
    best_dep_delays = np.zeros(n - 1)
    best_mk, best_x = true_walk_makespan(kt, n, perm, best_dep_delays)
    print(f"[E-589] zero-delay chrono walk mk={best_mk:.4f} "
          f"(banked greedy = {CURRENT_BANK})", flush=True)

    improved = True
    rounds = 0
    while improved and rounds < 3:
        improved = False
        rounds += 1
        for i in interesting:
            for d in cand_delays[i]:
                if d == 0.0:
                    continue
                trial = best_dep_delays.copy()
                trial[i] = d
                mk, x = true_walk_makespan(kt, n, perm, trial)
                if mk is not None and mk < best_mk - 1e-4:
                    best_mk = mk
                    best_x = x
                    best_dep_delays = trial
                    improved = True
                    print(f"[E-589] r{rounds} leg{i} delay={d:.2f} "
                          f"-> mk={mk:.4f}", flush=True)
        print(f"[E-589] round {rounds} best mk={best_mk:.4f}", flush=True)

    print(f"[E-589] FINAL best mk={best_mk:.4f} (banked {CURRENT_BANK})",
          flush=True)
    if best_x is not None and best_mk < CURRENT_BANK - 1e-4:
        fit = kt.fitness(best_x)
        if kt.is_feasible(fit):
            json.dump([{"decisionVector": best_x, "problem": "large",
                        "challenge": CHALLENGE}], open(OUT, "w"))
            print(f"[E-589] WROTE {OUT} mk={float(fit[0]):.4f} "
                  f"viols={list(fit[1:])}", flush=True)
        else:
            print(f"[E-589] best not feasible viols={list(fit[1:])}",
                  flush=True)
    else:
        print("[E-589] did NOT beat bank — wrote nothing.", flush=True)


def true_walk_makespan(kt, n, perm, dep_delays):
    """Chrono walk along fixed perm, applying dep_delays[i] extra idle BEFORE
    leg i's departure (on top of the earliest-feasible departure). Returns
    (makespan, x) or (None, None) if infeasible / no transfer."""
    cur, t = perm[0], 0.0
    times, tofs, dvs = [], [], []
    exc = 0
    for i in range(n - 1):
        j = perm[i + 1]
        td = t + float(dep_delays[i])
        thr_cheap = kt.dv_thr
        tof, dv = find_earliest_transfer(kt, cur, j, td, thr_cheap,
                                         TOF_WINDOW, N_STEPS)
        is_exc = False
        if tof is None and exc < kt.n_exc:
            tof, dv = find_earliest_transfer(kt, cur, j, td, kt.dv_exc,
                                             TOF_WINDOW, N_STEPS)
            if tof is not None:
                is_exc = True
        if tof is None:
            # fallback small waits for feasibility
            found = False
            for w in np.arange(0.5, 4.01, 0.5):
                t2 = td + w
                tof, dv = find_earliest_transfer(kt, cur, j, t2, kt.dv_thr,
                                                 TOF_WINDOW, N_STEPS)
                if tof is not None:
                    td = t2
                    found = True
                    break
                if exc < kt.n_exc:
                    tof, dv = find_earliest_transfer(kt, cur, j, t2,
                                                     kt.dv_exc, TOF_WINDOW,
                                                     N_STEPS)
                    if tof is not None:
                        td = t2
                        is_exc = True
                        found = True
                        break
            if not found:
                return None, None
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = td + tof
        cur = j
        if t > kt.max_time:
            return None, None
    if exc > kt.n_exc:
        return None, None
    x = [float(v) for v in times] + [float(v) for v in tofs] \
        + [float(p) for p in perm]
    mk = times[-1] + tofs[-1]
    return mk, x


if __name__ == "__main__":
    main()
