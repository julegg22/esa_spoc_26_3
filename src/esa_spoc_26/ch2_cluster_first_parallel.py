"""Ch2 KTTSP — parallel cluster-first (6 orderings × 1 worker each)."""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

from esa_spoc_26.ch2_cluster_first import (
    CLUSTER,
    build_cluster_opener,
    greedy_continue,
)
from esa_spoc_26.ch2_findtransfer_greedy import (
    _WORKER_KT_FX,
    _init_worker_fx,
)
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def _worker(ordering):
    kt = _WORKER_KT_FX[0]
    opener = build_cluster_opener(kt, ordering, tof_window=8.0,
                                   n_steps=200)
    if opener is None:
        return ordering, None
    perm_o, t_o, tof_o, dv_o, t_end, exc_used = opener
    perm, times, tofs, dvs, ok = greedy_continue(
        kt, perm_o, t_end, exc_used,
        tof_window=12.0, n_steps=120)
    all_times = t_o + times
    all_tofs = tof_o + tofs
    all_dvs = dv_o + dvs
    return ordering, (perm, all_times, all_tofs, all_dvs, ok)


def search(inst, problem="small",
           out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    n = kt.n
    orderings = list(itertools.permutations(CLUSTER))
    import multiprocessing as mp
    t0 = time.time()
    full_tours = []
    partials = []
    with mp.Pool(4, initializer=_init_worker_fx, initargs=(inst,)) as pool:
        for ordering, result in pool.imap_unordered(_worker, orderings):
            if result is None:
                print(f"[{ordering}] opener INFEASIBLE", flush=True)
                continue
            perm, all_times, all_tofs, all_dvs, ok = result
            legs = len(perm) - 1
            if ok and legs == n - 1:
                mk = all_times[-1] + all_tofs[-1]
                n_exc = sum(1 for d in all_dvs if d > kt.dv_thr)
                full_tours.append({"ordering": list(ordering),
                                   "mk": mk,
                                   "n_exc": n_exc,
                                   "perm": perm,
                                   "times": all_times, "tofs": all_tofs,
                                   "dvs": all_dvs})
                print(f"[{ordering}] FULL TOUR mk={mk:.2f}, n_exc={n_exc}",
                      flush=True)
            else:
                missing = sorted(set(range(n)) - set(perm))
                partials.append({"ordering": list(ordering),
                                 "legs": legs, "missing": missing})
                print(f"[{ordering}] partial legs={legs}, missing={missing}",
                      flush=True)
    wall = time.time() - t0
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "n_full_tours": len(full_tours),
            "rank3_small_d": 111.76,
            "partials": partials}
    if full_tours:
        best = min(full_tours, key=lambda r: r["mk"])
        info["best_full_tour"] = {"ordering": best["ordering"],
                                  "mk": float(best["mk"]),
                                  "n_exc": best["n_exc"],
                                  "perm": [int(p) for p in best["perm"]]}
        x = best["times"] + best["tofs"] + [float(p) for p in best["perm"]]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        info["fitness"] = list(f)
        info["feasible_by_fitness"] = feas
        if feas and f[0] < 142.99:
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["replaced_banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(search(inst), indent=2))
