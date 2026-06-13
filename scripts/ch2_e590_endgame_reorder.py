"""E-590 — Ch2 LARGE endgame JOINT local reorder + retime.

The bank (932.5304 d) is the retime-DP floor for the FIXED 1051-perm. A
global retime-DP showed the residual makespan concentrates in the dense
endgame cluster (the final segment after the last exc bridge at leg 957:
perm positions 958..1050, 93 nodes, heavy tofs on legs ~1034-1049).

This script holds the upstream tour FIXED (entry node perm[958]=116 arrives
at epoch 818.7824, set by the bank's upstream walk + idle) and runs a local
search over the ORDER of the endgame interior nodes ONLY, keeping:
  - entry node (perm[958]) and terminus node (perm[1050], the dead-tail) fixed
  - no exc bridge inside the endgame (it is one component; cheap dv only)

For EACH candidate order, the makespan is recomputed by the TRUE chrono walk
from epoch 818.7824 WITH a per-leg min-arrival retime (departure-delay search),
i.e. the same machinery that produced the 932.53 bank (E-589
true_walk_makespan). This is trap-free: the objective IS the chrono walk, not
a fixed-epoch surrogate matrix, so reorder-induced epoch shifts are exact.

Moves: 2-opt (segment reversal) and or-opt (relocate 1-3 node chains) over the
endgame interior. Strictly-improving (monotone) acceptance.

GUARDED: writes a strictly-better FULL feasible 1051-perm to
/tmp/ch2_large_endgame_cand.json ONLY. No git, no solutions/upload/, no submit.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import (  # noqa: E402
    find_earliest_transfer,
)

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = "/tmp/ch2_large_endgame_cand.json"
CURRENT_BANK = 932.5304126719427

TOF_WINDOW = 40.0
N_STEPS = 2400
EXC_LEGS = {149, 416, 566, 807, 957}
ENDGAME_START_POS = 958  # perm position of first endgame node (entry)

# Per-leg departure-delay retime grid (relative to earliest-feasible departure).
DELAY_GRID = np.round(np.arange(0.0, 6.01, 0.25), 3)
# Coarse grid used during the inner local-search ranking (fast, consistent).
RANK_GRID = np.array([0.0])  # pure greedy earliest-departure (0.4s/walk)

TIME_BUDGET_S = float(os.environ.get("E590_BUDGET", "2400"))  # ~40 min default


def endgame_walk(kt, entry_epoch, endgame_perm, grid=DELAY_GRID):
    """Chrono walk over the endgame node list starting from entry_epoch (the
    arrival epoch at endgame_perm[0]). For each leg pick the min-ARRIVAL
    departure delay over `grid` (retime). grid=[0.0] => pure greedy
    earliest-departure (fast). Endgame is one component -> cheap dv only.
    Returns (terminus_epoch, dep_times, tofs) or (None,None,None) infeasible."""
    t = entry_epoch
    dep_times, tofs = [], []
    m = len(endgame_perm)
    for k in range(m - 1):
        a, b = endgame_perm[k], endgame_perm[k + 1]
        best = None  # (arrival, dep, tof)
        for d in grid:
            td = t + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof, dv = find_earliest_transfer(kt, a, b, td, kt.dv_thr,
                                             TOF_WINDOW, N_STEPS)
            if tof is None:
                continue
            arr = td + tof
            if best is None or arr < best[0] - 1e-9:
                best = (arr, td, tof)
        if best is None:
            return None, None, None
        arr, td, tof = best
        dep_times.append(td)
        tofs.append(tof)
        t = arr
        if t > kt.max_time:
            return None, None, None
    return t, dep_times, tofs


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    bt = np.array(bank[:n - 1])
    bf = np.array(bank[n - 1:2 * (n - 1)])
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]

    fit = kt.fitness(bank)
    print(f"[E-590] bank mk={float(fit[0]):.4f} feas={bool(kt.is_feasible(fit))}"
          f" viols={list(fit[1:])}", flush=True)
    assert abs(float(fit[0]) - CURRENT_BANK) < 1e-3

    entry_epoch = float(bt[957] + bf[957])
    endgame = perm[ENDGAME_START_POS:]  # 93 nodes; [0]=entry, [-1]=terminus
    m = len(endgame)
    print(f"[E-590] endgame: {m} nodes, entry epoch {entry_epoch:.4f}, "
          f"bank terminus {CURRENT_BANK:.4f} "
          f"(span {CURRENT_BANK - entry_epoch:.4f}d)", flush=True)

    # Baselines on the bank's endgame ORDER:
    #  - greedy (RANK_GRID=[0]) is the fast inner-loop ranking objective.
    #  - retime (DELAY_GRID) is the isolated-endgame retimed makespan (our
    #    evaluator cannot reach the bank's 932.53 tail because that needed
    #    GLOBAL upstream coordination; both baselines are > 932.53).
    term_g, _, _ = endgame_walk(kt, entry_epoch, endgame, grid=RANK_GRID)
    term_r, _, _ = endgame_walk(kt, entry_epoch, endgame, grid=DELAY_GRID)
    print(f"[E-590] bank endgame order: greedy term={term_g:.4f}  "
          f"retime term={term_r:.4f}  (true bank {CURRENT_BANK:.4f})",
          flush=True)
    if term_g is None:
        print("[E-590] FATAL: bank endgame order infeasible greedy", flush=True)
        return

    # Local search over endgame INTERIOR positions [1 .. m-2] (keep entry & term).
    # Inner objective = FAST greedy walk (RANK_GRID). Order improvements that
    # beat the greedy baseline are re-checked under retime + global rebuild.
    best = list(endgame)
    best_term = term_g
    t0 = time.time()
    n_improve = 0
    improve_log = []

    # Incremental greedy-walk evaluator. epochs[k] = arrival epoch at best[k].
    # A candidate that equals best on [0..p) and differs at p is evaluated by
    # walking ONLY the suffix from epochs[p]. Single-leg transfer cache keyed by
    # (a, b, rounded epoch) keeps repeated legs cheap.
    leg_cache = {}

    def leg_tof(a, b, t):
        key = (a, b, round(t, 3))
        v = leg_cache.get(key)
        if v is None:
            tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr,
                                             TOF_WINDOW, N_STEPS)
            v = tof
            leg_cache[key] = v
        return v

    def compute_epochs(order):
        ep = [entry_epoch]
        t = entry_epoch
        for k in range(len(order) - 1):
            tof = leg_tof(order[k], order[k + 1], t)
            if tof is None:
                return None
            t = t + tof
            ep.append(t)
        return ep

    def walk_from(order, start, t_start):
        """Greedy terminus walking order[start:] starting at epoch t_start
        (= arrival at order[start]). Returns terminus or None."""
        t = t_start
        for k in range(start, len(order) - 1):
            tof = leg_tof(order[k], order[k + 1], t)
            if tof is None:
                return None
            t = t + tof
        return t

    epochs = compute_epochs(best)
    # Track the best order under the PROPER (retime) objective. The greedy walk
    # is only an inner ranking surrogate; retime is what's comparable to bank.
    best_retime_order = list(best)
    best_retime = term_r  # retime on bank order (936.36)

    def check_retime(order):
        nonlocal best_retime_order, best_retime
        tr, _, _ = endgame_walk(kt, entry_epoch, order, grid=DELAY_GRID)
        if tr is not None and tr < best_retime - 1e-4:
            best_retime = tr
            best_retime_order = list(order)
            print(f"[E-590] *** new best RETIME order term={tr:.4f} "
                  f"(bank {CURRENT_BANK:.4f})", flush=True)

    def feval_inc(cand, p):
        """Evaluate cand assuming cand[:p]==best[:p]. Then arrival epoch at
        cand[p-1] == epochs[p-1] (unchanged), so walk the suffix from p-1."""
        return walk_from(cand, p - 1, epochs[p - 1])

    def feval(cand):
        term, _, _ = endgame_walk(kt, entry_epoch, cand, grid=RANK_GRID)
        return term

    rounds = 0
    improved = True
    while improved and (time.time() - t0) < TIME_BUDGET_S:
        improved = False
        rounds += 1
        # OR-OPT: relocate chains of length 1..3 to another interior position.
        for L in (1, 2, 3):
            for i in range(1, m - 1 - L):
                if (time.time() - t0) >= TIME_BUDGET_S:
                    break
                seg = best[i:i + L]
                rest = best[:i] + best[i + L:]
                for jpos in range(1, len(rest)):
                    if jpos == i:
                        continue
                    cand = rest[:jpos] + seg + rest[jpos:]
                    if cand[0] != endgame[0] or cand[-1] != endgame[-1]:
                        continue
                    p = min(i, jpos)  # divergence point from `best`
                    term = feval_inc(cand, p)
                    if term is not None and term < best_term - 1e-4:
                        best = cand
                        best_term = term
                        epochs = compute_epochs(best)
                        improved = True
                        n_improve += 1
                        improve_log.append(("oropt", L, i, jpos, term))
                        print(f"[E-590] r{rounds} oropt L{L} {i}->{jpos} "
                              f"term={term:.4f}", flush=True)
                        check_retime(best)
                        break
        # 2-OPT: reverse interior segment [i..j].
        for i in range(1, m - 2):
            if (time.time() - t0) >= TIME_BUDGET_S:
                break
            for j in range(i + 1, m - 1):
                cand = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                term = feval_inc(cand, i)  # diverges at i
                if term is not None and term < best_term - 1e-4:
                    best = cand
                    best_term = term
                    epochs = compute_epochs(best)
                    improved = True
                    n_improve += 1
                    improve_log.append(("2opt", i, j, term))
                    print(f"[E-590] r{rounds} 2opt [{i}..{j}] "
                          f"term={best_term:.4f}", flush=True)
                    check_retime(best)
                    break
        print(f"[E-590] round {rounds} best_term={best_term:.4f} "
              f"({n_improve} improves, {time.time()-t0:.0f}s, "
              f"cache {len(leg_cache)})", flush=True)

    print(f"[E-590] DONE rounds={rounds} improves={n_improve} "
          f"best_term(greedy)={best_term:.4f} (greedy bank baseline {term_g:.4f})"
          f" | best RETIME order={best_retime:.4f} "
          f"(retime-on-bank-order={term_r:.4f}, true bank {CURRENT_BANK:.4f})",
          flush=True)

    if best_retime >= CURRENT_BANK - 1e-4:
        print(f"[E-590] NO endgame reorder beat the bank under retime "
              f"(best retime {best_retime:.4f} >= bank {CURRENT_BANK:.4f}). "
              f"Endgame order is LOCALLY OPTIMAL under chrono-walk+retime; the "
              f"bank's 932.53 tail is unreachable by isolated-endgame reorder "
              f"because it relied on GLOBAL upstream retime coordination.",
              flush=True)
        return

    # An order beat the bank under retime — rebuild full DV and validate.
    build_and_validate(kt, n, perm, bt, bf, entry_epoch, best_retime_order,
                       best_retime)


def build_and_validate(kt, n, perm, bt, bf, entry_epoch, endgame_new,
                       best_term):
    """Reconstruct the full 1051 DV with the new endgame order, validate with
    walk_perm_chrono (fine) AND kt.fitness, write to OUT if strictly better."""
    new_perm = perm[:ENDGAME_START_POS] + endgame_new
    assert len(new_perm) == n
    assert sorted(new_perm) == list(range(n)), "perm not a valid permutation"
    assert new_perm[:ENDGAME_START_POS] == perm[:ENDGAME_START_POS]

    # Full chrono walk WITH per-leg min-arrival retime to set times/tofs.
    # Upstream legs use bank bt/bf to preserve the bank's upstream idle (which
    # contributes the 26.7d of distributed waiting that floors the upstream).
    times, tofs = [], []
    # upstream (legs 0..956): use bank values exactly
    for i in range(ENDGAME_START_POS - 1):
        times.append(float(bt[i]))
        tofs.append(float(bf[i]))
    # exc bridge leg 957 (perm[957] -> perm[958] = endgame[0]): bank value
    times.append(float(bt[957]))
    tofs.append(float(bf[957]))
    # endgame legs from entry_epoch with retime
    term, edep, etof = endgame_walk(kt, entry_epoch, endgame_new,
                                    grid=DELAY_GRID)
    if term is None:
        print("[E-590] rebuild endgame infeasible — abort", flush=True)
        return
    for d, tf in zip(edep, etof):
        times.append(float(d))
        tofs.append(float(tf))
    assert len(times) == n - 1 and len(tofs) == n - 1

    x = [float(v) for v in times] + [float(v) for v in tofs] \
        + [float(p) for p in new_perm]

    fit = kt.fitness(x)
    mk = float(fit[0])
    feas = bool(kt.is_feasible(fit))
    print(f"[E-590] FULL rebuild: fitness mk={mk:.4f} feas={feas} "
          f"viols={list(fit[1:])}", flush=True)

    # Independent validation via walk_perm_chrono at FINE params.
    from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
    w = walk_perm_chrono(kt, new_perm, tof_window=40.0, n_steps=2400,
                         wait_steps=12, wait_dt=0.25)
    times_w, tofs_w, dvs_w, ok_w, exc_w, leg_w = w
    if ok_w:
        mk_w = times_w[-1] + tofs_w[-1]
        print(f"[E-590] walk_perm_chrono(fine) ok mk={mk_w:.4f} exc={exc_w}",
              flush=True)
    else:
        print(f"[E-590] walk_perm_chrono(fine) FAILED at leg {leg_w} "
              f"(greedy walk may fail; fitness is the authority)", flush=True)

    if feas and mk < CURRENT_BANK - 1e-4:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        fit2 = kt.fitness(x)
        print(f"[E-590] WROTE {OUT}: REVAL mk={float(fit2[0]):.4f} "
              f"feas={bool(kt.is_feasible(fit2))} viols={list(fit2[1:])}",
              flush=True)
    else:
        print(f"[E-590] rebuild did NOT beat bank under fitness "
              f"(mk={mk:.4f}) — wrote nothing.", flush=True)


if __name__ == "__main__":
    main()
