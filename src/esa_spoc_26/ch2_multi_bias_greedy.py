"""Ch2 KTTSP — multi-bias greedy + cluster-insertion sweep.

Sweep `greedy_findxfer` across several bias variants:
- A: cheap-first (default) — pick min-arrival cheap j; fallback exception.
- B: cheap-only-strict — never use exception unless no cheap j feasible
     under longer wait/tof window.
- C: exception-eager-early — use exceptions early to bank cluster bridges.
- D: wider tof_window (24, 30 d) for legs that benefit from longer cheap
     transfers.
- E: shorter tof_window (6, 8 d) for tighter makespan per leg.

For each variant × 49 starts (parallel mp.Pool), record best partial.
Then for each partial: run insertion-LNS over k ≤ 4 missing. Bank
the best feasible full tour across all variants.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import (
    _WORKER_KT_FX,
    _init_worker_fx,
    find_earliest_transfer,
)
from esa_spoc_26.ch2_insert_lns import insert_lns
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def greedy_biased(kt, start, tof_window=12.0, n_steps=120,
                  bias="cheap-first", wait_steps=4, wait_dt=0.5):
    """Bias variants for the per-step pick. See module docstring."""
    n = kt.n
    cur, t = start, 0.0
    unvis = set(range(n)) - {start}
    perm, times, tofs, dvs = [start], [], [], []
    exc = 0
    while unvis:
        best = None  # (rank-key, j, td, tof, dv, is_exc)
        candidates = []  # (j, tof, dv, is_exc, arr)
        for j in unvis:
            tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_thr,
                                              tof_window, n_steps)
            if tof is not None:
                candidates.append((j, tof, dv, False, t + tof))
        # Try exceptions too if budget left
        if exc < kt.n_exc:
            for j in unvis:
                if any(c[0] == j and not c[3] for c in candidates):
                    continue  # already have a cheap option for this j
                tof, dv = find_earliest_transfer(kt, cur, j, t, kt.dv_exc,
                                                  tof_window, n_steps)
                if tof is not None:
                    candidates.append((j, tof, dv, True, t + tof))
        if not candidates:
            # try waiting
            found = False
            for w in range(1, wait_steps + 1):
                t_try = t + w * wait_dt
                if t_try >= kt.max_time:
                    break
                for j in unvis:
                    tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                     kt.dv_thr,
                                                     tof_window, n_steps)
                    if tof is not None:
                        candidates.append((j, tof, dv, False, t_try + tof))
                        t = t_try
                        found = True
                        break
                if found:
                    break
            if not found and exc < kt.n_exc:
                for w in range(1, wait_steps + 1):
                    t_try = t + w * wait_dt
                    if t_try >= kt.max_time:
                        break
                    for j in unvis:
                        tof, dv = find_earliest_transfer(kt, cur, j, t_try,
                                                          kt.dv_exc,
                                                          tof_window,
                                                          n_steps)
                        if tof is not None:
                            candidates.append((j, tof, dv, True,
                                               t_try + tof))
                            t = t_try
                            found = True
                            break
                    if found:
                        break
        if not candidates:
            return perm, times, tofs, dvs, False
        # Choose by bias
        if bias == "cheap-first":
            cheap = [c for c in candidates if not c[3]]
            pool = cheap if cheap else candidates
            best = min(pool, key=lambda c: (c[4], c[2]))
        elif bias == "cheap-strict":
            cheap = [c for c in candidates if not c[3]]
            if cheap:
                best = min(cheap, key=lambda c: (c[4], c[2]))
            else:
                best = min(candidates, key=lambda c: (c[4], c[2]))
        elif bias == "exception-eager":
            # If we have any exception that gives a much shorter arrival,
            # prefer it
            cheap = [c for c in candidates if not c[3]]
            exc_c = [c for c in candidates if c[3]]
            if exc_c and (not cheap
                          or min(c[4] for c in exc_c)
                          < min(c[4] for c in cheap) - 2.0):
                best = min(exc_c, key=lambda c: (c[4], c[2]))
            elif cheap:
                best = min(cheap, key=lambda c: (c[4], c[2]))
            else:
                best = min(candidates, key=lambda c: (c[4], c[2]))
        elif bias == "min-dv":
            cheap = [c for c in candidates if not c[3]]
            pool = cheap if cheap else candidates
            best = min(pool, key=lambda c: (c[2], c[4]))
        else:
            cheap = [c for c in candidates if not c[3]]
            pool = cheap if cheap else candidates
            best = min(pool, key=lambda c: (c[4], c[2]))
        j, tof, dv, is_exc, _arr = best
        times.append(t)
        tofs.append(tof)
        dvs.append(dv)
        perm.append(j)
        if is_exc:
            exc += 1
        t = t + tof
        unvis.discard(j)
        cur = j
    return perm, times, tofs, dvs, True


def _worker_biased(args):
    st, tw, ns, bias = args
    kt = _WORKER_KT_FX[0]
    perm, times, tofs, dvs, ok = greedy_biased(
        kt, start=st, tof_window=tw, n_steps=ns, bias=bias)
    return st, bias, tw, perm, times, tofs, dvs, ok


def sweep(inst, problem="small",
          out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    n = kt.n
    variants = []
    for tw in [8.0, 12.0, 18.0, 24.0]:
        for bias in ["cheap-first", "cheap-strict",
                     "exception-eager", "min-dv"]:
            for st in range(n):
                variants.append((st, tw, 120, bias))
    print(f"Greedy sweep: {len(variants)} variants "
          f"({len(variants)/n:.0f} per start, {n} starts).", flush=True)
    import multiprocessing as mp
    t0 = time.time()
    best_partial = None   # (legs, t_final, st, perm, times, tofs, dvs, ok, bias, tw)
    full_tours = []       # (mk, st, bias, tw, perm, times, tofs, dvs)
    with mp.Pool(3, initializer=_init_worker_fx, initargs=(inst,)) as pool:
        for st, bias, tw, perm, times, tofs, dvs, ok in pool.imap_unordered(
                _worker_biased, variants, chunksize=4):
            legs = len(perm) - 1
            if ok and legs == n - 1:
                mk = times[-1] + tofs[-1]
                full_tours.append((mk, st, bias, tw, perm, times,
                                   tofs, dvs))
            else:
                if best_partial is None or legs > best_partial[0]:
                    best_partial = (legs, st, bias, tw, perm, times,
                                    tofs, dvs)
    wall = time.time() - t0
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "n_variants": len(variants),
            "n_full_tours_found": len(full_tours),
            "rank3_small_d": 111.76}
    if full_tours:
        full_tours.sort(key=lambda x: x[0])
        info["full_tours_top5"] = [
            {"mk": round(t[0], 3), "start": t[1], "bias": t[2], "tw": t[3]}
            for t in full_tours[:5]
        ]
        # Polish each top-5 with the existing 2-opt-style chronological walk:
        # actually just check fitness on the top, replace banked if better.
        for _mk, st, bias, tw, perm, times, tofs, _dvs in full_tours[:5]:
            x = times + tofs + [float(v) for v in perm]
            f = kt.fitness(x)
            feas = kt.is_feasible(f)
            if feas and f[0] < 143.79:
                p = Path(out) / "small.json"
                p.write_text(json.dumps([{"decisionVector": list(x),
                                          "problem": problem,
                                          "challenge": CHALLENGE}]))
                info["replaced_banked_with"] = {"mk": float(f[0]),
                                                "start": int(st),
                                                "bias": bias, "tw": float(tw)}
                break
    # also: from top partials, try insertion-LNS on the best ones (k ≤ 4)
    return info


def lns_on_partials(inst, partials, k_max=4):
    """For a list of partial perms (legs, st, bias, tw, perm, ...),
    run insertion-LNS on those with k ≤ k_max missing nodes. Return
    best feasible full tour found."""
    kt = KTTSP(inst)
    n = kt.n
    best = None
    for _legs, st, bias, tw, perm, _t, _tf, _dv in partials:
        missing = sorted(set(range(n)) - set(perm))
        if not (1 <= len(missing) <= k_max):
            continue
        print(f"  LNS on (start={st}, bias={bias}, tw={tw}, "
              f"missing={missing})...", flush=True)
        t0 = time.time()
        full_perm, parts, n_feas = insert_lns(kt, perm, missing,
                                              verbose=False)
        if full_perm is None:
            print(f"    no feasible insertion ({n_feas})", flush=True)
            continue
        times, tofs, _ = parts
        mk = times[-1] + tofs[-1]
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        wall = time.time() - t0
        print(f"    mk={mk:.2f}, feas={feas}, wall={wall:.1f}s", flush=True)
        if feas and (best is None or mk < best[0]):
            best = (mk, full_perm, times, tofs, st, bias, tw)
    return best


def main(inst="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
              "Salesperson Problem/problems/easy.kttsp",
         problem="small",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    print("STEP 1: greedy sweep (multi-bias)", flush=True)
    info = sweep(inst, problem, out)
    print(json.dumps(info, indent=2), flush=True)

    # Reconstruct partials list from a fresh sweep for LNS
    # (we don't store them in sweep's return; do a second pass)
    print("\nSTEP 2: insertion-LNS on top-K partials", flush=True)
    kt = KTTSP(inst)
    n = kt.n
    variants = []
    for tw in [8.0, 12.0, 18.0, 24.0]:
        for bias in ["cheap-first", "cheap-strict",
                     "exception-eager", "min-dv"]:
            for st in range(n):
                variants.append((st, tw, 120, bias))
    import multiprocessing as mp
    partials = []
    with mp.Pool(3, initializer=_init_worker_fx, initargs=(inst,)) as pool:
        for st, bias, tw, perm, times, tofs, dvs, ok in pool.imap_unordered(
                _worker_biased, variants, chunksize=4):
            legs = len(perm) - 1
            if not (ok and legs == n - 1):
                partials.append((legs, st, bias, tw, perm, times, tofs, dvs))
    partials.sort(reverse=True)  # by legs descending
    print(f"  total partials: {len(partials)}; top-5 legs: "
          f"{[p[0] for p in partials[:5]]}", flush=True)
    best = lns_on_partials(inst, partials[:20], k_max=4)
    if best:
        mk, full_perm, times, tofs, st, bias, tw = best
        info["lns_best"] = {"mk": float(mk), "start": int(st),
                            "bias": bias, "tw": float(tw)}
        x = times + tofs + [float(v) for v in full_perm]
        f = kt.fitness(x)
        feas = kt.is_feasible(f)
        if feas and f[0] < 143.79:
            p = Path(out) / "small.json"
            p.write_text(json.dumps([{"decisionVector": list(x),
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            info["replaced_banked"] = True
            info["replaced_banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
