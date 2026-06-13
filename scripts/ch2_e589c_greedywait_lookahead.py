"""E-589c — correct non-greedy timing test over the E-588 greedy-wait walk.

Baseline = E-588 greedy-wait forward pass (banked 934.4452): at each leg, pick
the wait delta that MINIMISES arrival. This is per-leg arrival-optimal.

Non-greedy lever: force, at some leg i, an EXTRA wait beyond the greedy-optimal
(a strictly LATER, hence locally-worse, departure), then continue greedy-wait
for the rest. If the downstream greedy-wait tail becomes cheap enough that the
final makespan drops, that's a genuine non-greedy gain the greedy pass cannot
see. We measure each forced-wait leg by a K-leg greedy-wait lookahead first
(cheap), then validate survivors by the FULL greedy-wait walk + kt.fitness.

GUARDED: writes only /tmp/ch2_large_cand.json, strictly-better & feasible.
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
_GWMAX = float(os.environ.get("E589C_GWMAX", "12.0"))
_GWN = int(os.environ.get("E589C_GWN", "49"))
GW_DELTAS = np.round(np.linspace(0.0, _GWMAX, _GWN), 4)   # greedy wait grid
_FMAX = float(os.environ.get("E589C_FMAX", "12.0"))
_FSTEP = float(os.environ.get("E589C_FSTEP", "0.5"))
FORCE_GRID = np.round(np.arange(_FSTEP, _FMAX + 0.001, _FSTEP), 3)
K = int(os.environ.get("E589C_K", "6"))
_PTOF = float(os.environ.get("E589C_PTOF", "1.5"))   # probe legs with tof>this

_kt = None
_perm = None


def _init():
    global _kt, _perm
    _kt = KTTSP(INST)
    bank = json.load(open(BANK))[0]["decisionVector"]
    n = _kt.n
    _perm = [int(round(v)) for v in bank[2 * (n - 1):]]


_PROBE_GW = np.round(np.linspace(0.0, _GWMAX,
                                 int(os.environ.get("E589C_PGWN", "13"))), 4)


def _greedy_leg(a, b, t, thr):
    """Arrival-minimising departure for one leg starting from epoch t.
    Returns (dep, tof, arr) or None. Uses the (coarser) probe GW grid."""
    best = None
    for d in _PROBE_GW:
        td = t + float(d)
        if td + 0.05 >= _kt.max_time:
            break
        tof, dv = find_earliest_transfer(_kt, a, b, td, thr,
                                         TOF_WINDOW, N_STEPS)
        if tof is None:
            continue
        arr = td + tof
        if best is None or arr < best[2] - 1e-9:
            best = (td, tof, arr)
    return best


def _greedy_miniwalk(start_leg, t_start, depth, force_first=0.0):
    """Greedy-wait mini-walk of `depth` legs from epoch t_start. On the first
    leg, force at least `force_first` extra wait (depart no earlier than
    t_start+force_first, then still greedy-optimise wait beyond that).
    Returns arrival epoch after the legs, or None."""
    n = _kt.n
    t = t_start
    for off in range(depth):
        li = start_leg + off
        if li >= n - 1:
            break
        a, b = _perm[li], _perm[li + 1]
        thr = _kt.dv_exc if li in EXC_LEGS else _kt.dv_thr
        t0 = t + (force_first if off == 0 else 0.0)
        res = _greedy_leg(a, b, t0, thr)
        if res is None:
            return None
        t = res[2]
    return t


def _probe_leg(args):
    """leg i: K-leg greedy arrival with no force vs best forced extra wait."""
    i, t_in = args
    n = _kt.n
    depth = min(K, (n - 1) - i)
    ref = _greedy_miniwalk(i, t_in, depth, force_first=0.0)
    if ref is None:
        return i, 0.0, 0.0
    best_f, best_arr = 0.0, ref
    for f in FORCE_GRID:
        arr = _greedy_miniwalk(i, t_in, depth, force_first=float(f))
        if arr is None:
            continue
        if arr < best_arr - 1e-4:
            best_arr, best_f = arr, float(f)
    return i, best_f, ref - best_arr


def greedy_full(kt, n, perm, force=None):
    """Full greedy-wait walk; optional dict {leg: extra_forced_wait}.
    Returns (mk, x) or (None, None)."""
    if force is None:
        force = {}
    t = 0.0
    times, tofs = [], []
    exc = 0
    for i in range(n - 1):
        a, b = perm[i], perm[i + 1]
        thr = kt.dv_exc if i in EXC_LEGS else kt.dv_thr
        t0 = t + float(force.get(i, 0.0))
        best = None
        for d in GW_DELTAS:
            td = t0 + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof, dv = find_earliest_transfer(kt, a, b, td, thr,
                                             TOF_WINDOW, N_STEPS)
            if tof is None:
                continue
            arr = td + tof
            if best is None or arr < best[2] - 1e-9:
                best = (td, tof, arr)
        if best is None:
            return None, None
        td, tof, arr = best
        times.append(td)
        tofs.append(tof)
        t = arr
        if t > kt.max_time:
            return None, None
    x = [float(v) for v in times] + [float(v) for v in tofs] \
        + [float(p) for p in perm]
    return times[-1] + tofs[-1], x


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    bt = np.array(bank[:n - 1])
    bf = np.array(bank[n - 1:2 * (n - 1)])
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    print(f"[E-589c] bank mk={float(kt.fitness(bank)[0]):.4f}", flush=True)

    base_mk, base_x = greedy_full(kt, n, perm)
    print(f"[E-589c] greedy-wait baseline mk={base_mk:.4f} "
          f"(should ~= {CURRENT_BANK})", flush=True)

    # Probe forced extra wait on legs with non-trivial tof; incoming epoch from
    # the banked walk (good approximation of the greedy-wait epoch).
    cand = [i for i in range(n - 1) if bf[i] > _PTOF]
    tasks = [(i, float(bt[i])) for i in cand]
    print(f"[E-589c] probing forced-wait on {len(tasks)} legs, K={K}",
          flush=True)
    workers = int(os.environ.get("E589C_WORKERS", "2"))
    res = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_init) as ex:
        for r in ex.map(_probe_leg, tasks, chunksize=4):
            res.append(r)
    pos = sorted([r for r in res if r[2] > 1e-3], key=lambda x: -x[2])
    print(f"[E-589c] legs where FORCED extra wait beats greedy over {K} legs: "
          f"{len(pos)}", flush=True)
    for r in pos[:30]:
        print(f"    leg{r[0]} force={r[1]:.2f} K-leg gain={r[2]:+.3f}",
              flush=True)
    if not pos:
        print("[E-589c] NO non-greedy forced-wait lever. Greedy-wait IS the "
              "order-fixed timing optimum.", flush=True)
        return

    # Validate by full greedy-wait walk, applying forced waits jointly.
    force = {}
    best_mk, best_x = base_mk, base_x
    accepted = 0
    for r in pos:
        i, f = r[0], r[1]
        trial = dict(force)
        trial[i] = f
        mk, x = greedy_full(kt, n, perm, trial)
        if mk is not None and mk < best_mk - 1e-4:
            best_mk, best_x, force = mk, x, trial
            accepted += 1
            print(f"[E-589c] accept leg{i} force={f:.2f} -> mk={mk:.4f}",
                  flush=True)
    print(f"[E-589c] accepted {accepted}; best mk={best_mk:.4f} "
          f"(banked {CURRENT_BANK})", flush=True)
    if best_x is not None and best_mk < CURRENT_BANK - 1e-4:
        fit = kt.fitness(best_x)
        if kt.is_feasible(fit):
            json.dump([{"decisionVector": best_x, "problem": "large",
                        "challenge": CHALLENGE}], open(OUT, "w"))
            fit2 = kt.fitness(best_x)
            print(f"[E-589c] WROTE {OUT} mk={float(fit2[0]):.4f} "
                  f"feas={kt.is_feasible(fit2)} viols={list(fit2[1:])}",
                  flush=True)
        else:
            print(f"[E-589c] infeasible viols={list(fit[1:])}", flush=True)
    else:
        print("[E-589c] did NOT beat bank — wrote nothing.", flush=True)


if __name__ == "__main__":
    main()
