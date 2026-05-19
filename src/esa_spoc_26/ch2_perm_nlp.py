"""Ch2 KTTSP — permutation-from-CP-SAT + chronological NLP refinement.

Builds on the static-graph CP-SAT diagnostic (min-Σmin-tof = 73 d):
1. CP-SAT picks a Hamiltonian path with `min_tof(i,j)` per arc and
   ≤5 exceptions (free of chronology).
2. The recovered permutation is fed into a chronological NLP chain:
   T_0 = 0; for each leg (π[i], π[i+1]), solve_leg_nlp finds (td*, tof*)
   minimising Δv with td* ≥ T_prev.
3. If the chain is feasible (all Δv ≤ 600, ≤5 exceptions, ΣTOF ≤ horizon),
   bank the artifact.

This is the T-008 final approach in its simplest constructive form.
LNS over permutation will be the next iteration.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_nlp_greedy import solve_leg_nlp

SCALE = 1000


def static_perm_cpsat(
    npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
    n=49, max_s=120.0, max_exc=5,
):
    """CP-SAT static-graph min-Σmin-tof Hamiltonian path."""
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]
    m = cp_model.CpModel()
    depot = n
    arcs = []
    exc_lits = []
    min_tof_q = {}
    edge_used = {}
    for i in range(n):
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            dvs = W[i, j, :int(counts[i, j]), 0]
            tofs = W[i, j, :int(counts[i, j]), 2]
            ok = dvs <= 600.0
            if not ok.any():
                continue
            x = m.NewBoolVar(f"x{i}_{j}")
            edge_used[(i, j)] = x
            arcs.append((i, j, x))
            min_tof_q[(i, j)] = round(float(tofs[ok].min()) * SCALE)
            if float(dvs.min()) > 100.0:
                exc_lits.append(x)
    for v in range(n):
        arcs.append((depot, v, m.NewBoolVar(f"s{v}")))
        arcs.append((v, depot, m.NewBoolVar(f"e{v}")))
    m.AddCircuit(arcs)
    m.Add(sum(exc_lits) <= max_exc)
    total = m.NewIntVar(0, 200_000_000, "total")
    m.Add(total == sum(x * min_tof_q[(i, j)]
                       for (i, j), x in edge_used.items()))
    m.Minimize(total)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(max_s)
    s.parameters.num_workers = 4
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, st
    nxt = {i: j for (i, j), x in edge_used.items() if s.Value(x)}
    start = None
    for t, h, c in arcs:
        if t == depot and s.Value(c):
            start = h
            break
    order = [start]
    while len(order) < n and order[-1] in nxt:
        order.append(nxt[order[-1]])
    return order, st


def chronological_nlp(kt, perm, verbose=False, arr_weight=0.5):
    """Refine a permutation via chronological NLP per-leg.
    Each leg's NLP minimises (arrival_time + Δv/arr_weight) under
    chronology + tight per-leg budget = (max_time - t_ready) / legs_left.
    Returns (decision_vector, fitness, feasible, diag) tuple."""
    n = kt.n
    if len(perm) != n or len(set(perm)) != n:
        return None, None, False, {"err": "bad perm"}
    t = 0.0
    times, tofs = [], []
    dvs = []
    exc = 0
    for i in range(n - 1):
        legs_left = n - 1 - i
        # Per-leg time budget: stay within fair share + slack
        fair = (kt.max_time - t) / max(legs_left, 1)
        t_budget = min(kt.max_time, t + fair * 4.0)
        # If exception budget gone, force dv ≤ dv_thr
        dv_cap = kt.dv_thr if exc >= kt.n_exc else kt.dv_exc
        r = solve_leg_nlp(kt, perm[i], perm[i + 1], t,
                          t_budget=t_budget, dv_cap=dv_cap,
                          arr_weight=arr_weight)
        if r is None:
            if verbose:
                print(f"  leg {i}: ({perm[i]}→{perm[i+1]}) at t_ready={t:.2f} NLP NONE",
                      flush=True)
            return None, None, False, {"err": "leg_none", "leg": i,
                                       "t_ready": t,
                                       "i_j": (int(perm[i]), int(perm[i + 1])),
                                       "dvs": dvs}
        dv, td, tof = r
        is_exc = dv > kt.dv_thr
        if is_exc and exc >= kt.n_exc:
            if verbose:
                print(f"  leg {i}: dv={dv:.1f} would exceed exc budget",
                      flush=True)
            return None, None, False, {"err": "exc_budget", "leg": i,
                                       "t_ready": t,
                                       "dv": dv,
                                       "dvs": dvs}
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = td + tof
        if t > kt.max_time + 1e-6:
            if verbose:
                print(f"  leg {i}: makespan {t:.1f} > max_time", flush=True)
            return None, None, False, {"err": "horizon", "leg": i,
                                       "t": t, "dvs": dvs}
    x = times + tofs + [float(o) for o in perm]
    f = kt.fitness(x)
    return x, f, kt.is_feasible(f), {"dvs": dvs, "max_dv": max(dvs)}


def solve(inst, problem="small",
          npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
          out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
          cpsat_s=120.0):
    kt = KTTSP(inst)
    t0 = time.time()
    perm, st = static_perm_cpsat(npz_w=npz_w, n=kt.n, max_s=cpsat_s,
                                  max_exc=kt.n_exc)
    cp_s = time.time() - t0
    if perm is None:
        return {"problem": problem, "feasible": False,
                "cpsat_status": st, "cpsat_s": round(cp_s, 1)}
    t1 = time.time()
    x, f, feas, diag = chronological_nlp(kt, perm, verbose=True)
    nlp_s = time.time() - t1
    if x is None:
        return {"problem": problem, "n": kt.n,
                "perm": [int(p) for p in perm],
                "cpsat_s": round(cp_s, 1),
                "feasible": False, "nlp_s": round(nlp_s, 1),
                "note": "chronological NLP failed", "diag": diag}
    res = {"problem": problem, "n": kt.n,
           "perm": [int(p) for p in perm],
           "cpsat_s": round(cp_s, 1), "nlp_s": round(nlp_s, 1),
           "makespan_d": round(f[0], 3), "perm_c": f[1],
           "dv_c": f[2], "time_c": f[3], "exc_c": f[4],
           "feasible": feas, "rank3_small_d": 111.76}
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
    cs = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    print(json.dumps(solve(inst, cpsat_s=cs), indent=2))
