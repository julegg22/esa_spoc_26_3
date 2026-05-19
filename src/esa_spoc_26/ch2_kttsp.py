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


def solve_small(inst, problem="small",
                out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    x = greedy(kt)
    if x is None:
        return {"problem": problem, "feasible": False,
                "note": "greedy found no feasible next leg"}
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    if feas:
        from pathlib import Path
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": x, "problem": problem,
                                  "challenge": CHALLENGE}]))
    return {"problem": problem, "n": kt.n, "makespan_d": f[0],
            "perm_c": f[1], "dv_c": f[2], "time_c": f[3], "exc_c": f[4],
            "feasible": feas, "rank3_small_d": 111.76}


if __name__ == "__main__":
    inst = sys.argv[1] if len(sys.argv) > 1 else (
        "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(solve_small(inst), indent=2))
