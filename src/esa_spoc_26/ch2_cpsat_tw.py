"""Ch2 KTTSP — TIME-WINDOWED CP-SAT (E-018 heavy-compute target prototype).

E-018 showed: the static CP-SAT model is solved optimally but the
chosen path's edges' cheap windows (the precomputed TD per pair) are
*scattered in absolute time* and cannot be chronologically chained.
This model adds **time variables** per tomato + chronological
constraints per used arc:

  T[i] ≤ TD[i,j]  AND  T[j] = TD[i,j] + TF[i,j]   if arc (i,j) is used

So each used edge MUST be reachable at its precomputed-cheap window.
Single-window-per-edge proof-of-concept; if feasible → multi-window
per pair is the heavy-compute scaling target.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

SCALE = 1000  # millidays — quantises [0, 200 d] into [0, 200000]


def solve_tw(inst, problem="small",
             npz="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
             out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
             max_s=180.0):
    kt = KTTSP(inst)
    n = kt.n
    Z = np.load(npz)
    DV, TD, TF = Z["dv"], Z["td"], Z["tf"]

    m = cp_model.CpModel()
    HORIZ = round(kt.max_time * SCALE)
    T = [m.NewIntVar(0, HORIZ, f"T{v}") for v in range(n)]
    depot = n
    arcs = []
    exc_lits = []
    lits = {}
    starts = []
    for v in range(n):
        s = m.NewBoolVar(f"s{v}")
        e = m.NewBoolVar(f"e{v}")
        arcs.append((depot, v, s))
        arcs.append((v, depot, e))
        starts.append(s)
        m.Add(T[v] == 0).OnlyEnforceIf(s)  # start: arrive at time 0
    for i in range(n):
        for j in range(n):
            if i == j or not np.isfinite(DV[i, j]) or DV[i, j] > 600.0:
                continue
            x = m.NewBoolVar(f"x{i}_{j}")
            arcs.append((i, j, x))
            lits[(i, j)] = x
            td_q = round(float(TD[i, j]) * SCALE)
            tf_q = round(float(TF[i, j]) * SCALE)
            if td_q + tf_q > HORIZ:
                m.Add(x == 0)  # window past horizon — forbid
                continue
            m.Add(T[i] <= td_q).OnlyEnforceIf(x)
            m.Add(T[j] == td_q + tf_q).OnlyEnforceIf(x)
            if DV[i, j] > 100.0:
                exc_lits.append(x)
    m.AddCircuit(arcs)
    m.Add(sum(exc_lits) <= kt.n_exc)
    mk = m.NewIntVar(0, HORIZ, "mk")
    m.AddMaxEquality(mk, T)
    m.Minimize(mk)

    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(max_s)
    s.parameters.num_workers = 4
    st = s.Solve(m)
    status_name = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
                   cp_model.INFEASIBLE: "INFEASIBLE",
                   cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"problem": problem, "feasible": False,
                "tw_cpsat_status": status_name, "n": n}

    # recover order
    nxt = {i: j for (i, j), v in lits.items() if s.Value(v)}
    start = next(h for t, h, c in arcs if t == depot and s.Value(c))
    order = [start]
    while len(order) < n and order[-1] in nxt:
        order.append(nxt[order[-1]])
    if len(order) != n or len(set(order)) != n:
        return {"problem": problem, "feasible": False,
                "tw_cpsat_status": status_name,
                "note": f"path recovery incomplete ({len(order)})"}

    # reconstruct timing from chosen arcs (CP-SAT-consistent)
    times, tofs = [], []
    for k in range(n - 1):
        i, j = order[k], order[k + 1]
        times.append(float(TD[i, j]))
        tofs.append(float(TF[i, j]))
    x = times + tofs + [float(o) for o in order]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    res = {"problem": problem, "n": n, "tw_cpsat_status": status_name,
           "makespan_d": round(f[0], 3), "perm_c": f[1], "dv_c": f[2],
           "time_c": f[3], "exc_c": f[4], "feasible": feas,
           "rank3_small_d": 111.76, "cp_mk_obj_d": s.ObjectiveValue() / SCALE}
    if feas:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": x, "problem": problem,
                                  "challenge": CHALLENGE}]))
        res["artifact"] = str(p)
    return res


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
    print(json.dumps(solve_tw(inst, max_s=ms), indent=2))
