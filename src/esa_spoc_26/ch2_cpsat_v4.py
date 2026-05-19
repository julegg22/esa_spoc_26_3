"""Ch2 KTTSP — CP-SAT v4: per-arc 3-way choice + Σtof ≤ horizon (T-008).

Each ordered arc (i, j) has up to 3 "modes":
  - short-cheap  : min tof window with Δv ≤ 100
  - long-cheap   : min Δv window (Δv ≤ 100) — gives a fallback tof
  - exception    : min tof window with 100 < Δv ≤ 600

Per used arc, exactly one mode chosen. Constraints:
  - AddCircuit for Ham-path on n nodes
  - sum of exception-mode chosen ≤ 5
  - sum of chosen-mode tofs ≤ max_time
Objective: minimise Σtof (= makespan if no waits).

This is the structural reformulation E-021 pointed to: capture the
short-tof-vs-cheap tradeoff per arc directly in the discrete model,
*before* worrying about chronology.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from ortools.sat.python import cp_model

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

SCALE = 1000


def per_arc_modes(W, counts, n, dv_thr=100.0, dv_exc=600.0):
    """For each arc (i,j) build up to 3 modes — returns dict
       (i,j) -> {'sc': (tof, dv), 'lc': (tof, dv), 'ex': (tof, dv)}
    Only modes that exist are present."""
    modes = {}
    for i in range(n):
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            dvs = W[i, j, :int(counts[i, j]), 0]
            tofs = W[i, j, :int(counts[i, j]), 2]
            tds = W[i, j, :int(counts[i, j]), 1]
            ok_cheap = dvs <= dv_thr
            ok_exc = (dvs > dv_thr) & (dvs <= dv_exc)
            m = {}
            if ok_cheap.any():
                # short-cheap: min tof among cheap
                idx = np.where(ok_cheap)[0]
                k_sc = idx[np.argmin(tofs[ok_cheap])]
                m['sc'] = (float(tofs[k_sc]), float(dvs[k_sc]),
                           float(tds[k_sc]))
                # long-cheap: min Δv among cheap (the safety/Δv-optimal)
                k_lc = idx[np.argmin(dvs[ok_cheap])]
                if k_lc != k_sc:
                    m['lc'] = (float(tofs[k_lc]), float(dvs[k_lc]),
                               float(tds[k_lc]))
            if ok_exc.any():
                idx = np.where(ok_exc)[0]
                k_ex = idx[np.argmin(tofs[ok_exc])]
                m['ex'] = (float(tofs[k_ex]), float(dvs[k_ex]),
                           float(tds[k_ex]))
            if m:
                modes[(i, j)] = m
    return modes


def solve_v4(inst, problem="small",
             npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
             out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
             max_s=300.0):
    kt = KTTSP(inst)
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]
    n = kt.n
    modes = per_arc_modes(W, counts, n, kt.dv_thr, kt.dv_exc)

    m = cp_model.CpModel()
    depot = n
    arcs = []
    edge_used = {}
    mode_lits = {}     # (i,j,'sc'/'lc'/'ex') -> BoolVar
    exc_lits = []
    tof_terms = []     # accumulate x_mode * tof_q
    for v in range(n):
        arcs.append((depot, v, m.NewBoolVar(f"s{v}")))
        arcs.append((v, depot, m.NewBoolVar(f"e{v}")))
    for (i, j), mods in modes.items():
        x = m.NewBoolVar(f"x{i}_{j}")
        edge_used[(i, j)] = x
        arcs.append((i, j, x))
        chosen = []
        for tag, (tof, _dv, _td) in mods.items():
            y = m.NewBoolVar(f"y{i}_{j}_{tag}")
            mode_lits[(i, j, tag)] = y
            chosen.append(y)
            tof_terms.append(y * round(tof * SCALE))
            if tag == 'ex':
                exc_lits.append(y)
        m.Add(sum(chosen) == x)   # exactly one mode if used
    m.AddCircuit(arcs)
    m.Add(sum(exc_lits) <= kt.n_exc)
    total = m.NewIntVar(0, round(kt.max_time * SCALE), "total")
    m.Add(total == sum(tof_terms))
    m.Minimize(total)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(max_s)
    s.parameters.num_workers = 4
    t0 = time.time()
    st = s.Solve(m)
    cp_s = time.time() - t0
    status = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE",
              cp_model.INFEASIBLE: "INFEASIBLE",
              cp_model.UNKNOWN: "UNKNOWN"}.get(st, str(st))
    info = {"problem": problem, "n": n, "v4_status": status,
            "cp_s": round(cp_s, 1), "n_modes": len(mode_lits),
            "n_arcs": len(edge_used)}
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {**info, "feasible": False}
    nxt = {i: j for (i, j), x in edge_used.items() if s.Value(x)}
    start = None
    for tt, h, c in arcs:
        if tt == depot and s.Value(c):
            start = h
            break
    perm = [start]
    while len(perm) < n and perm[-1] in nxt:
        perm.append(nxt[perm[-1]])
    if len(perm) != n:
        info["perm_recovery_len"] = len(perm)
        return {**info, "feasible": False}
    # Reconstruct legs from chosen modes (use precomputed td, tof per mode)
    times = []
    tofs = []
    dvs = []
    exc = 0
    t_chrono = 0.0
    chronology_violation = 0
    for k in range(n - 1):
        i, j = perm[k], perm[k + 1]
        chosen_tag = None
        for tag in ('sc', 'lc', 'ex'):
            lit = mode_lits.get((i, j, tag))
            if lit is not None and s.Value(lit):
                chosen_tag = tag
                break
        tof, dv, td = modes[(i, j)][chosen_tag]
        # If td < t_chrono we have a chronology issue; record but proceed
        if td < t_chrono - 1e-6:
            chronology_violation += 1
            td = t_chrono  # bump up (Δv check will see it)
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if dv > kt.dv_thr:
            exc += 1
        t_chrono = td + tof
    info.update({"cp_obj_d": s.ObjectiveValue() / SCALE,
                 "chronology_violations": chronology_violation,
                 "perm": [int(p) for p in perm]})
    x = times + tofs + [float(p) for p in perm]
    f = kt.fitness(x)
    info.update({"makespan_d": round(f[0], 3),
                 "perm_c": f[1], "dv_c": f[2], "time_c": f[3],
                 "exc_c": f[4], "feasible": kt.is_feasible(f),
                 "rank3_small_d": 111.76})
    if kt.is_feasible(f):
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": list(x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    print(json.dumps(solve_v4(inst, max_s=ms), indent=2))
