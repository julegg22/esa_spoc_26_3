"""Ch2 KTTSP — Dynamic Discretization Discovery (DDD) on top of the
Bannach time-expanded ILP encoding (O-009, E-026).

Bannach §5 (Boland et al. 2017 DDD):
- Start with a COARSE time-interval partition Λ per α (initially: 1–2
  intervals covering [t_0, t_max]).
- Build the time-INTERVAL network Γ_I (arcs aggregate min-Δv over all
  time-points in interval pair).
- Solve Γ_I via MILP (small ⇒ fast).
- Check the solution against the time-INDEXED problem:
  - **Temporal glitch** (Bannach Fig. 3): the chosen transfer can't be
    realised at any actual time-point in the source interval. Split
    the interval at the time of conflict.
  - **Subtour** (Fig. 4): the solution contains a cycle. Add a DFJ
    subtour-elimination constraint and re-solve.
- Re-solve until feasible.
- Theorem 1: converges to optimum as dt → 0.

Adapted for our SpOC4 KTTSP makespan objective:
- Per α, maintain interval partition Λ_α as a sorted list of
  time-points covering [0, max_time].
- Arc weights: min-Δv across all (td, tof, dv) windows that snap into
  the interval pair. Plus the (representative td_repr, arr_repr) for
  reconstruction.
- Objective: min makespan = max arrival across used arcs.

Simplified implementation: a few rounds of refinement, no full
subtour-elimination loop (we rely on flow conservation + MTZ-free).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import highspy
import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def _build_initial_intervals(max_time, n_init=5):
    """Initial Λ: n_init equally-spaced points covering [0, max_time]."""
    return [list(np.linspace(0.0, max_time, n_init))]


def build_interval_model(kt, npz_w, intervals_per_a):
    """Build the time-INTERVAL graph + MILP.
    intervals_per_a: list (length n) of sorted breakpoints per α.
    Each consecutive pair forms an interval. Returns the solver model
    + indexing dictionaries."""
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]
    n = kt.n

    # For each α, the intervals are pairs of consecutive breakpoints.
    # Index intervals per α by their start-breakpoint index.
    # vertex = (α, interval_idx) where interval_idx ∈ [0, len(breakpoints)-2]
    # vertex_arrival_time = breakpoints[interval_idx+1] (the END of the
    # interval = arrival time within it)
    # vertex_departure_time = breakpoints[interval_idx] (the START)

    # Coasting arcs: (α, k) → (α, k+1) for k ∈ [0, n_intervals_a-2]
    coasts = []
    for a in range(n):
        bps = intervals_per_a[a]
        n_iv = len(bps) - 1
        for k in range(n_iv - 1):
            coasts.append((a, k, a, k + 1))

    # Transfer arcs: aggregate min-Δv per (α-interval, β-interval) pair.
    # For each (i, j) pair, for each window k of (i, j), determine which
    # interval (k_a, k_b) it falls into. Keep the min-Δv per (k_a, k_b).
    transfer_dict = {}  # (i, k_a, j, k_b) -> (min_dv, td_repr, tof_repr)
    for i in range(n):
        bps_i = intervals_per_a[i]
        n_iv_i = len(bps_i) - 1
        for j in range(n):
            if i == j or counts[i, j] == 0:
                continue
            bps_j = intervals_per_a[j]
            n_iv_j = len(bps_j) - 1
            for kw in range(int(counts[i, j])):
                dv, td, tof = W[i, j, kw]
                if not np.isfinite(dv) or dv > kt.dv_exc + 1e-6:
                    continue
                arr = td + tof
                if arr > kt.max_time + 1e-6:
                    continue
                # Find k_a: largest interval of i whose start ≤ td
                k_a = max(0, np.searchsorted(bps_i, td, side='right') - 1)
                if k_a >= n_iv_i:
                    k_a = n_iv_i - 1
                # Find k_b: smallest interval of j whose end ≥ arr
                k_b = min(n_iv_j - 1,
                          np.searchsorted(bps_j, arr, side='left'))
                if k_b == 0 and bps_j[0] >= arr:
                    pass  # arr ≤ first break-point
                # Avoid self-arc on (α, α)-interval
                if i == j and k_a == k_b:
                    continue
                # Ensure forward time: bps_j[k_b+1] (end of target intvl) >
                # bps_i[k_a] (start of source intvl)
                end_b = bps_j[min(len(bps_j) - 1, k_b + 1)]
                start_a = bps_i[k_a]
                if end_b <= start_a:
                    continue
                key = (i, k_a, j, k_b)
                prior = transfer_dict.get(key)
                if prior is None or dv < prior[0]:
                    transfer_dict[key] = (float(dv), float(td), float(tof))
    transfers = [(i, k_a, j, k_b, dv, td, tof)
                 for (i, k_a, j, k_b), (dv, td, tof)
                 in transfer_dict.items()]
    return coasts, transfers


def solve_interval_milp(kt, intervals_per_a, coasts, transfers,
                        max_s=120.0, drop_exception=False):
    """Solve the MILP for the time-interval network. Returns
    (status, solution_dict, perm_recovered_or_None)."""
    n = kt.n
    n_intervals = sum(len(bps) - 1 for bps in intervals_per_a)
    # End-time of each interval for makespan term:
    end_time = {}
    for a in range(n):
        bps = intervals_per_a[a]
        for k in range(len(bps) - 1):
            end_time[(a, k)] = bps[k + 1]

    h = highspy.Highs()
    h.silent()

    n_coast = len(coasts)
    n_xfer = len(transfers)
    c_idx = {(a, k): i for i, (a, k, _a2, _k2) in enumerate(coasts)}
    x_idx = {}
    for i, (a, k, b, kp, _dv, _td, _tof) in enumerate(transfers):
        x_idx[(a, k, b, kp)] = n_coast + i
    s_idx = {a: n_coast + n_xfer + a for a in range(n)}
    e_idx = {a: n_coast + n_xfer + n + a for a in range(n)}
    mk_idx = n_coast + n_xfer + 2 * n
    n_vars = mk_idx + 1

    for _ in range(n_coast + n_xfer + 2 * n):
        h.addVar(0.0, 1.0)
    h.addVar(0.0, kt.max_time)
    for v in range(n_coast + n_xfer + 2 * n):
        h.changeColIntegrality(v, highspy.HighsVarType.kInteger)
    h.changeColCost(mk_idx, 1.0)

    def add(rows, lower=-highspy.kHighsInf, upper=highspy.kHighsInf):
        idxs = np.array([r[0] for r in rows], dtype=np.int32)
        vals = np.array([r[1] for r in rows], dtype=np.float64)
        h.addRow(lower, upper, len(rows), idxs, vals)

    # Σ s = 1, Σ e = 1
    add([(s_idx[a], 1.0) for a in range(n)], lower=1.0, upper=1.0)
    add([(e_idx[a], 1.0) for a in range(n)], lower=1.0, upper=1.0)

    # Departure: each α must depart at least once OR be end
    for a in range(n):
        rows = []
        for (aa, k, b, kp), idx in x_idx.items():
            if aa == a:
                rows.append((idx, 1.0))
        rows.append((e_idx[a], 1.0))
        if rows:
            add(rows, lower=1.0)

    # Flow per-(α, k) interval-vertex
    for a in range(n):
        bps = intervals_per_a[a]
        n_iv = len(bps) - 1
        for k in range(n_iv):
            rows = []
            # Coast in
            if k > 0 and (a, k - 1) in c_idx:
                rows.append((c_idx[(a, k - 1)], 1.0))
            # Transfers in
            for (aa, kk, bb, kp), idx in x_idx.items():
                if bb == a and kp == k:
                    rows.append((idx, 1.0))
            # Coast out
            if k < n_iv - 1 and (a, k) in c_idx:
                rows.append((c_idx[(a, k)], -1.0))
            # Transfers out
            for (aa, kk, bb, kp), idx in x_idx.items():
                if aa == a and kk == k:
                    rows.append((idx, -1.0))
            # Source / sink markers
            if k == 0:
                rows.append((s_idx[a], 1.0))
            if k == n_iv - 1:
                rows.append((e_idx[a], -1.0))
            if rows:
                add(rows, lower=0.0, upper=0.0)

    # Exception budget
    if not drop_exception:
        exc_rows = []
        for (a, k, b, kp, dv, _td, _tof) in transfers:
            if dv > kt.dv_thr:
                exc_rows.append((x_idx[(a, k, b, kp)], 1.0))
        if exc_rows:
            add(exc_rows, upper=float(kt.n_exc))

    # Makespan: mk ≥ end_time[(b, kp)] · x for each transfer arc
    for (a, k, b, kp, _dv, _td, _tof) in transfers:
        add([(mk_idx, 1.0), (x_idx[(a, k, b, kp)], -float(end_time[(b, kp)]))],
            lower=0.0)

    h.setOptionValue("time_limit", float(max_s))
    h.setOptionValue("mip_rel_gap", 0.02)
    t0 = time.time()
    h.run()
    wall = time.time() - t0
    status = h.getModelStatus()
    info = h.getInfo()
    sol = h.getSolution()
    obj = (info.objective_function_value
           if hasattr(info, "objective_function_value") else None)
    result = {"status": str(status), "wall_s": round(wall, 2),
              "obj": obj, "n_vars": n_vars,
              "n_intervals": n_intervals,
              "n_xfer": n_xfer}
    if status not in (highspy.HighsModelStatus.kOptimal,
                      highspy.HighsModelStatus.kFeasible):
        return status, result, None

    # Recover perm
    used = [(a, k, b, kp, dv, td, tof)
            for (a, k, b, kp, dv, td, tof) in transfers
            if sol.col_value[x_idx[(a, k, b, kp)]] >= 0.5]
    start_a = next((a for a in range(n)
                    if sol.col_value[s_idx[a]] >= 0.5), None)
    end_a = next((a for a in range(n)
                  if sol.col_value[e_idx[a]] >= 0.5), None)
    result["n_used_xfers"] = len(used)
    result["start"] = start_a
    result["end"] = end_a
    result["mk_var"] = sol.col_value[mk_idx]
    result["transfers"] = used
    return status, result, used


def reconstruct_and_check(kt, used_transfers, start_a):
    """Build a decision vector from used transfers and check feasibility.
    Returns (perm, times, tofs, dvs, fitness, feasible) or None on
    inconsistency."""
    n = kt.n
    if not used_transfers:
        return None
    # Build adjacency: (a, k) → (b, kp, td, tof)
    adj = {}
    for (a, k, b, kp, _dv, td, tof) in used_transfers:
        adj[(a, k)] = (b, kp, td, tof)
    # Find start vertex (start_a at the smallest interval index from which
    # there's an outgoing arc — typically (start_a, 0))
    cur = None
    for k in range(50):
        if (start_a, k) in adj:
            cur = (start_a, k)
            break
    if cur is None:
        return None
    perm = [start_a]
    times, tofs = [], []
    visited = {start_a}
    for _ in range(n - 1):
        if cur not in adj:
            break
        b, kp, td, tof = adj[cur]
        perm.append(b)
        times.append(td)
        tofs.append(tof)
        visited.add(b)
        cur = (b, kp)
    return perm, times, tofs


def ddd(inst, problem="small",
        npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
        out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
        n_init=5, max_iters=8, milp_time_s=120.0, total_time_s=2400.0):
    """Main DDD loop."""
    kt = KTTSP(inst)
    n = kt.n
    # Initial: same breakpoints per α
    init_bps = list(np.linspace(0.0, kt.max_time, n_init))
    intervals_per_a = [list(init_bps) for _ in range(n)]
    history = []
    t_overall = time.time()
    best_mk = float("inf")
    best_perm = None
    best_x = None
    for iter_i in range(max_iters):
        if time.time() - t_overall > total_time_s:
            print(f"DDD timed out after {iter_i} iters", flush=True)
            break
        n_intvs = sum(len(bps) - 1 for bps in intervals_per_a)
        coasts, transfers = build_interval_model(kt, npz_w,
                                                 intervals_per_a)
        print(f"[iter {iter_i}] n_intervals_total={n_intvs}, "
              f"transfers={len(transfers)}, coasts={len(coasts)}",
              flush=True)
        if not transfers:
            print("  no transfers — infeasible at this discretization",
                  flush=True)
            break
        _status, info, used = solve_interval_milp(
            kt, intervals_per_a, coasts, transfers, max_s=milp_time_s)
        info["iter"] = iter_i
        history.append(info)
        print(f"  status={info['status']}, mk={info.get('obj')}, "
              f"wall={info['wall_s']}s, n_used={info.get('n_used_xfers', 0)}",
              flush=True)
        if used is None:
            # Need to refine intervals: HALVE all intervals
            new_intervals_per_a = []
            for bps in intervals_per_a:
                new_bps = sorted(set(bps + [
                    (bps[k] + bps[k + 1]) / 2 for k in range(len(bps) - 1)
                ]))
                new_intervals_per_a.append(new_bps)
            intervals_per_a = new_intervals_per_a
            continue
        # Check decoded trajectory against KTSP fitness
        rec = reconstruct_and_check(kt, used, info["start"])
        if rec is None:
            print("  reconstruction failed", flush=True)
            break
        perm, times, tofs = rec
        if len(perm) != n:
            print(f"  perm incomplete ({len(perm)}/{n}); refining",
                  flush=True)
            # Refine: bisect every interval
            new_intervals_per_a = []
            for bps in intervals_per_a:
                new_bps = sorted(set(bps + [
                    (bps[k] + bps[k + 1]) / 2 for k in range(len(bps) - 1)
                ]))
                new_intervals_per_a.append(new_bps)
            intervals_per_a = new_intervals_per_a
            continue
        # Evaluate via official fitness
        x_dec = list(times) + list(tofs) + [float(p) for p in perm]
        f = kt.fitness(x_dec)
        feas = kt.is_feasible(f)
        info["fitness"] = list(f)
        info["feasible"] = feas
        info["perm"] = perm
        print(f"  perm complete; fitness={f}, feas={feas}", flush=True)
        if feas and f[0] < best_mk:
            best_mk = f[0]
            best_perm = perm
            best_x = x_dec
            print(f"  NEW BEST: mk={f[0]:.3f}", flush=True)
        # Refine: bisect ALL intervals (simple refinement)
        new_intervals_per_a = []
        for bps in intervals_per_a:
            new_bps = sorted(set(bps + [
                (bps[k] + bps[k + 1]) / 2 for k in range(len(bps) - 1)
            ]))
            new_intervals_per_a.append(new_bps)
        intervals_per_a = new_intervals_per_a
    # Output
    wall = time.time() - t_overall
    result = {"problem": problem, "n": n, "wall_s": round(wall, 1),
              "iters": len(history), "rank3_small_d": 111.76,
              "history": history,
              "best_mk": best_mk if best_mk < float("inf") else None,
              "best_perm": best_perm}
    if best_x is not None and best_mk < 142.99:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        result["banked"] = str(p)
    return result


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    n_init = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    max_iters = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    mt = float(sys.argv[3]) if len(sys.argv) > 3 else 120.0
    tt = float(sys.argv[4]) if len(sys.argv) > 4 else 2400.0
    print(json.dumps(ddd(inst, n_init=n_init, max_iters=max_iters,
                         milp_time_s=mt, total_time_s=tt), indent=2))
