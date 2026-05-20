"""Ch2 KTTSP — Cluster-insertion LNS over the best findxfer-greedy
partial path.

Insight from runs/ch2_v3/03_findxfer_par.json: best partial reaches 45
legs from start=34 but misses the small cluster {17, 11, 4} which is
mutually-connected at Δv≈20 m/s but reachable from the big cluster only
via Δv≈530–540 m/s exception bridges (E-022 observation).

This LNS:
1. Takes a partial perm of length L missing nodes M = {m_1..m_k}.
2. For each insertion point p ∈ {0..L-1} in the partial perm:
   - Try inserting the missing chain (m_1 → m_2 → ... → m_k) between
     position p and p+1, using two exception bridges (path_node[p] → m_1)
     and (m_k → path_node[p+1]).
3. Re-evaluates chronologically with find_earliest_transfer; keeps the
   permutation that yields the shortest makespan + ≤5 exceptions.

The missing chain order can also be permuted (k! = 3! = 6 options for
k=3); enumerate all.
"""

from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def walk_perm_chrono(kt, perm, tof_window=18.0, n_steps=180,
                     wait_steps=12, wait_dt=1.0):
    """Walk perm chronologically. For each leg, find earliest feasible
    transfer (cheap → exc → wait). Return (times, tofs, dvs, ok)."""
    cur, t = perm[0], 0.0
    times, tofs, dvs = [], [], []
    exc = 0
    for k in range(1, len(perm)):
        j = perm[k]
        # Try cheap
        tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                          tof_window, n_steps)
        is_exc = False
        if tof is None and exc < kt.n_exc:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                              tof_window, n_steps)
            if tof is not None:
                is_exc = True
        if tof is None:
            # Try waiting (cheap then exc)
            found = False
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                tof2, dv2 = find_earliest_transfer(kt, cur, j, t_try,
                                                    kt.dv_thr,
                                                    tof_window, n_steps)
                if tof2 is not None:
                    t = t_try
                    tof, dv = tof2, dv2
                    is_exc = False
                    found = True
                    break
                if exc < kt.n_exc:
                    tof2, dv2 = find_earliest_transfer(kt, cur, j, t_try,
                                                        kt.dv_exc,
                                                        tof_window, n_steps)
                    if tof2 is not None:
                        t = t_try
                        tof, dv = tof2, dv2
                        is_exc = True
                        found = True
                        break
            if not found:
                return times, tofs, dvs, False, exc, k
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        if is_exc:
            exc += 1
        t = t + tof
        cur = j
        if t > kt.max_time:
            return times, tofs, dvs, False, exc, k
    return times, tofs, dvs, True, exc, len(perm) - 1


def insert_lns(kt, partial_perm, missing, verbose=True,
               tof_window=18.0, n_steps=180):
    """Try inserting the missing nodes (in any order, contiguous chain)
    at each position p in partial_perm. Returns the best feasible full
    perm + decision_vector or (None, None, None) if no insertion feasible."""
    n_full = kt.n
    best = None  # (makespan, perm, times, tofs, dvs)
    orderings = list(itertools.permutations(missing))
    L = len(partial_perm)
    n_try = 0
    n_feas = 0
    for p in range(L):  # insert after partial_perm[p]
        for chain in orderings:
            new_perm = list(partial_perm[:p + 1]) + list(chain) \
                       + list(partial_perm[p + 1:])
            if len(new_perm) != n_full:
                continue
            n_try += 1
            times, tofs, dvs, ok, exc, _leg = walk_perm_chrono(
                kt, new_perm, tof_window=tof_window, n_steps=n_steps)
            if not ok:
                continue
            mk = times[-1] + tofs[-1]
            n_feas += 1
            x = times + tofs + [float(v) for v in new_perm]
            f = kt.fitness(x)
            feas = kt.is_feasible(f)
            if verbose:
                print(f"  insert@{p} chain={chain}: ok mk={mk:.2f}, "
                      f"exc={exc}, feas={feas}", flush=True)
            if feas and (best is None or mk < best[0]):
                best = (mk, new_perm, times, tofs, dvs)
    if verbose:
        print(f"insertions tried: {n_try}, feasible (per fitness): {n_feas}",
              flush=True)
    if best is None:
        return None, None, None
    return best[1], best[2:5], n_feas


def main(inst, problem="small",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    # From runs/ch2_v3/03_findxfer_par.json, start=34, 45 legs:
    partial = [34, 23, 18, 46, 12, 10, 41, 2, 25, 22, 13, 20, 40, 44, 5,
               47, 36, 31, 37, 9, 48, 45, 15, 28, 1, 29, 30, 19, 43, 0,
               39, 8, 38, 24, 6, 35, 26, 21, 7, 3, 42, 14, 33, 27, 16, 32]
    missing = sorted(set(range(kt.n)) - set(partial))
    print(f"partial: {len(partial)} nodes, missing: {missing}", flush=True)
    t0 = time.time()
    perm, parts, n_feas = insert_lns(kt, partial, missing)
    wall = time.time() - t0
    info = {"problem": problem, "n": kt.n, "wall_s": round(wall, 1),
            "n_feasible_insertions": n_feas,
            "rank3_small_d": 111.76}
    if perm is None:
        info["feasible"] = False
        return info
    times, tofs, _dvs = parts
    x = times + tofs + [float(v) for v in perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    info.update({"makespan_d": round(f[0], 3),
                 "perm_c": f[1], "dv_c": f[2], "time_c": f[3],
                 "exc_c": f[4], "feasible": feas,
                 "perm": [int(p) for p in perm]})
    if feas:
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
    print(json.dumps(main(inst), indent=2))
