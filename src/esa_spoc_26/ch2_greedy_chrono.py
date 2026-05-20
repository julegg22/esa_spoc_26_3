"""Ch2 KTTSP — fast chronological greedy from window-table lookup.

For each start node, walks the chain: at current (cur, t), pick the
unvisited (j, window_k) where window's `td ≥ t` and total arrival
(`td+tof`) is minimised, with cheap-preference if budget allows.

Pure table lookup over the windows2d_small.npz — ~1ms per step,
~5 s per full 49-node tour. Try many starts; refine the best via
chronological NLP post-process if needed. Tests whether ANY feasible
chain exists when freedom is maximal.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def greedy_chrono(W, counts, n, start, max_time, dv_thr=100.0,
                  dv_exc=600.0, n_exc=5, prefer_cheap=True):
    """Greedy chronological construction from start.
    Returns (perm, times, tofs, dvs, feasible) or None."""
    cur, t = start, 0.0
    unvis = set(range(n)) - {start}
    perm, times, tofs, dvs = [start], [], [], []
    exc = 0
    while unvis:
        best = None  # (rank, j, td, tof, dv, is_exc)
        for j in unvis:
            ws = W[cur, j, :int(counts[cur, j])]
            for w in ws:
                dv, td, tof = float(w[0]), float(w[1]), float(w[2])
                if not np.isfinite(dv):
                    continue
                if dv > dv_exc:
                    continue
                if td < t - 1e-6:
                    continue
                if td + tof > max_time:
                    continue
                is_exc = dv > dv_thr
                if is_exc and exc >= n_exc:
                    continue
                arr = td + tof
                # Rank: cheap first (if prefer_cheap), then earliest arrival
                rank = ((1 if is_exc else 0,) if prefer_cheap
                        else ()) + (arr, dv)
                if best is None or rank < best[0]:
                    best = (rank, j, td, tof, dv, is_exc)
        if best is None:
            return perm, times, tofs, dvs, False
        _, j, td, tof, dv, is_exc = best
        perm.append(j)
        times.append(td)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = td + tof
        unvis.discard(j)
        cur = j
    return perm, times, tofs, dvs, True


def search(inst, problem="small",
           npz_w="/home/julian/Projects/esa_spoc_26_3/windows2d_small.npz",
           out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
           verbose=True):
    kt = KTTSP(inst)
    Z = np.load(npz_w)
    W, counts = Z["W"], Z["counts"]
    n = kt.n
    best_full = None  # (makespan, start, perm, times, tofs, dvs)
    best_partial = None  # (legs_covered, ...)
    results = []
    t0 = time.time()
    for st in range(n):
        perm, times, tofs, dvs, ok = greedy_chrono(
            W, counts, n, st, kt.max_time,
            dv_thr=kt.dv_thr, dv_exc=kt.dv_exc, n_exc=kt.n_exc)
        legs = len(perm) - 1
        if ok:
            mk = times[-1] + tofs[-1] if times else 0.0
            results.append({"start": st, "legs": legs, "mk": round(mk, 2),
                            "n_exc": sum(1 for d in dvs if d > kt.dv_thr)})
            if best_full is None or mk < best_full[0]:
                best_full = (mk, st, perm, times, tofs, dvs)
        else:
            results.append({"start": st, "legs": legs, "ok": False})
            if best_partial is None or legs > best_partial[0]:
                best_partial = (legs, st, perm, times, tofs, dvs)
    wall = time.time() - t0
    info = {"problem": problem, "n": n, "n_starts": n,
            "wall_s": round(wall, 1),
            "n_full_tours": sum(1 for r in results if r.get("legs") == n - 1),
            "n_partial": sum(1 for r in results if r.get("legs", 0) < n - 1),
            "results_summary": results}
    if best_full is not None:
        mk, st, perm, times, tofs, dvs = best_full
        x = times + tofs + [float(p) for p in perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        info["best_full"] = {"start": st, "makespan_d": round(mk, 3),
                             "fitness": list(f), "feasible": feas,
                             "n_exc": sum(1 for d in dvs if d > kt.dv_thr),
                             "perm": [int(p) for p in perm]}
        if feas:
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["artifact"] = str(p)
            info["rank3_small_d"] = 111.76
    if best_partial is not None:
        legs_cov, st, perm, _, _, _ = best_partial
        info["best_partial"] = {"start": st, "legs_covered": legs_cov,
                                "perm_so_far": [int(p) for p in perm]}
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(search(inst), indent=2))
