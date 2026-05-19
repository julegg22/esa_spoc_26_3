"""Ch2 Keplerian Tomato TSP — official-mirror scorer + greedy baseline.

Mirrors the official KTTSP UDP (reference/spoc4_udp/kttsp-*.py, L-002):
time-dependent orbital ATSP, minimise makespan = times[-1]+tofs[-1];
each leg Δv≤600, ≤5 legs in (100,600], rest ≤100; chronological;
Δv via multi-rev Lambert about the Moon. H-003. Greedy nearest-
feasible constructor → early valid baseline (META.md §2).
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pykep as pk

MU_MOON = 4.904869500000000e12
CHALLENGE = "spoc-4-keplerian-tomato-traveling-salesperson"


class KTTSP:
    def __init__(self, path, max_revs=20):
        self.max_revs = max_revs
        hdr, rows = None, []
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                s = raw.strip()
                if not s or s.startswith("c"):
                    continue
                if s.startswith("p "):
                    hdr = s.split()
                    continue
                rows.append([float(v) for v in s.split()])
        self.t0 = pk.epoch(float(hdr[2]))
        self.min_tof = float(hdr[3])
        self.max_time = float(hdr[4])
        self.dv_thr = float(hdr[5])
        self.dv_exc = float(hdr[6])
        self.n_exc = int(hdr[7])
        self.opar = np.asarray(rows, float)
        self.n = self.opar.shape[0]
        self.tom = [
            pk.planet.keplerian(self.t0, list(r), MU_MOON, 0.0, 0.0, 0.0)
            for r in self.opar
        ]

    def compute_transfer(self, i, j, t_start, tof):
        ri, vi = self.tom[i].eph(t_start)
        rj, vj = self.tom[j].eph(t_start + tof)
        best = float("inf")
        for cw in (False, True):
            try:
                lp = pk.lambert_problem(ri, rj, tof * pk.DAY2SEC,
                                        MU_MOON, cw, self.max_revs)
            except Exception:
                continue
            for v1, v2 in zip(lp.get_v1(), lp.get_v2(), strict=False):
                dv = (np.linalg.norm(np.array(v1) - np.array(vi))
                      + np.linalg.norm(np.array(v2) - np.array(vj)))
                best = min(best, dv)
        return best

    def fitness(self, x):
        n = self.n
        times = x[:n - 1]
        tofs = x[n - 1:2 * n - 2]
        order = [round(v) for v in x[2 * n - 2:]]
        perm_c = len(set(order)) - n
        dv_cnt = exc_cnt = time_cnt = 0
        for i in range(n - 1):
            dv = self.compute_transfer(order[i], order[i + 1],
                                       times[i], tofs[i])
            if dv <= self.dv_exc + 1e-6:
                dv_cnt += 1
            if self.dv_thr < dv <= self.dv_exc + 1e-6:
                exc_cnt += 1
            if i < n - 2 and times[i] + tofs[i] <= times[i + 1] + 1e-6:
                time_cnt += 1
        return [times[-1] + tofs[-1], perm_c, dv_cnt - (n - 1),
                time_cnt - (n - 2), exc_cnt - self.n_exc]

    def is_feasible(self, f):
        return (f[1] == 0 and f[2] == 0 and f[3] == 0 and f[4] <= 0)


def greedy(kt: KTTSP, start=0, tof_grid=None):
    """No-wait greedy: from current tomato pick the next minimising leg
    Δv (≤ dv_thr if possible, else accept an exception, ≤5) over a TOF
    grid; depart on arrival (chronological by construction)."""
    if tof_grid is None:
        tof_grid = np.concatenate([np.arange(0.2, 5, 0.4),
                                   np.arange(5, 30, 2.0)])
    n = kt.n
    unvis = set(range(n))
    unvis.discard(start)
    order = [start]
    times, tofs = [], []
    t, exc_used = 0.0, 0
    cur = start
    while unvis:
        best = None  # (dv, tof, j, is_exc)
        for j in unvis:
            for tf in tof_grid:
                dv = kt.compute_transfer(cur, j, t, float(tf))
                if dv > kt.dv_exc + 1e-6:
                    continue
                is_exc = dv > kt.dv_thr
                if is_exc and exc_used >= kt.n_exc:
                    continue
                key = (dv, float(tf), j, is_exc)
                if best is None or dv < best[0]:
                    best = key
        if best is None:  # no feasible next under any tof → fail
            return None
        dv, tf, j, is_exc = best
        times.append(t)
        tofs.append(tf)
        t += tf
        exc_used += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def greedy_wait(kt: KTTSP, start, wait=4.0, d_dep=0.3,
                tof_grid=None, prefer_normal=True):
    """Earliest-feasible-arrival greedy WITH waiting. From each tomato,
    scan departure times t_dep∈[t_ready, t_ready+wait] and a TOF grid;
    pick the (j, t_dep, tof) feasible (Δv≤dv_thr, else an exception ≤5)
    minimising arrival time t_dep+tof (≈ makespan). Chronology holds by
    construction (t_dep ≥ t_ready = previous arrival)."""
    if tof_grid is None:
        tof_grid = np.concatenate([np.arange(0.2, 4, 0.4),
                                   np.arange(4, 20, 1.5)])
    n = kt.n
    unvis = set(range(n)) - {start}
    order, times, tofs = [start], [], []
    cur, t_ready, exc = start, 0.0, 0
    while unvis:
        best = None  # (arr, t_dep, tof, j, is_exc, dv)
        for j in unvis:
            for t_dep in np.arange(t_ready, t_ready + wait + 1e-9, d_dep):
                for tf in tof_grid:
                    if t_dep + tf > kt.max_time:
                        continue
                    dv = kt.compute_transfer(cur, j, float(t_dep), float(tf))
                    if dv > kt.dv_exc + 1e-6:
                        continue
                    is_exc = dv > kt.dv_thr
                    if is_exc and exc >= kt.n_exc:
                        continue
                    arr = t_dep + tf
                    rank = (arr, dv) if not prefer_normal else (
                        is_exc, arr, dv)
                    if best is None or rank < best[0]:
                        best = (rank, float(t_dep), float(tf), j, is_exc)
        if best is None:
            return None
        _, t_dep, tf, j, is_exc = best
        times.append(t_dep)
        tofs.append(tf)
        t_ready = t_dep + tf
        exc += int(is_exc)
        order.append(j)
        unvis.discard(j)
        cur = j
    return times + tofs + [float(o) for o in order]


def analyze_structure(kt: KTTSP, n_t=10, n_tof=14):
    """M-002 ultrathink probe: pairwise min-Δv over a (t_dep,tof,rev)
    search → reveal the cheap-edge graph structure (is Ch2 a clustered
    constrained-Hamiltonian-path problem?)."""
    n = kt.n
    t_grid = np.linspace(0.0, min(20.0, kt.max_time * 0.1), n_t)
    tof_grid = np.concatenate([np.arange(0.2, 4, 0.3),
                               np.arange(4, 25, 2.0)])[:n_tof]
    from scipy.optimize import minimize

    def edge_min(i, j):
        # coarse grid → seed → Nelder-Mead local polish (cheap Δv
        # windows are narrow; multi-rev handled inside compute_transfer)
        best, seed = np.inf, (0.0, 1.0)
        for td in t_grid:
            for tf in tof_grid:
                dv = kt.compute_transfer(i, j, float(td), float(tf))
                if dv < best:
                    best, seed = dv, (float(td), float(tf))
        try:
            r = minimize(
                lambda p: kt.compute_transfer(
                    i, j, max(p[0], 0.0),
                    min(max(p[1], kt.min_tof), kt.max_time)),
                np.array(seed), method="Nelder-Mead",
                options={"xatol": 1e-3, "fatol": 1e-2, "maxiter": 60},
            )
            best = min(best, float(r.fun))
        except Exception:
            pass
        return best

    M = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(n):
            if i != j:
                M[i, j] = edge_min(i, j)
    finite = M[np.isfinite(M)]
    le100 = int((M <= 100).sum())
    le600 = int(((M > 100) & (M <= 600)).sum())
    outdeg100 = (M <= 100).sum(axis=1)
    return {
        "n": n,
        "pairs": n * (n - 1),
        "min_dv_m_s": {"min": float(finite.min()),
                       "median": float(np.median(finite)),
                       "p10": float(np.percentile(finite, 10)),
                       "max_finite": float(finite.max())},
        "edges_le100": le100,
        "edges_100_600": le600,
        "nodes_with_no_le100_out": int((outdeg100 == 0).sum()),
        "min_outdeg_le100": int(outdeg100.min()),
        "median_outdeg_le100": float(np.median(outdeg100)),
    }


def solve_small(inst, problem="small", n_starts=8,
                out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    """Multi-start greedy_wait; keep the best FEASIBLE tour by makespan;
    bank the artifact. Establishes the early valid Ch2 baseline."""
    from pathlib import Path

    kt = KTTSP(inst)
    starts = np.linspace(0, kt.n - 1, min(n_starts, kt.n), dtype=int)
    best_x, best_f = None, None
    for s in dict.fromkeys(int(v) for v in starts):
        x = greedy_wait(kt, s)
        if x is None:
            continue
        f = kt.fitness(x)
        if kt.is_feasible(f) and (best_f is None or f[0] < best_f[0]):
            best_x, best_f = x, f
    if best_x is None:
        return {"problem": problem, "feasible": False,
                "note": "no feasible tour across starts (greedy_wait)"}
    p = Path(out) / f"{problem}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{"decisionVector": best_x, "problem": problem,
                              "challenge": CHALLENGE}]))
    return {"problem": problem, "n": kt.n, "makespan_d": best_f[0],
            "feasible": True, "rank3_small_d": 111.76,
            "artifact": str(p)}


if __name__ == "__main__":
    inst = (
        "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
    if len(sys.argv) > 1 and sys.argv[1] == "probe":
        print(json.dumps(analyze_structure(KTTSP(inst)), indent=2))
    else:
        print(json.dumps(solve_small(inst), indent=2))
