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


def chronological_nlp(kt, perm):
    """Refine a permutation via chronological NLP per-leg.
    Returns (decision_vector, fitness, feasible) or (None, None, False)."""
    n = kt.n
    if len(perm) != n or len(set(perm)) != n:
        return None, None, False
    t = 0.0
    times, tofs = [], []
    dvs = []
    exc = 0
    for i in range(n - 1):
        r = solve_leg_nlp(kt, perm[i], perm[i + 1], t)
        if r is None:
            return None, None, False
        dv, td, tof = r
        is_exc = dv > kt.dv_thr
        if is_exc and exc >= kt.n_exc:
            # try restricting tof to find ≤thr solution? (skip for now)
            return None, None, False
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = td + tof
        if t > kt.max_time + 1e-6:
            return None, None, False
    x = times + tofs + [float(o) for o in perm]
    f = kt.fitness(x)
    return x, f, kt.is_feasible(f)


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
    x, f, feas = chronological_nlp(kt, perm)
    nlp_s = time.time() - t1
    if x is None:
        return {"problem": problem, "n": kt.n,
                "perm": [int(p) for p in perm],
                "cpsat_s": round(cp_s, 1),
                "feasible": False, "nlp_s": round(nlp_s, 1),
                "note": "chronological NLP failed"}
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
