"""Ch2 KTTSP — insertion LNS over TOP-K partial perms from findxfer-greedy.

E-022 banked makespan 145.8 d from start=34. Other partials reaching
43–44 legs (start=23, 16, 18, 27, 32, 42) may yield shorter makespans
via the same insertion process. Run all and bank the best.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from esa_spoc_26.ch2_findtransfer_greedy import _init_worker_fx
from esa_spoc_26.ch2_insert_lns import insert_lns
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def main(inst, problem="small",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         top_k=8):
    kt = KTTSP(inst)
    n = kt.n
    # Re-derive top-K partials from greedy_findxfer per start
    print("Greedy partial computation (mp pool)...", flush=True)
    import multiprocessing as mp

    from esa_spoc_26.ch2_findtransfer_greedy import _worker_search
    t0 = time.time()
    args = [(st, 12.0, 120) for st in range(n)]
    partials = []  # (legs, start, perm, missing)
    with mp.Pool(4, initializer=_init_worker_fx, initargs=(inst,)) as pool:
        for st, perm, _times, _tofs, _dvs, _ok in pool.imap_unordered(
                _worker_search, args):
            legs = len(perm) - 1
            missing = sorted(set(range(n)) - set(perm))
            partials.append((legs, st, perm, missing))
    greedy_t = time.time() - t0

    partials.sort(reverse=True)   # by legs descending
    print(f"top {top_k} partials by legs:", flush=True)
    for legs, st, _, missing in partials[:top_k]:
        print(f"  start={st}, legs={legs}, missing={missing}", flush=True)

    best = None  # (makespan, perm, times, tofs, dvs, start)
    insert_t = 0.0
    for legs, st, perm, missing in partials[:top_k]:
        if len(missing) > 4:  # too many to enumerate
            continue
        t1 = time.time()
        print(f"\nInserting {missing} into partial(start={st}, legs={legs})",
              flush=True)
        full_perm, parts, n_feas = insert_lns(
            kt, perm, missing, verbose=False)
        insert_t += time.time() - t1
        if full_perm is None:
            print(f"  no feasible insertion (n_feas={n_feas})", flush=True)
            continue
        times, tofs, dvs = parts
        mk = times[-1] + tofs[-1]
        print(f"  BEST INSERTION: mk={mk:.2f}, n_feas={n_feas}", flush=True)
        if best is None or mk < best[0]:
            best = (mk, full_perm, times, tofs, dvs, st)

    info = {"problem": problem, "n": n, "greedy_s": round(greedy_t, 1),
            "insert_s": round(insert_t, 1),
            "rank3_small_d": 111.76,
            "top_k_partial_legs":
            [(p[0], p[1]) for p in partials[:top_k]]}
    if best is None:
        info["feasible"] = False
        return info
    mk, full_perm, times, tofs, dvs, src_start = best
    x = times + tofs + [float(v) for v in full_perm]
    f = kt.fitness(x)
    feas = kt.is_feasible(f)
    info.update({"source_start": src_start, "makespan_d": round(mk, 3),
                 "fitness": list(f), "feasible": feas,
                 "perm": [int(p) for p in full_perm]})
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
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    print(json.dumps(main(inst, top_k=k), indent=2))
