"""Ch2 KTTSP — greedy variants with different per-step ranking criteria.

Standard greedy_findxfer picks min-arrival (t_ready + tof). For medium,
this leaves a 20-node cluster behind. Try different preferences that
might naturally visit clusters earlier.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import (
    _WORKER_KT_FX,
    _init_worker_fx,
    find_earliest_transfer,
)
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def greedy_variant(kt, start, mode="arrival", tof_window=12.0, n_steps=120,
                   wait_steps=4, wait_dt=0.5):
    """Single-start greedy with selectable ranking criterion.
    mode:
        - arrival: min(t_ready + tof)  (default, same as greedy_findxfer)
        - dv:      min(dv)             (lowest-Δv first)
        - tof:     min(tof)            (shortest-tof first)
        - hybrid:  min(t_ready + tof + dv*0.05)  (blend)
    """
    n = kt.n
    cur, t = start, 0.0
    unvis = set(range(n)) - {start}
    perm, times, tofs, dvs = [start], [], [], []
    exc = 0
    while unvis:
        candidates = []   # (j, tof, dv, is_exc, arr)
        for j in unvis:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                              tof_window, n_steps)
            if tof is not None:
                candidates.append((j, tof, dv, False, t + tof))
        if exc < kt.n_exc:
            for j in unvis:
                if any(c[0] == j and not c[3] for c in candidates):
                    continue
                tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                                  tof_window, n_steps)
                if tof is not None:
                    candidates.append((j, tof, dv, True, t + tof))
        if not candidates:
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                for j in unvis:
                    tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                     kt.dv_thr,
                                                     tof_window, n_steps)
                    if tof is not None:
                        candidates.append((j, tof, dv, False,
                                           t_try + tof))
                        t = t_try
                        break
                if candidates:
                    break
        if not candidates:
            return perm, times, tofs, dvs, False
        # Choose by mode
        cheap = [c for c in candidates if not c[3]]
        pool = cheap if cheap else candidates
        if mode == "arrival":
            best = min(pool, key=lambda c: (c[4], c[2]))
        elif mode == "dv":
            best = min(pool, key=lambda c: (c[2], c[4]))
        elif mode == "tof":
            best = min(pool, key=lambda c: (c[1], c[4]))
        elif mode == "hybrid":
            best = min(pool, key=lambda c: (c[4] + c[2] * 0.05, c[2]))
        else:
            best = min(pool, key=lambda c: (c[4], c[2]))
        j, tof, dv, is_exc, arr = best
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        perm.append(j)
        if is_exc:
            exc += 1
        t = arr
        unvis.discard(j)
        cur = j
    return perm, times, tofs, dvs, True


def _worker(args):
    st, mode, tof_window, n_steps = args
    kt = _WORKER_KT_FX[0]
    perm, times, tofs, dvs, ok = greedy_variant(
        kt, start=st, mode=mode, tof_window=tof_window, n_steps=n_steps)
    return st, mode, perm, times, tofs, dvs, ok


def sweep_variants(inst, problem="medium", n_starts=20,
                   out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    """Per start in {0, 1, ..., n_starts-1}, run all 4 ranking modes
    in parallel. Bank best feasible if any."""
    import multiprocessing as mp
    kt = KTTSP(inst)
    n = kt.n
    args = []
    for st in range(min(n_starts, n)):
        for mode in ["arrival", "dv", "tof", "hybrid"]:
            args.append((st, mode, 12.0, 120))
    print(f"Sweep: {len(args)} (start, mode) variants", flush=True)
    t0 = time.time()
    best_full = None
    best_partial = (0, None, None, None, None, None)
    rows = []
    with mp.Pool(4, initializer=_init_worker_fx,
                 initargs=(inst,)) as pool:
        for st, mode, perm, times, tofs, _dvs, ok in pool.imap_unordered(
                _worker, args):
            legs = len(perm) - 1
            if ok and legs == n - 1:
                mk = times[-1] + tofs[-1]
                x = times + tofs + [float(p) for p in perm]
                f = kt.fitness(x)
                feas = kt.is_feasible(f)
                rows.append({"start": st, "mode": mode, "legs": legs,
                             "mk": round(mk, 2), "feas": feas})
                if feas and (best_full is None or mk < best_full[0]):
                    best_full = (mk, perm, times, tofs, st, mode)
                print(f"  start={st}, mode={mode}: FULL legs={legs}, "
                      f"mk={mk:.2f}, feas={feas}", flush=True)
            else:
                rows.append({"start": st, "mode": mode, "legs": legs,
                             "ok": ok})
                if legs > best_partial[0]:
                    best_partial = (legs, perm, times, tofs, st, mode)
    wall = time.time() - t0
    info = {"problem": problem, "wall_s": round(wall, 1),
            "n_variants": len(args), "rows": rows,
            "best_partial_legs": best_partial[0],
            "best_partial_start": best_partial[4],
            "best_partial_mode": best_partial[5]}
    if best_full is not None:
        mk, perm, times, tofs, st, mode = best_full
        x_dec = list(times) + list(tofs) + [float(p) for p in perm]
        info.update({"best_mk": float(mk), "best_start": int(st),
                     "best_mode": mode, "best_perm_head": [int(p)
                     for p in perm[:10]]})
        p = Path(out) / f"{problem}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([{"decisionVector": list(x_dec),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    problem = sys.argv[1] if len(sys.argv) > 1 else "medium"
    n_starts = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    inst = (f"reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            f"Salesperson Problem/problems/"
            f"{'easy' if problem == 'small' else problem}.kttsp")
    print(json.dumps(sweep_variants(inst, problem=problem,
                                    n_starts=n_starts), indent=2))
