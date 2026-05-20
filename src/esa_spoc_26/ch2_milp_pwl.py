"""Ch2 KTTSP — MILP formulation (Phase 1: discrete-window MILP via HiGHS).

The "PWL" version would interpolate between discrete (td, tof, Δv)
points; that's a major build. Phase 1 just builds the MILP equivalent
of the v3 multi-window CP-SAT (E-021), with HiGHS solver. CP-SAT
returned UNKNOWN on the v3 dense windows (18 651 windows) at 600s; a
MILP solver may have a different LP relaxation profile and could find
feasible solutions where CP-SAT couldn't.

Variables:
  x_{i,j}        ∈ {0,1}  arc used
  y_{i,j,k}      ∈ {0,1}  window k of arc (i,j) selected
  T_v            ∈ [0, M] arrival time at v
  s_v            ∈ {0,1}  v is start
  e_v            ∈ {0,1}  v is end
  u_v            ∈ [1, n] MTZ sub-tour-elimination var

Constraints:
  - Flow: Σ_j x_{i,j} + e_i = 1 (one out or end); Σ_i x_{i,j} + s_j = 1
  - One start, one end: Σ s_v = 1, Σ e_v = 1
  - Window selection: Σ_k y_{i,j,k} = x_{i,j}
  - Chronology: T_j = td_k + tof_k if y_{i,j,k}=1 (big-M)
                T_i ≤ td_k if y_{i,j,k}=1
  - Start time: T_v ≤ M(1 - s_v) → T_v = 0 if s_v
  - Exception: Σ y_{i,j,k} [dv > 100] ≤ 5
  - MTZ subtour: u_i - u_j + n x_{i,j} ≤ n - 1
  - Horizon: T_v ≤ max_time
Objective: min Σ x_{i,j} td_{i,j} -- wait, makespan = max T_v.
  We need mk = max T_v, then min mk.
  Equivalent: introduce mk, T_v ≤ mk ∀ v, min mk.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import highspy
import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def _build_warmstart(kt, perm, times, tofs, dvs, arc_windows, n_arcs,
                     x_idx, y_idx, T_idx, s_idx, e_idx, u_idx,
                     mk_idx, n_vars):
    """Construct a HiGHS warmstart from a known feasible perm + window
    chosen per arc. Returns (col_values, valid)."""
    n = len(perm)
    col = [0.0] * n_vars
    # Set s, e
    col[s_idx[perm[0]]] = 1.0
    col[e_idx[perm[-1]]] = 1.0
    # Set u (MTZ): u_v = position in perm + 1
    for pos, v in enumerate(perm):
        col[u_idx[v]] = float(pos + 1)
    # Set T_v
    col[T_idx[perm[0]]] = 0.0
    for k in range(n - 1):
        i, j = perm[k], perm[k + 1]
        td = times[k]
        tof = tofs[k]
        arr = td + tof
        col[T_idx[j]] = arr
        # Find the closest window to (td, tof) for this arc
        if (i, j) not in arc_windows:
            return None, False
        ws = arc_windows[(i, j)]
        # Find window matching td/tof closely
        best_k = None
        best_dist = float("inf")
        for w in ws:
            k_w, _dv_w, td_w, tof_w = w
            dist = abs(td_w - td) + abs(tof_w - tof)
            if dist < best_dist:
                best_dist = dist
                best_k = k_w
        if best_k is None:
            return None, False
        # Set x_{i,j} = 1, y_{i,j,k} = 1
        col[x_idx[(i, j)]] = 1.0
        col[y_idx[(i, j, best_k)]] = 1.0
    col[mk_idx] = max(col[T_idx[v]] for v in range(n))
    return col, True


def build_and_solve(inst, problem="small",
                    npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
                    out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
                    warm_start_path=None,
                    max_s=600.0):
    """Phase 1 MILP: discrete-window selection with chronology + exception
    budget + MTZ subtour elimination. Built and solved via HiGHS."""
    kt = KTTSP(inst)
    n = kt.n
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]
    M_LARGE = kt.max_time + 10.0   # big-M

    # Build list of windows for each arc
    arcs = []  # list of (i, j) with at least 1 window
    arc_windows = {}  # (i, j) -> list of (k, dv, td, tof)
    for i in range(n):
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            ws = []
            for k in range(int(counts[i, j])):
                dv, td, tof = W[i, j, k]
                if not np.isfinite(dv):
                    continue
                if td + tof > kt.max_time + 1e-6:
                    continue
                ws.append((k, float(dv), float(td), float(tof)))
            if ws:
                arcs.append((i, j))
                arc_windows[(i, j)] = ws
    n_arcs = len(arcs)
    n_windows = sum(len(v) for v in arc_windows.values())
    print(f"Model: n={n}, arcs={n_arcs}, windows={n_windows}", flush=True)

    # Initialise HiGHS LP
    h = highspy.Highs()
    h.silent()

    # Variable index helpers
    # Order of variables in HiGHS:
    # 1. x_{i,j} for each arc (n_arcs vars)
    # 2. y_{i,j,k} for each window (n_windows vars)
    # 3. T_v for each node (n vars)
    # 4. s_v, e_v for each node (2n vars)
    # 5. u_v for MTZ (n vars)
    # 6. mk for makespan (1 var)
    x_idx = {a: i for i, a in enumerate(arcs)}
    y_idx = {}
    cur = n_arcs
    for a in arcs:
        for w in arc_windows[a]:
            k = w[0]
            y_idx[(a[0], a[1], k)] = cur
            cur += 1
    T_idx = {v: cur + v for v in range(n)}
    cur += n
    s_idx = {v: cur + v for v in range(n)}
    cur += n
    e_idx = {v: cur + v for v in range(n)}
    cur += n
    u_idx = {v: cur + v for v in range(n)}
    cur += n
    mk_idx = cur
    cur += 1
    n_vars = cur
    print(f"Variables: x={n_arcs}, y={n_windows}, T={n}, s={n}, e={n}, "
          f"u={n}, mk=1 → total {n_vars}", flush=True)

    # Add variables
    # x_{i,j} binary
    for _ in arcs:
        h.addVar(0.0, 1.0)
    # y_{i,j,k} binary
    for _ in range(n_windows):
        h.addVar(0.0, 1.0)
    # T_v continuous [0, max_time]
    for _ in range(n):
        h.addVar(0.0, kt.max_time)
    # s_v, e_v binary
    for _ in range(n):
        h.addVar(0.0, 1.0)
    for _ in range(n):
        h.addVar(0.0, 1.0)
    # u_v continuous [1, n]
    for _ in range(n):
        h.addVar(0.0, float(n))
    # mk
    h.addVar(0.0, kt.max_time)

    # Set integrality
    for a in arcs:
        h.changeColIntegrality(x_idx[a], highspy.HighsVarType.kInteger)
    for _key, idx in y_idx.items():
        h.changeColIntegrality(idx, highspy.HighsVarType.kInteger)
    for v in range(n):
        h.changeColIntegrality(s_idx[v], highspy.HighsVarType.kInteger)
        h.changeColIntegrality(e_idx[v], highspy.HighsVarType.kInteger)

    # Objective: min mk
    h.changeColCost(mk_idx, 1.0)

    # Add constraints (HiGHS row-style)
    # Helper: add row sum(coefs_i * x_i) <= ub (or >= lb)
    def add_row(rows, lower=-highspy.kHighsInf,
                upper=highspy.kHighsInf):
        # rows = [(var_idx, coef), ...]
        idxs = np.array([r[0] for r in rows], dtype=np.int32)
        vals = np.array([r[1] for r in rows], dtype=np.float64)
        h.addRow(lower, upper, len(rows), idxs, vals)

    # Flow constraints:
    # For each v: Σ_j x_{v,j} + e_v = 1 (one out-arc or end)
    # For each v: Σ_i x_{i,v} + s_v = 1 (one in-arc or start)
    for v in range(n):
        out_rows = [(x_idx[a], 1.0) for a in arcs if a[0] == v]
        out_rows.append((e_idx[v], 1.0))
        add_row(out_rows, lower=1.0, upper=1.0)
        in_rows = [(x_idx[a], 1.0) for a in arcs if a[1] == v]
        in_rows.append((s_idx[v], 1.0))
        add_row(in_rows, lower=1.0, upper=1.0)

    # Σ s_v = 1, Σ e_v = 1
    add_row([(s_idx[v], 1.0) for v in range(n)], lower=1.0, upper=1.0)
    add_row([(e_idx[v], 1.0) for v in range(n)], lower=1.0, upper=1.0)

    # Window selection: Σ_k y_{i,j,k} = x_{i,j}
    for a in arcs:
        i, j = a
        rows = [(y_idx[(i, j, w[0])], 1.0) for w in arc_windows[a]]
        rows.append((x_idx[a], -1.0))
        add_row(rows, lower=0.0, upper=0.0)

    # Chronology: T_j = td_k + tof_k * y_{i,j,k}  via big-M
    # T_j - (td_k + tof_k) + M(1 - y_{i,j,k}) >= 0  → T_j >= td+tof when y=1
    # T_j - (td_k + tof_k) - M(1 - y_{i,j,k}) <= 0  → T_j <= td+tof when y=1
    # T_i - td_k - M(1 - y_{i,j,k}) <= 0  → T_i <= td when y=1
    for a in arcs:
        i, j = a
        for w in arc_windows[a]:
            k_idx, dv_k, td_k, tof_k = w
            yk = y_idx[(i, j, k_idx)]
            arr_k = td_k + tof_k
            # T_j - arr_k * y_k - (arrival_when_not_used) — use big-M
            # T_j + M*y_k >= arr_k + M*y_k -- no, let me write directly:
            # T_j - arr_k >= -M(1 - y_k) ⟹ T_j - arr_k + M y_k >= -M + M y_k ...
            # Simpler: T_j >= arr_k - M(1 - y_k) → T_j + M y_k >= arr_k - M + M y_k
            # which is: T_j - arr_k + M y_k >= -M + M y_k → T_j - arr_k >= -M
            # That's always true. Wrong formulation. Use:
            # If y_k = 1, then T_j = arr_k. Two-sided big-M:
            # T_j - arr_k <= M(1 - y_k)
            # arr_k - T_j <= M(1 - y_k)
            # which becomes: T_j - M(1 - y_k) <= arr_k  AND  T_j + M(1 - y_k) >= arr_k
            # Rewriting in canonical:
            # T_j + M y_k <= arr_k + M
            # T_j - M y_k >= arr_k - M
            add_row([(T_idx[j], 1.0), (yk, M_LARGE)],
                    upper=arr_k + M_LARGE)
            add_row([(T_idx[j], 1.0), (yk, -M_LARGE)],
                    lower=arr_k - M_LARGE)
            # T_i <= td_k + M(1 - y_k) → T_i + M y_k <= td_k + M
            add_row([(T_idx[i], 1.0), (yk, M_LARGE)],
                    upper=td_k + M_LARGE)

    # Start time: T_v <= M(1 - s_v) → T_v + M s_v <= M
    for v in range(n):
        add_row([(T_idx[v], 1.0), (s_idx[v], M_LARGE)],
                upper=M_LARGE)

    # Exception count: Σ y_{i,j,k} [dv > 100] <= n_exc
    exc_rows = []
    for a in arcs:
        i, j = a
        for w in arc_windows[a]:
            k_idx, dv_k, _, _ = w
            if dv_k > kt.dv_thr:
                exc_rows.append((y_idx[(i, j, k_idx)], 1.0))
    if exc_rows:
        add_row(exc_rows, upper=float(kt.n_exc))

    # MTZ subtour elimination: u_i - u_j + n x_{i,j} <= n - 1 for i != j
    # (when x_{i,j}=1: u_j >= u_i + 1; when x=0: trivial)
    for a in arcs:
        i, j = a
        add_row([(u_idx[i], 1.0), (u_idx[j], -1.0),
                 (x_idx[a], float(n))], upper=float(n - 1))

    # mk constraint: T_v <= mk
    for v in range(n):
        add_row([(T_idx[v], 1.0), (mk_idx, -1.0)], upper=0.0)

    # Solver options
    h.setOptionValue("time_limit", float(max_s))
    h.setOptionValue("mip_rel_gap", 0.01)

    # Optional warm-start from a feasible solution file
    if warm_start_path is not None:
        with open(warm_start_path) as fh:
            ws_data = json.load(fh)
        ws_x = ws_data[0]["decisionVector"]
        ws_n = n
        ws_times = ws_x[:ws_n - 1]
        ws_tofs = ws_x[ws_n - 1:2 * ws_n - 2]
        ws_perm = [round(v) for v in ws_x[2 * ws_n - 2:]]
        ws_dvs = []
        for k in range(ws_n - 1):
            ws_dvs.append(kt.compute_transfer(ws_perm[k], ws_perm[k + 1],
                                              ws_times[k], ws_tofs[k]))
        col, ok = _build_warmstart(
            kt, ws_perm, ws_times, ws_tofs, ws_dvs, arc_windows,
            n_arcs, x_idx, y_idx, T_idx, s_idx, e_idx, u_idx, mk_idx,
            n_vars)
        if ok:
            print(f"Warm-start from {warm_start_path} (mk={col[mk_idx]:.3f})",
                  flush=True)
            sol_obj = highspy.HighsSolution()
            sol_obj.col_value = col
            h.setSolution(sol_obj)
        else:
            print("Warm-start construction FAILED", flush=True)

    print("Solving...", flush=True)
    t0 = time.time()
    h.run()
    wall = time.time() - t0
    status = h.getModelStatus()
    print(f"Status: {status}, wall={wall:.1f}s", flush=True)
    sol = h.getSolution()
    info_status = h.getInfo()
    obj_val = (info_status.objective_function_value
               if hasattr(info_status, "objective_function_value")
               else None)
    info = {"problem": problem, "n": n, "n_arcs": n_arcs,
            "n_windows": n_windows, "wall_s": round(wall, 1),
            "status": str(status), "obj": obj_val,
            "rank3_small_d": 111.76}
    if status == highspy.HighsModelStatus.kOptimal or \
       status == highspy.HighsModelStatus.kTimeLimit:
        # Recover solution
        x_vals = {a: sol.col_value[x_idx[a]] for a in arcs}
        y_vals = {(i, j, k): sol.col_value[idx]
                  for (i, j, k), idx in y_idx.items()}
        T_vals = [sol.col_value[T_idx[v]] for v in range(n)]
        info["mk"] = float(max(T_vals))
        # Decode perm via x_{i,j}>=0.5
        nxt = {a[0]: a[1] for a in arcs if x_vals[a] >= 0.5}
        start = next((v for v in range(n)
                      if sol.col_value[s_idx[v]] >= 0.5), None)
        if start is not None:
            perm = [start]
            while len(perm) < n and perm[-1] in nxt:
                perm.append(nxt[perm[-1]])
            info["perm_recovered_len"] = len(perm)
            if len(perm) == n:
                # Build decision vector
                times = []
                tofs = []
                for k in range(n - 1):
                    i, j = perm[k], perm[k + 1]
                    # Find which window k was chosen
                    chosen = None
                    for w in arc_windows.get((i, j), []):
                        if y_vals.get((i, j, w[0]), 0) >= 0.5:
                            chosen = w
                            break
                    if chosen is None:
                        break
                    _, _, td, tof = chosen
                    times.append(td)
                    tofs.append(tof)
                if len(times) == n - 1:
                    x_dec = times + tofs + [float(p) for p in perm]
                    f = kt.fitness(x_dec)
                    feas = kt.is_feasible(f)
                    info["fitness"] = list(f)
                    info["feasible"] = feas
                    if feas and f[0] < 142.99:
                        p = Path(out) / f"{problem}.json"
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(json.dumps([{"decisionVector":
                                                  list(x_dec),
                                                  "problem": problem,
                                                  "challenge": CHALLENGE}]))
                        info["replaced_banked"] = True
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    ms = float(sys.argv[1]) if len(sys.argv) > 1 else 600.0
    ws_path = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(build_and_solve(inst, max_s=ms,
                                     warm_start_path=ws_path), indent=2))
