"""Ch2 KTTSP — per-leg NLP polish on a fixed permutation.

For a fixed permutation π, the makespan is determined by the (td, tof)
choices per leg subject to:
- td_k ≥ t_ready (chronology)
- Δv(π_k, π_{k+1}, td, tof) ≤ Δv_thr OR Δv_exc (with budget)
- Minimise arrival = td + tof for each leg → minimise final t_ready

`find_earliest_transfer` (used in greedy_findxfer) scans tof at FIXED
t_start = t_ready with n_steps granularity. This is locally optimal
for tof at that exact t_ready, but doesn't search over td > t_ready
(no waiting). Per-leg NLP with continuous (td, tof) can find:
- Shorter (td_offset + tof) pairs that the discrete scan missed
- "Wait briefly to take a shorter tof" trades that improve arrival

The 142.99 perm has been validated as a robust local optimum for
the existing greedy/2-opt/SA tooling. Per-leg NLP is a different
kind of polish: keep the permutation, optimise the timing only.

Sequential chain: each leg's optimal (td, tof) feeds the next.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def optimise_leg(kt, i, j, t_ready, dv_cap, wait_max=30.0,
                 tof_min=None, tof_max=None, n_starts=8):
    """Find (td, tof) minimising arrival = td + tof subject to
    Δv(i, j, td, tof) ≤ dv_cap, td ≥ t_ready, tof_min ≤ tof ≤ tof_max,
    td + tof ≤ kt.max_time. Multi-start scipy.minimize."""
    if tof_min is None:
        tof_min = max(kt.min_tof, 0.05)
    if tof_max is None:
        tof_max = min(kt.max_time - t_ready - 0.01, 40.0)
    if tof_max <= tof_min:
        return None
    # Objective: arrival = td + tof. Penalty for Δv > cap.

    def obj(x):
        td, tof = x
        if td < t_ready - 1e-6 or tof < tof_min or tof > tof_max:
            return 1e8
        if td + tof > kt.max_time + 1e-6:
            return 1e8
        dv = kt.compute_transfer(i, j, float(td), float(tof))
        pen = max(0.0, dv - dv_cap) * 1e4
        return td + tof + pen
    # Multi-start seeds
    seeds = []
    td_offsets = np.linspace(0.0, min(wait_max, kt.max_time - t_ready - 1),
                             n_starts // 2)
    tofs_seed = np.linspace(tof_min, min(tof_max, 8.0), n_starts // 2)
    for td_off in td_offsets:
        for tof_s in tofs_seed:
            seeds.append([t_ready + td_off, tof_s])
    best = None  # (arrival, td, tof, dv)
    for s in seeds:
        if s[0] + s[1] > kt.max_time:
            continue
        try:
            r = minimize(obj, s, method="Nelder-Mead",
                         options={"xatol": 1e-3, "fatol": 1e-3,
                                  "maxiter": 100})
        except Exception:
            continue
        td, tof = float(r.x[0]), float(r.x[1])
        if td < t_ready - 1e-6 or td + tof > kt.max_time + 1e-6:
            continue
        if tof < tof_min - 1e-6 or tof > tof_max + 1e-6:
            continue
        dv = kt.compute_transfer(i, j, td, tof)
        if dv <= dv_cap + 1e-6:
            arr = td + tof
            if best is None or arr < best[0]:
                best = (arr, td, tof, dv)
    return best


def polish(inst, problem="small",
           in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
           out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.4f} d", flush=True)

    # Identify which legs need ≤ dv_thr (cheap) vs ≤ dv_exc (exception)
    # by computing the current Δv at the original (td, tof). We preserve
    # the cheap/exc assignment from the banked solution.
    times0 = x0[:n - 1]
    tofs0 = x0[n - 1:2 * (n - 1)]
    cap_per_leg = []
    for k in range(n - 1):
        dv0 = kt.compute_transfer(perm[k], perm[k + 1],
                                   times0[k], tofs0[k])
        # If original is exception: allow up to dv_exc
        cap = kt.dv_exc if dv0 > kt.dv_thr else kt.dv_thr
        cap_per_leg.append(cap)
    n_exc_orig = sum(1 for c in cap_per_leg if c > kt.dv_thr)
    print(f"Original exceptions: {n_exc_orig}", flush=True)

    # Sequential polish: optimise leg-by-leg
    t_ready = 0.0
    times_new = []
    tofs_new = []
    dvs_new = []
    t0 = time.time()
    for k in range(n - 1):
        i, j = perm[k], perm[k + 1]
        cap = cap_per_leg[k]
        result = optimise_leg(kt, i, j, t_ready, cap)
        if result is None:
            # Fallback: keep original
            td_orig = max(times0[k], t_ready)
            tof_orig = tofs0[k]
            times_new.append(td_orig)
            tofs_new.append(tof_orig)
            dvs_new.append(kt.compute_transfer(i, j, td_orig, tof_orig))
            t_ready = td_orig + tof_orig
            continue
        arr, td, tof, dv = result
        times_new.append(td)
        tofs_new.append(tof)
        dvs_new.append(dv)
        t_ready = arr
    wall = time.time() - t0
    x_new = times_new + tofs_new + [float(p) for p in perm]
    f_new = kt.fitness(x_new)
    feas_new = kt.is_feasible(f_new)
    print(f"Polished: mk={f_new[0]:.4f}, fitness={f_new}, feas={feas_new}",
          flush=True)
    print(f"Δmk = {initial_mk - f_new[0]:.4f} d, wall={wall:.1f} s",
          flush=True)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "polished_mk": float(f_new[0]), "feasible": feas_new,
            "delta_d": float(initial_mk - f_new[0]),
            "rank3_small_d": 111.76}
    if feas_new and f_new[0] < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": list(x_new),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    problem = sys.argv[1] if len(sys.argv) > 1 else "small"
    print(json.dumps(polish(inst, problem=problem), indent=2))
