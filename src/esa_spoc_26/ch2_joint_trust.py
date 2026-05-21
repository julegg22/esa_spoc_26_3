"""Ch2 KTTSP — joint NLP with scipy trust-constr (interior-point).

SLSQP returned mk=142.3873 INFEAS from one jittered start, signalling
a 0.5d improvement basin exists nearby but SLSQP's SQP can't track
the nonlinear Δv constraint strictly. trust-constr uses interior-
point + barrier on inequality constraints — much stricter
feasibility tracking.

Multi-start from a few specific seeds: banked + start-7 (warmstart
the 142.3873 infeas region with a tighter safety margin).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, NonlinearConstraint

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def trust_polish(kt, perm, times0, tofs0, cap_per_leg,
                 maxiter=200, verbose=True):
    """trust-constr joint optimisation. Same objective + chronology +
    bounds, but Δv as NonlinearConstraint to leverage IP barriers."""
    n_legs = len(perm) - 1
    x0 = np.array(list(times0) + list(tofs0))

    def obj(x):
        return x[n_legs - 1] + x[2 * n_legs - 1]

    def obj_grad(x):
        g = np.zeros_like(x)
        g[n_legs - 1] = 1.0
        g[2 * n_legs - 1] = 1.0
        return g
    # Linear constraints: chronology + max_time + first-leg
    A = np.zeros((2 * n_legs, 2 * n_legs))
    lb = np.full(2 * n_legs, -np.inf)
    ub = np.full(2 * n_legs, np.inf)
    # Chronology rows k=0..n_legs-2: x[k+1] - x[k] - x[n_legs+k] >= 0
    for k in range(n_legs - 1):
        A[k, k + 1] = 1.0
        A[k, k] = -1.0
        A[k, n_legs + k] = -1.0
        lb[k] = 0.0
    # Max-time rows k=0..n_legs-1: x[k] + x[n_legs+k] <= max_time
    for k in range(n_legs):
        A[n_legs - 1 + k, k] = 1.0
        A[n_legs - 1 + k, n_legs + k] = 1.0
        ub[n_legs - 1 + k] = kt.max_time
    linear = (A, lb, ub)
    # Bounds
    tof_min = max(kt.min_tof, 0.05)
    bounds = [(0.0, kt.max_time)] * n_legs + \
             [(tof_min, 40.0)] * n_legs
    # Nonlinear: dv per leg (vector-valued)

    def dv_vec(x):
        out = np.zeros(n_legs)
        for k in range(n_legs):
            out[k] = kt.compute_transfer(perm[k], perm[k + 1],
                                          float(x[k]),
                                          float(x[n_legs + k]))
        return out
    nlc = NonlinearConstraint(dv_vec, lb=-np.inf,
                              ub=np.array(cap_per_leg))
    # Linear constraint via LinearConstraint
    from scipy.optimize import LinearConstraint
    lc = LinearConstraint(A, lb=lb, ub=ub)
    t0 = time.time()
    if verbose:
        print(f"trust-constr: {2*n_legs} vars, {n_legs} dv + "
              f"{2*n_legs} linear cons, warm-start "
              f"mk={x0[n_legs-1]+x0[2*n_legs-1]:.4f}",
              flush=True)
    try:
        r = minimize(obj, x0, jac=obj_grad, method="trust-constr",
                     bounds=bounds, constraints=[lc, nlc],
                     options={"maxiter": maxiter, "verbose": 0,
                              "gtol": 1e-7, "xtol": 1e-8})
    except Exception as e:
        print(f"  trust-constr failed: {e}", flush=True)
        return list(times0), list(tofs0), times0[-1] + tofs0[-1]
    wall = time.time() - t0
    if verbose:
        print(f"  trust-constr done: status={r.status}, "
              f"nit={r.nit}, fun={r.fun:.4f}, wall={wall:.1f}s",
              flush=True)
    times = list(r.x[:n_legs])
    tofs = list(r.x[n_legs:])
    return times, tofs, times[-1] + tofs[-1]


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", maxiter=400, safety_margin=5e-4):
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
        cap_orig = kt.dv_exc if dv0 > kt.dv_thr else kt.dv_thr
        cap_per_leg.append(cap_orig - safety_margin)
    times, tofs, mk = trust_polish(kt, perm, times0, tofs0,
                                    cap_per_leg, maxiter=maxiter)
    x_new = times + tofs + [float(p) for p in perm]
    f_new = kt.fitness(x_new)
    feas_new = kt.is_feasible(f_new)
    print(f"Polished: mk={f_new[0]:.4f}, fitness={list(f_new)}, "
          f"feas={feas_new}", flush=True)
    info = {"problem": problem, "n": n,
            "safety_margin": safety_margin,
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
    mi = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    sm = float(sys.argv[2]) if len(sys.argv) > 2 else 5e-4
    print(json.dumps(main(maxiter=mi, safety_margin=sm), indent=2))
