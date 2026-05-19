"""Ch2 KTTSP — joint order+timing co-optimising LNS (full commitment).

E-015 proved order and timing must be optimised jointly: an edge's Δv
depends on the *absolute* departure epoch. So we decode any order by a
**full-horizon** per-leg timing search (find the cheapest feasible
(t_dep≥t_ready, tof) over the whole [t_ready, max_time], not a short
window), score with the official-mirror fitness, and search the
permutation with LNS (cheap-graph-seeded order + ruin-and-recreate /
Or-opt). Target: feasible `small` tour, makespan → rank-3 (≤111.76 d).
"""

from __future__ import annotations

import json
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

_KT: KTTSP | None = None


@lru_cache(maxsize=400_000)
def _leg(i, j, t_ready_q):
    """Cheapest (dv, t_dep, tof) for i→j with t_dep ≥ t_ready over the
    FULL horizon (windows recur; quantised t_ready for cache hits)."""
    kt = _KT
    t_ready = t_ready_q * 0.5
    hi = kt.max_time
    if t_ready >= hi - 0.5:
        return (1e9, t_ready, 0.5)
    tg = np.arange(t_ready, hi - 0.4, 0.5)
    fg = np.concatenate([np.arange(0.2, 4, 0.3), np.arange(4, 26, 1.5)])
    best = (1e18, t_ready, 1.0)
    for td in tg:
        for tf in fg:
            if td + tf > hi:
                continue
            dv = kt.compute_transfer(i, j, float(td), float(tf))
            if dv < best[0]:
                best = (dv, float(td), float(tf))

    def _o(p):
        d = kt.compute_transfer(i, j, max(p[0], t_ready),
                                min(max(p[1], kt.min_tof),
                                    hi - max(p[0], t_ready)))
        return d if np.isfinite(d) else 1e12

    try:
        r = minimize(_o, np.array(best[1:]), method="Nelder-Mead",
                     options={"xatol": 1e-3, "fatol": 1e-2, "maxiter": 50})
        if r.fun < best[0]:
            td = max(float(r.x[0]), t_ready)
            best = (float(r.fun), td,
                    float(min(max(r.x[1], kt.min_tof), hi - td)))
    except Exception:
        pass
    return best


def decode(order):
    """order → (x, feasible, makespan, n_exc, n_bad). Per-leg full-
    horizon timing; chronological by construction."""
    kt = _KT
    times, tofs, t_ready, n_exc, n_bad = [], [], 0.0, 0, 0
    for k in range(len(order) - 1):
        dv, td, tf = _leg(order[k], order[k + 1], round(t_ready / 0.5))
        times.append(td)
        tofs.append(tf)
        t_ready = td + tf
        if dv > kt.dv_exc + 1e-6:
            n_bad += 1
        elif dv > kt.dv_thr:
            n_exc += 1
    x = times + tofs + [float(o) for o in order]
    mk = times[-1] + tofs[-1]
    feasible = (n_bad == 0 and n_exc <= kt.n_exc)
    return x, feasible, mk, n_exc, n_bad


def _cost(order):
    _, feas, mk, n_exc, n_bad = decode(order)
    # lexicographic-ish scalarisation: feasibility dominates makespan
    return (n_bad * 1e6 + max(0, n_exc - _KT.n_exc) * 1e5 + mk, feas, mk)


def initial_order(DV, n, rng):
    """Cheap-graph nearest construction (DV = static min-Δv matrix)."""
    cur = int(rng.integers(n))
    seen = {cur}
    order = [cur]
    while len(order) < n:
        cand = sorted((j for j in range(n) if j not in seen),
                      key=lambda j: DV[cur, j])
        cur = cand[0]
        order.append(cur)
        seen.add(cur)
    return order


def lns(inst, problem="small",
        npz="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
        out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
        budget_s=900.0, seed=0):
    global _KT
    _KT = KTTSP(inst)
    n = _KT.n
    DV = np.load(npz)["dv"]
    rng = np.random.default_rng(seed)
    cur = initial_order(DV, n, rng)
    cur_c = _cost(cur)
    best, best_c = cur[:], cur_c
    t0, it = time.time(), 0
    while time.time() - t0 < budget_s:
        it += 1
        cand = cur[:]
        op = rng.integers(3)
        if op == 0:                        # segment reversal (2-opt)
            a, b = sorted(rng.choice(n, 2, replace=False))
            cand[a:b + 1] = cand[a:b + 1][::-1]
        elif op == 1:                      # Or-opt relocate (len 1-3)
            L = int(rng.integers(1, 4))
            a = int(rng.integers(0, n - L))
            seg = cand[a:a + L]
            del cand[a:a + L]
            p = int(rng.integers(0, len(cand) + 1))
            cand[p:p] = seg
        else:                              # ruin & recreate (random k)
            k = int(rng.integers(3, max(4, n // 4)))
            idx = sorted(rng.choice(n, k, replace=False), reverse=True)
            removed = [cand.pop(i) for i in idx]
            for r in removed:              # cheapest-DV reinsertion
                bp, bd = 0, 1e18
                for p in range(len(cand) + 1):
                    left = DV[cand[p - 1], r] if p > 0 else 0
                    right = DV[r, cand[p]] if p < len(cand) else 0
                    if left + right < bd:
                        bd, bp = left + right, p
                cand.insert(bp, r)
        c = _cost(cand)
        if c[0] <= cur_c[0]:               # accept equal/better
            cur, cur_c = cand, c
            if c[0] < best_c[0]:
                best, best_c = cand[:], c
        elif rng.random() < 0.05:          # mild diversification
            cur, cur_c = cand, c
    x, feas, mk, n_exc, n_bad = decode(best)
    res = {"problem": problem, "n": n, "iters": it,
           "makespan_d": round(mk, 3), "n_exc": n_exc, "n_bad": n_bad,
           "feasible": feas, "rank3_small_d": 111.76}
    if feas:
        f = _KT.fitness(x)
        if _KT.is_feasible(f):
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": x,
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            res["artifact"] = str(p)
            res["official_makespan_d"] = round(f[0], 3)
        else:
            res["feasible"] = False
            res["note"] = f"decode-feasible but official rejects: {f}"
    return res


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    b = float(sys.argv[1]) if len(sys.argv) > 1 else 900.0
    print(json.dumps(lns(inst, budget_s=b), indent=2))
