"""Ch2 KTTSP — pairwise NLP polish via coordinate descent.

Single-leg sequential polish (ch2_per_leg_nlp_polish) is greedy: at
leg k it minimises (td_k + tof_k), which fixes t_ready_{k+1}. But
leg k could trade — take a tof slightly longer to depart earlier OR
to arrive on a faster onward window. A *pair* polish over (k, k+1)
captures one-step look-ahead.

For each adjacent pair (k, k+1), holding all earlier and later legs
fixed (their td's are frozen at current values; later legs' t_ready
is shifted by the pair's change), jointly optimise
(td_k, tof_k, td_{k+1}, tof_{k+1}) to minimise the arrival of leg
k+1, subject to:
  td_k ≥ t_ready_k (from leg k-1)
  td_{k+1} ≥ td_k + tof_k (chronology within pair)
  Δv(perm[k], perm[k+1], td_k, tof_k) ≤ cap_k
  Δv(perm[k+1], perm[k+2], td_{k+1}, tof_{k+1}) ≤ cap_{k+1}
  bounds on tof and total time

Sweep forward across all pairs, then backward, until total makespan
stops decreasing. Each pair NLP is small (4 vars, 4 constraints, ~50
COBYLA iters).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def optimise_pair(kt, i, j, k_last, t_ready_pair, dv_cap_a, dv_cap_b,
                  td_a0, tof_a0, td_b0, tof_b0):
    """Joint NLP over (td_a, tof_a, td_b, tof_b) for adjacent pair.

    i, j, k_last are perm[idx], perm[idx+1], perm[idx+2].
    t_ready_pair is the earliest valid td_a.
    Returns (td_a, tof_a, td_b, tof_b, arrival_b) or None on failure.
    """
    tof_min = max(kt.min_tof, 0.05)
    # Cap b's tof so td_b + tof_b ≤ max_time
    max_total = kt.max_time
    # Cap a's tof so td_a + tof_a ≤ td_b initial guess
    # We let COBYLA enforce sequence chronology

    def obj(x):
        td_a, tof_a, td_b, tof_b = x
        if td_a < t_ready_pair - 1e-6:
            return 1e8
        if tof_a < tof_min or tof_b < tof_min:
            return 1e8
        if td_b < td_a + tof_a - 1e-6:
            return 1e8
        if td_b + tof_b > max_total + 1e-6:
            return 1e8
        dv_a = kt.compute_transfer(i, j, float(td_a), float(tof_a))
        dv_b = kt.compute_transfer(j, k_last, float(td_b), float(tof_b))
        pen_a = max(0.0, dv_a - dv_cap_a) * 1e4
        pen_b = max(0.0, dv_b - dv_cap_b) * 1e4
        # Objective: pair arrival = td_b + tof_b
        return td_b + tof_b + pen_a + pen_b

    # Seed: current values, shifted to t_ready
    td_a_init = max(td_a0, t_ready_pair)
    tof_a_init = tof_a0
    td_b_init = max(td_b0, td_a_init + tof_a_init)
    tof_b_init = tof_b0
    if td_b_init + tof_b_init > max_total:
        # Shrink tof_b
        tof_b_init = max(tof_min, max_total - td_b_init - 0.001)
    seeds = [
        [td_a_init, tof_a_init, td_b_init, tof_b_init],
    ]
    # A few jittered seeds for multi-start
    rng = np.random.default_rng(0)
    for _ in range(4):
        seeds.append([
            td_a_init + rng.uniform(-0.5, 0.5),
            max(tof_min, tof_a_init * rng.uniform(0.7, 1.3)),
            td_b_init + rng.uniform(-0.5, 0.5),
            max(tof_min, tof_b_init * rng.uniform(0.7, 1.3)),
        ])
    # Pre-evaluate current as known-baseline
    dv_a0 = kt.compute_transfer(i, j, td_a_init, tof_a_init)
    dv_b0 = kt.compute_transfer(j, k_last, td_b_init, tof_b_init)
    if dv_a0 <= dv_cap_a + 1e-6 and dv_b0 <= dv_cap_b + 1e-6 \
            and td_b_init + tof_b_init <= max_total + 1e-6 \
            and td_b_init >= td_a_init + tof_a_init - 1e-6 \
            and td_a_init >= t_ready_pair - 1e-6:
        best = (td_b_init + tof_b_init, td_a_init, tof_a_init,
                td_b_init, tof_b_init)
    else:
        best = None
    for s in seeds:
        try:
            r = minimize(obj, s, method="Nelder-Mead",
                         options={"xatol": 1e-3, "fatol": 1e-3,
                                  "maxiter": 300})
        except Exception:
            continue
        td_a, tof_a, td_b, tof_b = [float(v) for v in r.x]
        if (td_a < t_ready_pair - 1e-6
                or tof_a < tof_min - 1e-6
                or tof_b < tof_min - 1e-6
                or td_b < td_a + tof_a - 1e-6
                or td_b + tof_b > max_total + 1e-6):
            continue
        dv_a = kt.compute_transfer(i, j, td_a, tof_a)
        dv_b = kt.compute_transfer(j, k_last, td_b, tof_b)
        if dv_a > dv_cap_a + 1e-6 or dv_b > dv_cap_b + 1e-6:
            continue
        arr = td_b + tof_b
        if best is None or arr < best[0] - 1e-5:
            best = (arr, td_a, tof_a, td_b, tof_b)
    return best


def pairwise_polish(kt, perm, times0, tofs0, cap_per_leg,
                    max_sweeps=4, verbose=True):
    """Coordinate descent over adjacent leg pairs. Returns
    (times, tofs, mk)."""
    times = list(times0)
    tofs = list(tofs0)
    n_legs = len(perm) - 1
    for sweep in range(max_sweeps):
        # Forward sweep over pairs (0,1), (1,2), ..., (n_legs-2, n_legs-1)
        before_arr = times[-1] + tofs[-1]
        improved = 0
        for k in range(n_legs - 1):
            # Pair = legs k and k+1; nodes (perm[k], perm[k+1], perm[k+2])
            i = perm[k]
            j = perm[k + 1]
            k_last = perm[k + 2]
            t_ready = 0.0 if k == 0 else times[k - 1] + tofs[k - 1]
            cap_a = cap_per_leg[k]
            cap_b = cap_per_leg[k + 1]
            res = optimise_pair(kt, i, j, k_last, t_ready,
                                cap_a, cap_b,
                                times[k], tofs[k],
                                times[k + 1], tofs[k + 1])
            if res is None:
                continue
            arr, td_a, tof_a, td_b, tof_b = res
            old_arr = times[k + 1] + tofs[k + 1]
            if arr < old_arr - 1e-5:
                times[k] = td_a
                tofs[k] = tof_a
                times[k + 1] = td_b
                tofs[k + 1] = tof_b
                improved += 1
        after_arr = times[-1] + tofs[-1]
        if verbose:
            print(f"  sweep {sweep}: {before_arr:.4f} → "
                  f"{after_arr:.4f} (improved {improved} pairs)",
                  flush=True)
        if after_arr >= before_arr - 1e-5:
            break
    return times, tofs, times[-1] + tofs[-1]


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small"):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.4f} d", flush=True)
    times0 = list(x0[:n - 1])
    tofs0 = list(x0[n - 1:2 * (n - 1)])
    cap_per_leg = []
    for k in range(n - 1):
        dv0 = kt.compute_transfer(perm[k], perm[k + 1], times0[k], tofs0[k])
        cap = kt.dv_exc if dv0 > kt.dv_thr else kt.dv_thr
        cap_per_leg.append(cap)
    t0 = time.time()
    times, tofs, mk = pairwise_polish(kt, perm, times0, tofs0, cap_per_leg)
    wall = time.time() - t0
    x_new = times + tofs + [float(p) for p in perm]
    f_new = kt.fitness(x_new)
    feas_new = kt.is_feasible(f_new)
    print(f"Polished: mk={f_new[0]:.4f}, fitness={f_new}, feas={feas_new}",
          flush=True)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "polished_mk": float(f_new[0]), "feasible": feas_new,
            "delta_d": float(initial_mk - f_new[0]),
            "rank3_small_d": 111.76}
    if feas_new and f_new[0] < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(x_new),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
