"""Ch2 KTTSP — joint NLP polish over ALL (td, tof) variables.

Per-leg polish (greedy) and pairwise polish (one-step look-ahead)
both confirmed 142.9202 as a local optimum for the banked perm.
To break out, we need to optimise ALL 2*(n-1) = 96 timing
variables JOINTLY with the full constraint system:

minimize    times[n-2] + tofs[n-2]              (final arrival)
subject to  times[0] >= 0
            times[k+1] >= times[k] + tofs[k]    for k = 0..n-3
            times[k] + tofs[k] <= max_time      for k = 0..n-2
            tof_min <= tofs[k] <= max_tof       for k = 0..n-2
            Δv(perm[k], perm[k+1], times[k], tofs[k]) <= cap_k

This is what trajectory-optimisation papers do (Conway 2010; Tao et
al. 2023). scipy.optimize.minimize with method='SLSQP' supports
nonlinear inequality constraints. Warm-start at the banked timings.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def joint_polish(kt, perm, times0, tofs0, cap_per_leg,
                 maxiter=200, verbose=True):
    """SLSQP joint optimisation over all (td, tof). Returns
    (times, tofs, mk). Warm-start at (times0, tofs0)."""
    n_legs = len(perm) - 1
    # x packing: x[0:n_legs] = td, x[n_legs:2*n_legs] = tof
    x0 = np.array(list(times0) + list(tofs0))

    def obj(x):
        return x[n_legs - 1] + x[2 * n_legs - 1]

    def obj_grad(x):
        g = np.zeros_like(x)
        g[n_legs - 1] = 1.0
        g[2 * n_legs - 1] = 1.0
        return g
    # Chronology: times[k+1] - times[k] - tofs[k] >= 0
    chron = []
    for k in range(n_legs - 1):
        def chron_k(x, k=k):
            return x[k + 1] - x[k] - x[n_legs + k]
        chron.append({"type": "ineq", "fun": chron_k})
    # Max time: max_time - times[k] - tofs[k] >= 0
    mt = []
    for k in range(n_legs):
        def mt_k(x, k=k):
            return kt.max_time - x[k] - x[n_legs + k]
        mt.append({"type": "ineq", "fun": mt_k})
    # First-leg: times[0] >= 0
    mt.append({"type": "ineq", "fun": lambda x: x[0]})
    # Δv: cap_k - Δv(perm[k], perm[k+1], td_k, tof_k) >= 0
    dv = []
    for k in range(n_legs):
        def dv_k(x, k=k):
            return cap_per_leg[k] - kt.compute_transfer(
                perm[k], perm[k + 1], float(x[k]), float(x[n_legs + k]))
        dv.append({"type": "ineq", "fun": dv_k})
    # Bounds: tof_min <= tofs <= max_tof (rough)
    tof_min = max(kt.min_tof, 0.05)
    bounds = [(0.0, kt.max_time)] * n_legs + \
             [(tof_min, 40.0)] * n_legs
    cons = chron + mt + dv
    t0 = time.time()
    if verbose:
        print(f"Joint NLP: {2*n_legs} vars, {len(cons)} inequality "
              f"constraints, warm-start mk={x0[n_legs-1]+x0[2*n_legs-1]:.4f}",
              flush=True)
    try:
        r = minimize(obj, x0, jac=obj_grad, method="SLSQP",
                     bounds=bounds, constraints=cons,
                     options={"maxiter": maxiter, "ftol": 1e-6,
                              "disp": verbose})
    except Exception as e:
        print(f"  SLSQP failed: {e}", flush=True)
        return list(times0), list(tofs0), times0[-1] + tofs0[-1]
    wall = time.time() - t0
    if verbose:
        print(f"  SLSQP done: status={r.status}, "
              f"nit={r.nit}, fun={r.fun:.4f}, wall={wall:.1f}s",
              flush=True)
    times = list(r.x[:n_legs])
    tofs = list(r.x[n_legs:])
    return times, tofs, times[-1] + tofs[-1]


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", maxiter=300):
    # Map problem name to KTTSP instance filename
    inst_name = {"small": "easy", "medium": "medium",
                 "large": "large"}.get(problem, problem)
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/{inst_name}.kttsp")
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
    safety_margin = 5e-4  # SLSQP nonlinear-constraint tolerance buffer
    for k in range(n - 1):
        dv0 = kt.compute_transfer(perm[k], perm[k + 1], times0[k], tofs0[k])
        cap_orig = kt.dv_exc if dv0 > kt.dv_thr else kt.dv_thr
        cap_per_leg.append(cap_orig - safety_margin)
    times, tofs, mk = joint_polish(kt, perm, times0, tofs0, cap_per_leg,
                                    maxiter=maxiter)
    x_new = times + tofs + [float(p) for p in perm]
    f_new = kt.fitness(x_new)
    feas_new = kt.is_feasible(f_new)
    print(f"Polished: mk={f_new[0]:.4f}, fitness={list(f_new)}, "
          f"feas={feas_new}", flush=True)
    info = {"problem": problem, "n": n,
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
    mi = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print(json.dumps(main(maxiter=mi), indent=2))
