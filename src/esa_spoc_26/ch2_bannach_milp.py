"""Ch2 KTTSP — canonical time-expanded-network MILP per Bannach et al.
(IAC 2024) "On the Keplerian TSP and VRP: Benchmarks and Encoding
Techniques" — O-009.

Critical differences from `ch2_milp_pwl.py` (refuted by E-024):
- Vertices V = A × T (tomato × time grid point), NOT just A.
- Arcs E = E_C (coasting α→α at next t) ∪ E_T (transfer α→β at (t,t')).
- Constraints:
    1. Departure: each tomato α leaves at least once.
    2. Flow: at every (α, t), in-flow == out-flow (no half-arcs).
    3. Vehicle: starts at (α_s, t_0).
- NO MTZ subtour elimination (the flow + acyclicity of the time-
  expanded graph make MTZ unnecessary for our objective).
- Plain time-indexed encoding; Dynamic Discretization Discovery
  (DDD) is a future extension.

Adaptation for SpOC4 KTTSP:
- Objective: MIN makespan (not min Σ Δv as in Bannach).
- ≤ n_exc exception arcs (Δv > 100); all arcs satisfy Δv ≤ 600.
- Single start (any tomato), single end (any tomato).
- Use precomputed `windows2d_small.npz` (E-021's K=24 dense
  windows) as the source of transfer arcs.

The MILP this produces is the principled encoding the SpOC4 winners
likely use (with Gurobi). We solve with HiGHS — slower but
available.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import highspy
import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def _build_time_grid(max_time, dt):
    """Return time grid array [0, dt, 2dt, ..., t_max]."""
    n_t = round(max_time / dt) + 1
    return np.linspace(0.0, max_time, n_t)


def _snap_to_grid(t, grid):
    """Snap a continuous time t to the nearest grid index."""
    idx = round(t / (grid[1] - grid[0]))
    return max(0, min(len(grid) - 1, idx))


def build_arcs(kt, windows_npz, grid):
    """Build E_C (coasting) + E_T (transfer) arcs from the precomputed
    windows and a time grid. Snap window (td, td+tof) to grid points."""
    Z = np.load(windows_npz)
    W, counts = Z["W"], Z["counts"]
    n = kt.n
    n_t = len(grid)
    # Coasting arcs: ((α, t), (α, t+1)) for each α and each t < n_t-1
    coasts = []
    for a in range(n):
        for t_idx in range(n_t - 1):
            coasts.append((a, t_idx, a, t_idx + 1))
    # Transfer arcs from windows: ((α, snap(td)), (β, snap(td+tof)))
    transfers = []  # (α, t_idx, β, tp_idx, dv)
    for i in range(n):
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            for k in range(int(counts[i, j])):
                dv, td, tof = W[i, j, k]
                if not np.isfinite(dv) or dv > kt.dv_exc + 1e-6:
                    continue
                arr = td + tof
                if arr > kt.max_time + 1e-6:
                    continue
                # Snap td DOWN (floor) and arr UP (ceil) so short arcs
                # don't collapse to self-loops at coarse dt.
                step = grid[1] - grid[0]
                t_idx = max(0, min(len(grid) - 1, int(td / step)))
                tp_idx = min(len(grid) - 1,
                             int(np.ceil(arr / step)))
                if tp_idx <= t_idx:
                    tp_idx = t_idx + 1
                if tp_idx >= len(grid):
                    continue   # arc exceeds horizon
                transfers.append((i, t_idx, j, tp_idx, float(dv)))
    return coasts, transfers


def build_and_solve(inst, problem="small",
                    npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
                    out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
                    dt=2.0, max_s=600.0, drop_exception_budget=False):
    kt = KTTSP(inst)
    n = kt.n
    grid = _build_time_grid(kt.max_time, dt)
    n_t = len(grid)
    coasts, transfers = build_arcs(kt, npz_w, grid)
    n_coast = len(coasts)
    n_xfer = len(transfers)
    print(f"Time-expanded model: n={n}, n_t={n_t} (dt={dt}d)", flush=True)
    print(f"Arcs: coasting={n_coast}, transfer={n_xfer}", flush=True)

    h = highspy.Highs()
    h.silent()

    # Variable order:
    # 1. c_idx[(a, t)] for coasting arc (a, t)→(a, t+1)        — n_coast
    # 2. x_idx[(α, t, β, tp)] for transfer arc                  — n_xfer
    # 3. s_idx[α] = "α is start"                                — n
    # 4. e_idx[α] = "α is end"                                  — n
    # 5. visit_idx[α] = "α was visited" (derived)               — n
    # 6. exc_used: total exception arcs used (continuous, ≤ n_exc)
    # 7. mk: makespan (continuous)
    c_idx = {(a, t): i for i, (a, t, _a2, _tp) in enumerate(coasts)}
    x_idx = {}
    cur = n_coast
    for i, (a, t, b, tp, _dv) in enumerate(transfers):
        x_idx[(a, t, b, tp)] = cur + i
    cur += n_xfer
    s_idx = {a: cur + a for a in range(n)}
    cur += n
    e_idx = {a: cur + a for a in range(n)}
    cur += n
    mk_idx = cur
    cur += 1
    n_vars = cur

    # Add variables
    for _ in range(n_coast):
        h.addVar(0.0, 1.0)
    for _ in range(n_xfer):
        h.addVar(0.0, 1.0)
    for _ in range(n):
        h.addVar(0.0, 1.0)  # s
    for _ in range(n):
        h.addVar(0.0, 1.0)  # e
    h.addVar(0.0, kt.max_time)  # mk

    # Integrality
    for v in range(n_coast + n_xfer + 2 * n):
        h.changeColIntegrality(v, highspy.HighsVarType.kInteger)

    # Objective: minimise makespan
    h.changeColCost(mk_idx, 1.0)

    def add_row(rows, lower=-highspy.kHighsInf, upper=highspy.kHighsInf):
        idxs = np.array([r[0] for r in rows], dtype=np.int32)
        vals = np.array([r[1] for r in rows], dtype=np.float64)
        h.addRow(lower, upper, len(rows), idxs, vals)

    # --- Constraints ---
    # Departure (each tomato visited at least once = leaves at least once,
    # or is the END).
    # Σ over outgoing transfer arcs from any (α, t) + e[α] ≥ 1
    # Equivalent: spacecraft departs α (transfer-arc out) or ends at α.
    for a in range(n):
        rows = []
        for (aa, t, b, tp), idx in x_idx.items():
            if aa == a:
                rows.append((idx, 1.0))
        rows.append((e_idx[a], 1.0))
        if rows:
            add_row(rows, lower=1.0)

    # Flow at each (α, t): in_flow - out_flow = 0 unless start/end
    # in_flow = Σ over coasting in + Σ over transfer arcs to (α, t)
    # out_flow = Σ over coasting out + Σ over transfer arcs from (α, t)
    # Modified for start/end: in - out = -s[α] if t==0; +e[α] if visited
    # Simpler: in - out + s[α]·δ(t==0) - e[α]·δ(t-visited) = 0
    # We use the formulation: for each (α, t),
    #   inflow - outflow = (s[α] if t==0 else 0) - e[α]·(if last visit)
    # The cleanest version: spacecraft starts at (α_start, 0) and ends
    # at the latest visited point. Treat it as a "single unit" flowing
    # from start to end.
    #
    # For each (α, t) NOT the global source/sink, in = out:
    for a in range(n):
        for t in range(n_t):
            in_rows = []
            out_rows = []
            # Coasting in: from (a, t-1)
            if t > 0 and (a, t - 1) in c_idx:
                in_rows.append((c_idx[(a, t - 1)], 1.0))
            # Coasting out: to (a, t+1)
            if t < n_t - 1 and (a, t) in c_idx:
                out_rows.append((c_idx[(a, t)], 1.0))
            # Transfer in: arcs ending at (a, t)
            for (aa, tt, bb, tp), idx in x_idx.items():
                if bb == a and tp == t:
                    in_rows.append((idx, 1.0))
                if aa == a and tt == t:
                    out_rows.append((idx, 1.0))
            # Source: (a, 0) gets +1 if a is start
            # Sink: (a, t_last_visit) gets -1 if a is end at this t
            # Simplified: introduce per-(a, t) end indicator? Too complex.
            # Cleaner: for each a, exactly one "exit" point — either via
            # last coasting → (a, n_t-1) with e[a]=1 marking end, or via
            # transfer-out. Skipping per-time end markers; use endpoint
            # marker e[α] = 1 means α is FINAL and flow exits at some
            # (α, t_e). Since transfer arcs are sparse, we encode:
            #   Σ_t (in_flow[(a,t)] - out_flow[(a,t)]) =
            #        (-1 if s[a]=1) + (+1 if e[a]=1) + (0 else)
            # This is the per-α flow conservation, not per-(α, t).
            # ⇒ Use the AGGREGATED form below, drop per-(α, t).
            pass  # see aggregated flow constraints below

    # NOTE: per-α aggregated flow conservation is REDUNDANT with the
    # per-(α, t) constraints below (and would be wrong if including
    # coasting arcs, since those cancel out under α-aggregation).
    # We rely solely on per-(α, t) constraints, which together imply
    # the per-α aggregate.

    # Per-(α, t) conservation: inflow == outflow (for INTERIOR vertices)
    # but with relaxation for (α, 0) (start can have +1) and ENDS:
    # Σ_t (visit indicator) is implicit; cleaner to enforce strict
    # per-(α, t) flow == 0 EXCEPT for (α, 0) where outflow = +1 if s[α].
    for a in range(n):
        for t in range(n_t):
            rows = []
            # in
            if t > 0 and (a, t - 1) in c_idx:
                rows.append((c_idx[(a, t - 1)], 1.0))
            for (aa, tt, bb, tp), idx in x_idx.items():
                if bb == a and tp == t:
                    rows.append((idx, 1.0))
            # out (negated)
            if t < n_t - 1 and (a, t) in c_idx:
                rows.append((c_idx[(a, t)], -1.0))
            for (aa, tt, bb, tp), idx in x_idx.items():
                if aa == a and tt == t:
                    rows.append((idx, -1.0))
            # right-hand side
            # Flow at source (t=0): outflow = inflow + s[α]
            #   ⇒ in - out + s[α] = 0 — add s[α] with +1
            if t == 0:
                rows.append((s_idx[a], 1.0))
            # Flow at sink (t=n_t-1): inflow = outflow + e[α]
            #   ⇒ in - out - e[α] = 0 — add e[α] with -1
            if t == n_t - 1:
                rows.append((e_idx[a], -1.0))
            if rows:
                add_row(rows, lower=0.0, upper=0.0)

    # Exactly one start, exactly one end
    add_row([(s_idx[a], 1.0) for a in range(n)], lower=1.0, upper=1.0)
    add_row([(e_idx[a], 1.0) for a in range(n)], lower=1.0, upper=1.0)

    # Exception budget: Σ over transfer arcs with dv > dv_thr ≤ n_exc
    exc_rows = []
    for (aa, tt, bb, tp), idx in x_idx.items():
        # need to look up dv from transfers — store dv keyed by arc
        pass
    # Rebuild dv lookup
    dv_lookup = {}
    for i, (a, t, b, tp, dv) in enumerate(transfers):
        dv_lookup[(a, t, b, tp)] = dv
    for key, idx in x_idx.items():
        if dv_lookup.get(key, 0) > kt.dv_thr:
            exc_rows.append((idx, 1.0))
    if exc_rows and not drop_exception_budget:
        add_row(exc_rows, upper=float(kt.n_exc))

    # Makespan: mk ≥ t' * x_arc for every transfer arc (with big-M)
    # Equivalent: mk ≥ t_grid[tp] - M(1 - x_arc)
    # Linearised: mk + M·x_arc ≥ t_grid[tp] - M  (i.e., upper:M-t, lower:- inf)
    # Re-express: -mk - M·x_arc ≤ -t + M  ⇒  -mk - M·x_arc + M ≤ ...
    # Cleaner using "if x_arc=1 then mk ≥ t'" via:
    #   mk ≥ t_grid[tp] · x_arc  (linear, since x is binary and mk is continuous)
    # i.e., mk - t_grid[tp] · x_arc ≥ 0
    for (a, t, b, tp), idx in x_idx.items():
        add_row([(mk_idx, 1.0), (idx, -float(grid[tp]))],
                lower=0.0)

    # Solve
    h.setOptionValue("time_limit", float(max_s))
    h.setOptionValue("mip_rel_gap", 0.02)
    print(f"Vars: {n_vars}, solving with HiGHS time_limit={max_s}s...",
          flush=True)
    t0 = time.time()
    h.run()
    wall = time.time() - t0
    status = h.getModelStatus()
    info_status = h.getInfo()
    obj_val = (info_status.objective_function_value
               if hasattr(info_status, "objective_function_value")
               else None)
    print(f"Status: {status}, wall={wall:.1f}s, obj={obj_val}",
          flush=True)
    info = {"problem": problem, "n": n, "n_t": n_t, "dt": dt,
            "n_coast": n_coast, "n_xfer": n_xfer, "n_vars": n_vars,
            "wall_s": round(wall, 1),
            "status": str(status), "obj": obj_val,
            "rank3_small_d": 111.76}
    if status in (highspy.HighsModelStatus.kOptimal,
                  highspy.HighsModelStatus.kTimeLimit):
        sol = h.getSolution()
        # Recover used transfer arcs + sequence
        used_xfers = [(a, t, b, tp, dv_lookup[(a, t, b, tp)])
                      for (a, t, b, tp), idx in x_idx.items()
                      if sol.col_value[idx] >= 0.5]
        start_a = next((a for a in range(n)
                        if sol.col_value[s_idx[a]] >= 0.5), None)
        end_a = next((a for a in range(n)
                      if sol.col_value[e_idx[a]] >= 0.5), None)
        info.update({"n_used_xfers": len(used_xfers),
                     "start": start_a, "end": end_a,
                     "mk_var": sol.col_value[mk_idx]})
        # Try to recover the perm by following the chain
        if start_a is not None:
            # Build adj: (a, t) → (b, tp)
            adj = {(a, t): (b, tp) for (a, t, b, tp, _) in used_xfers}
            # Find start vertex (the (start_a, t) with no inbound transfer)
            start_t = 0
            cur = (start_a, start_t)
            perm = [start_a]
            visited = {start_a}
            times, tofs = [], []
            for _ in range(n - 1):
                if cur not in adj:
                    # Try coasting forward to find next transfer
                    a, t = cur
                    found = False
                    for tt in range(t + 1, n_t):
                        if (a, tt) in adj:
                            cur = (a, tt)
                            found = True
                            break
                    if not found:
                        break
                a, t = cur
                b, tp = adj[cur]
                times.append(float(grid[t]))
                tofs.append(float(grid[tp] - grid[t]))
                visited.add(b)
                perm.append(b)
                cur = (b, tp)
            info["perm"] = perm
            info["perm_len"] = len(perm)
            if len(perm) == n:
                x_dec = times + tofs + [float(p) for p in perm]
                f = kt.fitness(x_dec)
                feas = kt.is_feasible(f)
                info["fitness"] = list(f)
                info["feasible"] = feas
                if feas and f[0] < 142.99:
                    p = Path(out) / f"{problem}.json"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(json.dumps([{"decisionVector": x_dec,
                                              "problem": problem,
                                              "challenge": CHALLENGE}]))
                    info["replaced_banked"] = True
                    info["banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    dt = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    ms = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    drop_exc = (len(sys.argv) > 3 and sys.argv[3] == "noexc")
    print(json.dumps(build_and_solve(inst, dt=dt, max_s=ms,
                                     drop_exception_budget=drop_exc),
                     indent=2))
