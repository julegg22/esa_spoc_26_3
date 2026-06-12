"""E-045 (script e576): Ch2 LARGE — pure global time-dependent greedy NN.

E-041 proved the 1048->424 gap is ordering/phasing: idle=0, median
min-cheap-tof 0.150d at EVERY epoch, ~37 cheap neighbors/node/epoch. The
static 4-component decomposition is a snapshot artifact. r1=424.62d over
1051 legs = 0.404d/leg avg — i.e. "take a short cheap hop at every step".
TGMA reached 424d (cluster+LKH); we never tried the natural algorithm.

The global epoch-aware OR-Tools rebuilds (E-042/E-043) minimize tof at
FIXED epochs, but reordering shifts realized epochs (the time-dependent
TSP trap) -> they diverged to 1400d+. A greedy NN avoids that trap by
construction: it commits to the realized epoch as it walks, always hopping
to the unvisited node with the SMALLEST feasible tof RIGHT NOW.

Algorithm (multi-start):
  - cur=start, t=0, visited={start}, exc_used=0.
  - each step: over cur's static-cheap candidates (unvisited), find the
    one with smallest feasible cheap tof (dv<=dv_thr) at epoch t -> hop.
  - if none cheap: allow ONE exc hop (dv<=dv_exc, budget 5) to nearest
    feasible cheap-candidate; else widen to ALL unvisited (capped) for an
    exc hop; else wait a few quanta and retry cheap.
  - record realized (departure, tof); continue till all 1051 visited.
  - strict walk_perm_chrono to validate + official kt.fitness.

GUARDED: best STRICT-feasible candidate -> /tmp ONLY; banks NOTHING.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
OUT = "/tmp/ch2_large_td_greedy_candidate.json"
CURRENT_BANK = 1048.9786
R1 = 424.62

WIN = float(os.environ.get("E576_WIN", "4.0"))      # short-hop window
STEPS = int(os.environ.get("E576_STEPS", "80"))     # tof scan resolution
WAIT_DT = float(os.environ.get("E576_WAITDT", "0.5"))
WAIT_MAX = int(os.environ.get("E576_WAITMAX", "10"))
WIDEN_CAP = int(os.environ.get("E576_WIDEN", "120"))  # all-unvisited probe cap
N_STARTS = int(os.environ.get("E576_NSTARTS", "12"))
STRICT = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)


def best_cheap_hop(kt, cands, cur, t, dv_cap):
    """Among cands (node ids), return (j, tof) with smallest feasible tof
    at epoch t under dv_cap, or (None, None)."""
    best_j, best_tof = None, None
    for j in cands:
        tof, dv = find_earliest_transfer(kt, cur, int(j), t, dv_cap, WIN, STEPS)
        if tof is not None and (best_tof is None or tof < best_tof):
            best_j, best_tof = int(j), tof
    return best_j, best_tof


def greedy_nn(kt, neigh, start, n):
    visited = np.zeros(n, dtype=bool)
    visited[start] = True
    order = [start]
    cur, t = start, 0.0
    exc_used = 0
    for _ in range(n - 1):
        cands = [j for j in neigh[cur] if not visited[j]]
        # 1) cheap hop among static-cheap neighbors
        j, tof = best_cheap_hop(kt, cands, cur, t, kt.dv_thr)
        if j is None and exc_used < kt.n_exc:
            # 2) exc hop among cheap neighbors
            j, tof = best_cheap_hop(kt, cands, cur, t, kt.dv_exc)
            if j is not None:
                exc_used += 1
        if j is None:
            # 3) wait a few quanta, retry cheap
            for w in range(1, WAIT_MAX + 1):
                tt = t + w * WAIT_DT
                if tt >= kt.max_time:
                    break
                j, tof = best_cheap_hop(kt, cands, cur, tt, kt.dv_thr)
                if j is not None:
                    t = tt
                    break
        if j is None and exc_used < kt.n_exc:
            # 4) widen: exc hop to nearest of ALL unvisited (capped)
            rest = np.where(~visited)[0]
            rest = rest[:WIDEN_CAP]
            j, tof = best_cheap_hop(kt, rest, cur, t, kt.dv_exc)
            if j is not None:
                exc_used += 1
        if j is None:
            return None, exc_used  # stuck — dead start
        order.append(j)
        visited[j] = True
        t += tof
        cur = j
    return order, exc_used


def strict_eval(kt, order):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in order]
    fit = kt.fitness(x)
    return dict(x=x, mk=float(fit[0]), feas=bool(kt.is_feasible(fit)),
                exc=exc, viols=list(fit[1:]))


def main():
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    neigh = [list(np.where(cheap[i])[0]) for i in range(n)]
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    deg = np.array([len(neigh[i]) for i in range(n)])

    # start candidates: bank start + lowest-degree nodes (hardest to reach
    # late, so commit early) + a few random
    starts = [perm0[0]]
    starts += list(np.argsort(deg)[:N_STARTS])
    rng = np.random.default_rng(0)
    starts += list(rng.integers(0, n, size=4))
    seen = set()
    starts = [s for s in (int(x) for x in starts)
              if not (s in seen or seen.add(s))][:N_STARTS]

    best = None
    print(f"[E-576] n={n} bank={CURRENT_BANK} r1={R1} starts={len(starts)}",
          flush=True)
    for si, s in enumerate(starts):
        t0 = time.time()
        order, exc = greedy_nn(kt, neigh, s, n)
        if order is None or len(set(order)) != n:
            print(f"[start {si} node={s}] STUCK exc={exc} "
                  f"({time.time()-t0:.0f}s)", flush=True)
            continue
        ev = strict_eval(kt, order)
        if ev is None:
            print(f"[start {si} node={s}] built but strict-REJECTED "
                  f"({time.time()-t0:.0f}s)", flush=True)
            continue
        tag = ""
        if ev["feas"] and (best is None or ev["mk"] < best["mk"]):
            best = ev
            tag = " *** NEW BEST"
        print(f"[start {si} node={s}] mk={ev['mk']:.2f} feas={ev['feas']} "
              f"exc={ev['exc']} viols={ev['viols']} "
              f"({time.time()-t0:.0f}s){tag}", flush=True)

    if best is None:
        print("[FINAL] no strict-feasible greedy tour built.", flush=True)
        return
    fit = kt.fitness(best["x"])
    feas = bool(kt.is_feasible(fit))
    perm = [int(round(v)) for v in best["x"][2 * (n - 1):]]
    covered = len(set(perm)) == n
    json.dump([{"decisionVector": best["x"], "problem": "large",
                "challenge": CHALLENGE}], open(OUT, "w"))
    if feas and best["mk"] < R1 and covered:
        gain = "*** BEATS r1=424 -> RANK 1 ***"
    elif feas and best["mk"] < CURRENT_BANK and covered:
        gain = "beats bank (still r2, no points)"
    else:
        gain = "no gain"
    print(f"\n[FINAL] best greedy mk={best['mk']:.2f} feas={feas} "
          f"covered={covered} (bank {CURRENT_BANK}, r1 {R1}) -> {gain}",
          flush=True)
    print(f"[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    main()
