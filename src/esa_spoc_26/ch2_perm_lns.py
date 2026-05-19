"""Ch2 KTTSP — permutation LNS with leg-failure recovery (T-008 v2).

Builds on perm_nlp: chronological NLP fails at some leg k when the
remaining tomatoes can't be reached cheaply. This LNS:
1. CP-SAT seeds a static-min-Σtof Hamiltonian (no chronology).
2. NLP walks the chain; on first failure at leg k:
   a. Try swapping perm[k+1] with each later tomato perm[m], m>k+1.
   b. Re-evaluate the suffix [k:] with the swap; keep the best
      partial chain (longest reach or feasible).
3. After a swap, retry recovery up to N attempts. Keep best partial.

Goal: bank ANY feasible Ch2 small (rank-3 = 112 d; even rank-10 = ~5 pt).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_nlp_greedy import solve_leg_nlp
from esa_spoc_26.ch2_perm_nlp import static_perm_cpsat


def walk_chain(kt, perm, arr_weight=1.0, dv_thr=None, dv_exc=None,
               n_exc=None):
    """Walk perm chronologically, NLP per leg. Return:
       (legs_completed, t_ready, exc_used, times[], tofs[], dvs[]).
    Stops at first NLP failure."""
    dv_thr = dv_thr if dv_thr is not None else kt.dv_thr
    dv_exc = dv_exc if dv_exc is not None else kt.dv_exc
    n_exc = n_exc if n_exc is not None else kt.n_exc
    t = 0.0
    times, tofs, dvs = [], [], []
    exc = 0
    for i in range(len(perm) - 1):
        legs_left = len(perm) - 1 - i
        fair = (kt.max_time - t) / max(legs_left, 1)
        t_budget = min(kt.max_time, t + fair * 4.0)
        dv_cap = dv_thr if exc >= n_exc else dv_exc
        r = solve_leg_nlp(kt, perm[i], perm[i + 1], t,
                          t_budget=t_budget, dv_cap=dv_cap,
                          arr_weight=arr_weight)
        if r is None:
            return i, t, exc, times, tofs, dvs
        dv, td, tof = r
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if dv > dv_thr:
            exc += 1
        t = td + tof
        if t > kt.max_time + 1e-6:
            return i + 1, t, exc, times, tofs, dvs
    return len(perm) - 1, t, exc, times, tofs, dvs


def lns_repair(kt, perm0, max_swaps=5, time_budget=600.0,
               arr_weight=1.0, verbose=True, seed=0):
    rng = np.random.default_rng(seed)
    """Walk perm; on failure at leg k, try swapping perm[k+1] with each
    perm[m], m∈(k+1, n). Pick the swap maximising progress (largest k
    after re-walk; tiebreak smaller makespan). Iterate."""
    perm = list(perm0)
    n = len(perm)
    t0 = time.time()
    best_partial = None  # (legs, t, perm, times, tofs, dvs, exc)
    for it in range(max_swaps):
        if time.time() - t0 > time_budget:
            break
        legs, t, exc, times, tofs, dvs = walk_chain(
            kt, perm, arr_weight=arr_weight)
        if verbose:
            print(f"  iter{it}: legs={legs}/{n-1}, t={t:.1f}, exc={exc}", flush=True)
        full = legs == n - 1 and t <= kt.max_time
        if full:
            x = times + tofs + [float(p) for p in perm]
            f = kt.fitness(x)
            if kt.is_feasible(f):
                return x, f, True, perm
            # not feasible per fitness — odd; record
            return x, f, False, perm
        if (best_partial is None or legs > best_partial[0]
                or (legs == best_partial[0] and t < best_partial[1])):
            best_partial = (legs, t, list(perm), list(times), list(tofs),
                            list(dvs), exc)
        # try swaps at position legs+1 (the failed destination)
        kfail = legs  # failed-leg index (perm[kfail+1] is the unreachable)
        if kfail >= n - 1:
            break
        candidates = list(range(kfail + 2, n))
        rng.shuffle(candidates)
        improved = False
        for m in candidates[:min(15, len(candidates))]:
            cand = list(perm)
            cand[kfail + 1], cand[m] = cand[m], cand[kfail + 1]
            l2, _t2, _, _, _, _ = walk_chain(
                kt, cand, arr_weight=arr_weight)
            if l2 > legs:
                perm = cand
                improved = True
                if verbose:
                    print(f"    swap{kfail+1}<->{m}: legs {legs}→{l2}",
                          flush=True)
                break
        if not improved:
            break
    # Return best partial
    if best_partial is None:
        return None, None, False, perm
    legs, t, p, times, tofs, dvs, exc = best_partial
    return None, None, False, p   # no feasible found


def solve_lns(inst, problem="small",
              npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
              out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
              cpsat_s=30.0, lns_s=600.0):
    kt = KTTSP(inst)
    t0 = time.time()
    perm0, st = static_perm_cpsat(npz_w=npz_w, n=kt.n,
                                  max_s=cpsat_s, max_exc=kt.n_exc)
    cp_s = time.time() - t0
    if perm0 is None:
        return {"problem": problem, "feasible": False,
                "cpsat_status": st, "cpsat_s": round(cp_s, 1)}
    t1 = time.time()
    x, f, feas, perm = lns_repair(kt, perm0, max_swaps=20,
                                  time_budget=lns_s)
    lns_t = time.time() - t1
    res = {"problem": problem, "n": kt.n,
           "perm0": [int(p) for p in perm0],
           "perm_final": [int(p) for p in perm],
           "cpsat_s": round(cp_s, 1), "lns_s": round(lns_t, 1),
           "feasible": feas}
    if x is not None:
        res.update({"makespan_d": round(f[0], 3),
                    "perm_c": f[1], "dv_c": f[2],
                    "time_c": f[3], "exc_c": f[4],
                    "rank3_small_d": 111.76})
        if feas:
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            res["artifact"] = str(p)
    return res


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    cps = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    lnss = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    print(json.dumps(solve_lns(inst, cpsat_s=cps, lns_s=lnss), indent=2))
