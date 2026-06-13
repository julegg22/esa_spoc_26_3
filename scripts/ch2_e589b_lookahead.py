"""E-589b — Ch2 LARGE non-greedy timing: K-leg lookahead from the BANKED walk.

The banked 934.4452 walk is the per-leg greedy arrival-minimiser. Non-greedy
gain is only possible if, at some leg i, choosing a delay d that LOSES locally
(later arrival at i+1) lets a downstream leg's transfer window become so much
cheaper that the net arrival after K legs is EARLIER than the banked tail.

This probe, for each leg i, fixes the true banked incoming epoch t0=bt[i],
then for each delay d on a grid does an EXACT greedy chrono mini-walk of the
next K legs (perm[i..i+K]) starting from departure t0+d, and compares the
arrival after K legs to the banked arrival after K legs. If any d gives a
strictly earlier K-leg arrival, that's a non-greedy lever; we then splice it
into the full perm and validate by the true full chrono walk + kt.fitness.

Parallelized over legs. GUARDED: writes only /tmp/ch2_large_cand.json.
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
K = 4                       # lookahead depth (legs)
DELAY_GRID = np.round(np.arange(0.5, 12.01, 0.5), 3)

_kt = None
_perm = None
_bt = None
_bf = None


def _init():
    global _kt, _perm, _bt, _bf
    _kt = KTTSP(INST)
    bank = json.load(open(BANK))[0]["decisionVector"]
    n = _kt.n
    _bt = np.array(bank[:n - 1])
    _bf = np.array(bank[n - 1:2 * (n - 1)])
    _perm = [int(round(v)) for v in bank[2 * (n - 1):]]


def _earliest(a, b, t, exc_used):
    """Greedy earliest-arrival pick at epoch t (cheap then exc). Returns
    (tof, is_exc) or (None, False)."""
    tof, dv = find_earliest_transfer(_kt, a, b, t, _kt.dv_thr,
                                     TOF_WINDOW, N_STEPS)
    if tof is not None:
        return tof, False
    if exc_used < _kt.n_exc:
        tof, dv = find_earliest_transfer(_kt, a, b, t, _kt.dv_exc,
                                         TOF_WINDOW, N_STEPS)
        if tof is not None:
            return tof, True
    return None, False


def _miniwalk(start_leg, t_dep, depth):
    """Greedy earliest mini-walk of `depth` legs starting by departing leg
    start_leg at t_dep. Returns arrival epoch after the legs, or None.
    Exc budget treated as unlimited locally (legs within window are sparse);
    only cheap is attempted first then exc as fallback."""
    n = _kt.n
    t = t_dep
    cur = _perm[start_leg]
    exc_used = 0
    for off in range(depth):
        li = start_leg + off
        if li >= n - 1:
            break
        a, b = _perm[li], _perm[li + 1]
        if off == 0:
            dep = t  # apply chosen delay only on first leg
        else:
            dep = t  # subsequent legs depart immediately (greedy)
        tof, is_exc = _earliest(a, b, dep, exc_used)
        if tof is None:
            return None
        if is_exc:
            exc_used += 1
        t = dep + tof
        cur = b
    return t


def _probe_leg(i):
    """For leg i: banked K-leg arrival vs best delayed K-leg arrival."""
    n = _kt.n
    if i + K > n - 1:
        depth = (n - 1) - i
    else:
        depth = K
    t0 = float(_bt[i])
    # banked arrival after `depth` legs = bt[i+depth] if exists else final
    if i + depth <= n - 2:
        banked_arr = float(_bt[i + depth])
    else:
        banked_arr = float(_bt[-1] + _bf[-1])
    # greedy (delay 0) reference using our miniwalk (should ~match banked_arr)
    ref0 = _miniwalk(i, t0, depth)
    best = (0.0, ref0 if ref0 is not None else banked_arr)
    for d in DELAY_GRID:
        arr = _miniwalk(i, t0 + float(d), depth)
        if arr is None:
            continue
        if arr < best[1] - 1e-4:
            best = (float(d), arr)
    gain = (ref0 if ref0 is not None else banked_arr) - best[1]
    return i, best[0], gain, (ref0 if ref0 is not None else banked_arr)


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    bt = np.array(bank[:n - 1])
    bf = np.array(bank[n - 1:2 * (n - 1)])
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    print(f"[E-589b] bank mk={float(kt.fitness(bank)[0]):.4f} K={K}",
          flush=True)

    # restrict to legs that could matter: tof>2 (room to shrink) + a margin
    cand_legs = [i for i in range(n - 1) if bf[i] > 2.0]
    print(f"[E-589b] probing {len(cand_legs)} legs (tof>2) with K={K} "
          f"lookahead", flush=True)
    workers = int(os.environ.get("E589B_WORKERS", "2"))
    results = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
        for r in ex.map(_probe_leg, cand_legs, chunksize=4):
            results.append(r)
    results.sort(key=lambda x: -x[2])
    pos = [r for r in results if r[2] > 1e-3]
    print(f"[E-589b] legs where a delay gives EARLIER {K}-leg arrival: "
          f"{len(pos)}", flush=True)
    for r in pos[:30]:
        print(f"    leg{r[0]} delay={r[1]:.2f} K-leg gain={r[2]:+.3f} "
              f"(ref_arr={r[3]:.2f})", flush=True)
    if not pos:
        print("[E-589b] NO non-greedy lookahead lever exists. The banked "
              "greedy walk is the order-fixed timing optimum.", flush=True)
        return

    # Splice promising delays into full perm and validate by true full walk.
    # Apply delays jointly (largest-gain first), revalidate each accept.
    splice_and_validate(kt, n, perm, bt, bf, pos)


def splice_and_validate(kt, n, perm, bt, bf, pos):
    delays = np.zeros(n - 1)
    best_mk, best_x = full_walk(kt, n, perm, delays)
    print(f"[E-589b] zero-delay full walk mk={best_mk:.4f}", flush=True)
    # also evaluate banked itself as reference baseline via greedy-wait? We
    # compare against CURRENT_BANK directly.
    accepted = 0
    for r in pos:
        i, d = r[0], r[1]
        trial = delays.copy()
        trial[i] = d
        mk, x = full_walk(kt, n, perm, trial)
        if mk is not None and mk < (best_mk if best_mk else 1e9) - 1e-4:
            best_mk, best_x, delays = mk, x, trial
            accepted += 1
            print(f"[E-589b] accept leg{i} d={d:.2f} -> mk={mk:.4f}",
                  flush=True)
    print(f"[E-589b] accepted {accepted}; best full-walk mk={best_mk:.4f} "
          f"(banked {CURRENT_BANK})", flush=True)
    if best_x is not None and best_mk < CURRENT_BANK - 1e-4:
        fit = kt.fitness(best_x)
        if kt.is_feasible(fit):
            json.dump([{"decisionVector": best_x, "problem": "large",
                        "challenge": CHALLENGE}], open(OUT, "w"))
            print(f"[E-589b] WROTE {OUT} mk={float(fit[0]):.4f} "
                  f"viols={list(fit[1:])}", flush=True)
        else:
            print(f"[E-589b] infeasible viols={list(fit[1:])}", flush=True)
    else:
        print("[E-589b] did NOT beat bank — wrote nothing.", flush=True)


def full_walk(kt, n, perm, delays):
    cur, t = perm[0], 0.0
    times, tofs = [], []
    exc = 0
    for i in range(n - 1):
        j = perm[i + 1]
        td = t + float(delays[i])
        tof, dv = find_earliest_transfer(kt, cur, j, td, kt.dv_thr,
                                         TOF_WINDOW, N_STEPS)
        is_exc = False
        if tof is None and exc < kt.n_exc:
            tof, dv = find_earliest_transfer(kt, cur, j, td, kt.dv_exc,
                                             TOF_WINDOW, N_STEPS)
            if tof is not None:
                is_exc = True
        if tof is None:
            found = False
            for w in np.arange(0.5, 4.01, 0.5):
                t2 = td + w
                tof, dv = find_earliest_transfer(kt, cur, j, t2, kt.dv_thr,
                                                 TOF_WINDOW, N_STEPS)
                if tof is not None:
                    td, found = t2, True
                    break
                if exc < kt.n_exc:
                    tof, dv = find_earliest_transfer(kt, cur, j, t2,
                                                     kt.dv_exc, TOF_WINDOW,
                                                     N_STEPS)
                    if tof is not None:
                        td, is_exc, found = t2, True, True
                        break
            if not found:
                return None, None
        times.append(td)
        tofs.append(tof)
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
    return times[-1] + tofs[-1], x


if __name__ == "__main__":
    main()
