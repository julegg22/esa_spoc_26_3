"""Ch2 KTTSP — MULTI-WINDOW CP-SAT (the heavy-compute target, T-008).

Each ordered pair (i,j) carries up to K precomputed cheap windows
(Δv_k, t_dep_k, tof_k) [windows_small.npz, O-008 found ~100 windows
per cheap pair → we sample K of them]. The model picks ONE window
per used edge, enforces chronology, ≤5 exceptions, minimises
makespan. With ~K-flexibility per cheap edge, the time-coupling
that broke E-018 should resolve.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

SCALE = 1000  # millidays


def solve_mw(inst, problem="small",
             npz_w="/home/julian/Projects/esa_spoc_26_3/windows_small.npz",
             out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
             max_s=600.0):
    kt = KTTSP(inst)
    n = kt.n
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]   # W[i,j,k] = (dv, td, tof)

    m = cp_model.CpModel()
    HORIZ = round(kt.max_time * SCALE)
    T = [m.NewIntVar(0, HORIZ, f"T{v}") for v in range(n)]
    depot = n
    arcs = []                   # for AddCircuit (uses x_{i,j} edge-flag)
    edge_used = {}              # (i,j) -> BoolVar x_{i,j}
    win_lits = {}               # (i,j,k) -> BoolVar y_{i,j,k}
    exc_lits = []
    for v in range(n):
        s = m.NewBoolVar(f"s{v}")
        e = m.NewBoolVar(f"e{v}")
        arcs.append((depot, v, s))
        arcs.append((v, depot, e))
        m.Add(T[v] == 0).OnlyEnforceIf(s)
    for i in range(n):
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            x_ij = m.NewBoolVar(f"x{i}_{j}")
            edge_used[(i, j)] = x_ij
            arcs.append((i, j, x_ij))
            ks = []
            for k in range(int(counts[i, j])):
                dv, td, tf = W[i, j, k]
                td_q = round(float(td) * SCALE)
                tf_q = round(float(tf) * SCALE)
                if td_q + tf_q > HORIZ or not np.isfinite(dv):
                    continue
                y = m.NewBoolVar(f"y{i}_{j}_{k}")
                win_lits[(i, j, k)] = y
                ks.append(y)
                m.Add(T[i] <= td_q).OnlyEnforceIf(y)
                m.Add(T[j] == td_q + tf_q).OnlyEnforceIf(y)
                if dv > 100.0:
                    exc_lits.append(y)
            if not ks:
                m.Add(x_ij == 0)
            else:
                m.Add(sum(ks) == x_ij)  # exactly one window if edge used
    m.AddCircuit(arcs)
    m.Add(sum(exc_lits) <= kt.n_exc)
    mk = m.NewIntVar(0, HORIZ, "mk")
    m.AddMaxEquality(mk, T)
    m.Minimize(mk)

    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(max_s)
    s.parameters.num_workers = 4
    st = s.Solve(m)
    status = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
              cp_model.INFEASIBLE: "INFEASIBLE",
              cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    info = {"problem": problem, "n": n, "mw_status": status,
            "n_edges": len(edge_used), "n_windows": len(win_lits)}
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {**info, "feasible": False}

    # recover order + chosen windows
    nxt = {i: j for (i, j), x in edge_used.items() if s.Value(x)}
    start = next(h for t, h, c in arcs if t == depot and s.Value(c))
    order = [start]
    while len(order) < n and order[-1] in nxt:
        order.append(nxt[order[-1]])
    if len(order) != n or len(set(order)) != n:
        return {**info, "feasible": False,
                "note": f"path recovery incomplete ({len(order)})"}
    chosen_td = []
    chosen_tf = []
    for k in range(n - 1):
        i, j = order[k], order[k + 1]
        for wk in range(int(counts[i, j])):
            if (i, j, wk) in win_lits and s.Value(win_lits[(i, j, wk)]):
                chosen_td.append(float(W[i, j, wk, 1]))
                chosen_tf.append(float(W[i, j, wk, 2]))
                break
    x = chosen_td + chosen_tf + [float(o) for o in order]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    info.update({"makespan_d": round(f[0], 3), "perm_c": f[1], "dv_c": f[2],
                 "time_c": f[3], "exc_c": f[4], "feasible": feas,
                 "rank3_small_d": 111.76,
                 "cp_mk_obj_d": s.ObjectiveValue() / SCALE})
    if feas:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": x, "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    print(json.dumps(solve_mw(inst, max_s=ms), indent=2))
