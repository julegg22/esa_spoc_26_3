"""Ch2 KTTSP — OR-Tools CP-SAT constrained-Hamiltonian-path solver.

E-014/T-006: constructive heuristics strand (feasibility is a global
property). This models Ch2 exactly: on the precomputed feasible-edge
graph (edges_small.npz: time-optimal Δv per ordered pair), pick a
Hamiltonian PATH using only ≤600 m/s edges, ≤5 of them in (100,600],
minimising a makespan proxy (Σ time-of-flight). The CP-SAT order is
then chronologically re-timed (per-leg windowed) and validated by the
official-mirror scorer before banking. Needs ortools (L-003).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def solve_cpsat(inst, problem="small",
                npz="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
                out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
                max_s=120.0):
    kt = KTTSP(inst)
    n = kt.n
    Z = np.load(npz)
    DV, TF = Z["dv"], Z["tf"]

    m = cp_model.CpModel()
    depot = n
    arcs, lits, exc_lits = [], {}, []
    for i in range(n):  # path via depot: depot→i (start), i→depot (end)
        s = m.NewBoolVar(f"s{i}")
        e = m.NewBoolVar(f"e{i}")
        arcs.append((depot, i, s))
        arcs.append((i, depot, e))
    for i in range(n):
        for j in range(n):
            if i == j or not np.isfinite(DV[i, j]) or DV[i, j] > 600.0:
                continue
            v = m.NewBoolVar(f"x{i}_{j}")
            arcs.append((i, j, v))
            lits[(i, j)] = v
            if DV[i, j] > 100.0:
                exc_lits.append(v)
    m.AddCircuit(arcs)
    m.Add(sum(exc_lits) <= kt.n_exc)
    # makespan proxy: total time-of-flight of used real edges
    m.Minimize(sum(round(float(TF[i, j]) * 1000) * v
                   for (i, j), v in lits.items()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(max_s)
    solver.parameters.num_workers = 8
    st = solver.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"problem": problem, "feasible": False,
                "note": f"CP-SAT no solution (status {st})"}

    # recover path order from chosen arcs
    nxt = {}
    start = None
    for (i, j), v in lits.items():
        if solver.Value(v):
            nxt[i] = j
    for t, h, c in arcs:
        if t == depot and solver.Value(c):
            start = h
    order = [start]
    while len(order) < n and order[-1] in nxt:
        order.append(nxt[order[-1]])
    if len(order) != n or len(set(order)) != n:
        return {"problem": problem, "feasible": False,
                "note": f"CP-SAT path recovery incomplete ({len(order)})"}

    # chronological re-timing — FULL HORIZON (E-015 fix): cheap windows
    # recur on the synodic-beat period; the prior 14-d window was the
    # bug, not the CP-SAT model. Reuse the verified ch2_lns full-horizon
    # decoder so the search spans [t_ready, max_time].
    import esa_spoc_26.ch2_lns as L
    L._KT = kt
    x, _, mk, n_exc, n_bad = L.decode(order)
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    res = {"problem": problem, "n": n, "makespan_d": f[0],
           "perm_c": f[1], "dv_c": f[2], "time_c": f[3], "exc_c": f[4],
           "feasible": feas, "rank3_small_d": 111.76,
           "cpsat_status": int(st), "retimed_exc": n_exc,
           "retimed_bad": n_bad, "decode_mk": round(mk, 3)}
    if feas:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": x, "problem": problem,
                                  "challenge": CHALLENGE}]))
        res["artifact"] = str(p)
    return res


if __name__ == "__main__":
    inst = (
        "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
    print(json.dumps(solve_cpsat(inst, max_s=ms), indent=2))
