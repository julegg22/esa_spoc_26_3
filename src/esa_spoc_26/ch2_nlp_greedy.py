"""Ch2 KTTSP — CONTINUOUS-TIME per-leg NLP + greedy permutation builder
(T-008 finalised heavy-compute target). Discrete CP-SAT over precomputed
point-windows was proven infeasible at three densities (E-018/20/21);
the binding constraint is the per-arc `T_j = td_k + tof_k` exact
equality. This module replaces table-lookup with a per-leg NLP that
finds (td*, tof*) given chronological predecessor:

  argmin Δv(td, tof)  s.t.  td ≥ t_ready,
                            td + tof ≤ max_time,
                            tof ∈ [min_tof, tof_cap]

solved via scipy `least_squares`-style or Nelder-Mead with multi-start
seeds (cheap-window precompute + grid). Returns (Δv, td, tof) or None
if no feasible point.

Greedy permutation: at each step from current `cur` at `t_ready`, pick
the (next, td, tof) minimising Δv (or arrival time, or makespan-aware
mix) over unvisited tomatoes, respecting exception budget.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def solve_leg_nlp(kt, i, j, t_ready, t_budget=None, dv_cap=600.0,
                  arr_weight=1.0, n_td=12, n_tof=10):
    """Solve for arc (i, j) starting after t_ready, ending ≤ t_budget.
    Coarse 2D scan of Δv(td, tof) (n_td × n_tof grid) followed by NLP
    refinement of the K best local-minima seeds. Returns (Δv, td, tof)
    of the *best feasible* solution, or None.

    Objective (smaller is better):  arr + Δv / arr_weight + pen(Δv>cap)
    """
    if t_budget is None:
        t_budget = kt.max_time
    if t_budget - t_ready < 0.5:
        return None
    tds = np.linspace(t_ready + 0.05, max(t_ready + 0.06,
                                          t_budget - 0.5), n_td)
    # tof scales with available window
    tof_max = max(0.5, t_budget - t_ready - 0.05)
    tofs = np.linspace(0.4, min(tof_max, 36.0), n_tof)
    # Grid scan
    grid = np.full((n_td, n_tof), np.inf)
    for a, td in enumerate(tds):
        for b, tof in enumerate(tofs):
            if td + tof > t_budget + 1e-6:
                continue
            grid[a, b] = kt.compute_transfer(i, j, float(td), float(tof))
    # Pick K best grid cells as NLP seeds
    flat = grid.flatten()
    if np.isinf(flat).all():
        return None
    K = min(8, int((flat <= dv_cap + 200).sum()))
    if K <= 0:
        K = 4
    seed_idx = np.argpartition(flat, K)[:K]
    best = None  # (combined_cost, Δv, td, tof)

    def cost_fn(x):
        td, tof = x
        if td < t_ready - 1e-6 or tof < 0.4 or td + tof > t_budget + 1e-6:
            return 1e8
        dv = kt.compute_transfer(i, j, float(td), float(tof))
        pen = max(0.0, dv - dv_cap) * 1000.0
        return td + tof + dv / max(arr_weight, 1e-6) + pen

    for idx in seed_idx:
        a, b = divmod(int(idx), n_tof)
        td0, tof0 = float(tds[a]), float(tofs[b])
        if td0 + tof0 >= t_budget:
            continue
        try:
            r = minimize(cost_fn, [td0, tof0], method="Nelder-Mead",
                         options={"xatol": 0.01, "fatol": 0.5,
                                  "maxiter": 150})
        except Exception:
            continue
        td, tof = float(r.x[0]), float(r.x[1])
        if td < t_ready - 1e-6 or td + tof > t_budget + 1e-6 or tof < 0.4:
            continue
        dv = kt.compute_transfer(i, j, td, tof)
        if dv <= dv_cap + 1e-6:
            c = td + tof + dv / max(arr_weight, 1e-6)
            if best is None or c < best[0]:
                best = (c, float(dv), td, tof)
    if best is None:
        # fallback: just take grid-min cell if it's ≤ dv_cap
        mn_idx = int(np.argmin(flat))
        a, b = divmod(mn_idx, n_tof)
        td0, tof0 = float(tds[a]), float(tofs[b])
        dv0 = float(grid[a, b])
        if dv0 <= dv_cap + 1e-6 and td0 + tof0 <= t_budget + 1e-6:
            return (dv0, td0, tof0)
        return None
    return (best[1], best[2], best[3])


def greedy_nlp(kt, start=0, deadline=120.0, prefer_normal=True,
               makespan_bias=0.5):
    """Greedy permutation builder using NLP per-leg. From cur, pick the
    unvisited (j, td*, tof*) minimising a mix of Δv and arrival time:
        rank = (is_exc_used_up?, dv*0.001 + arr*makespan_bias)
    where is_exc_used_up flags pushing an exception when budget left.
    """
    n = kt.n
    cur, t = start, 0.0
    unvis = set(range(n)) - {start}
    order, times, tofs = [start], [], []
    exc = 0
    started_at = time.time()
    while unvis:
        if time.time() - started_at > deadline:
            return None
        best = None
        for j in unvis:
            r = solve_leg_nlp(kt, cur, j, t)
            if r is None:
                continue
            dv, td, tof = r
            is_exc = dv > kt.dv_thr
            if is_exc and exc >= kt.n_exc:
                continue
            arr = td + tof
            key = (is_exc if prefer_normal else 0,
                   dv * 0.001 + arr * makespan_bias, dv, arr)
            if best is None or key < best[0]:
                best = (key, td, tof, j, is_exc, dv)
        if best is None:
            return None
        _, td, tof, j, is_exc, dv = best
        times.append(td)
        tofs.append(tof)
        t = td + tof
        exc += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def search_starts(inst, problem="small",
                  out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
                  deadline_per_start=180.0, max_starts=49):
    """Try greedy_nlp from each start; bank the best feasible."""
    kt = KTTSP(inst)
    results = []
    feasible_best = None
    for st in range(min(max_starts, kt.n)):
        t0 = time.time()
        x = greedy_nlp(kt, start=st, deadline=deadline_per_start)
        wall = time.time() - t0
        if x is None:
            results.append({"start": st, "ok": False, "wall_s": round(wall, 1)})
            continue
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        results.append({"start": st, "ok": True, "feas": feas,
                        "makespan_d": round(f[0], 3),
                        "dv_c": f[2], "exc_c": f[4],
                        "wall_s": round(wall, 1)})
        if feas and (feasible_best is None
                     or f[0] < feasible_best["makespan_d"]):
            feasible_best = {"start": st, "x": list(x),
                             "makespan_d": float(f[0])}
    info = {"problem": problem, "n": kt.n, "starts_tried": len(results),
            "rank3_small_d": 111.76, "best_feasible": feasible_best,
            "results_summary":
            [r for r in results if r.get("ok") and r.get("feas")]}
    if feasible_best is not None:
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": feasible_best["x"],
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["artifact"] = str(p)
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    dl = float(sys.argv[1]) if len(sys.argv) > 1 else 120.0
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 49
    print(json.dumps(search_starts(inst, deadline_per_start=dl,
                                   max_starts=ns), indent=2))
