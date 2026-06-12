"""E-046 (script e577): Ch2 LARGE — MONOTONE time-dependent Or-opt.

E-042 isolated the lever: the surrogate global solve (E-572) and the
full-resolve fixpoint (E-573) both fail because they optimize a FROZEN-epoch
surrogate / are non-monotone and diverge; greedy NN (E-576) is the 1048
incumbent. The one untried principled attack: lower the REALIZED makespan
by LOCAL moves, accepting only verified strict improvements — monotone, so
it CANNOT diverge.

Move: Or-opt relocation of a single node v to an insertion slot (a,b) where
a or b is a cheap neighbor of v (neighbor-list restricted -> O(n*deg) moves
/ pass, not O(n^2)). Two-stage evaluation for tractability:
  1) SCREEN with a local tof delta at current epochs (cheap, approximate).
  2) For the best-screened improving moves, APPLY and do a FULL chrono
     re-walk; accept only if realized makespan strictly drops AND the walk
     stays feasible (<=5 exc, all covered). Else revert.
First-improvement with periodic re-anchor; checkpoint best feasible -> /tmp.

GUARDED: writes best feasible candidate to /tmp ONLY; banks NOTHING.
BINARY caveat (E-042): only realized mk < r1=424.62 changes the rank; this
is a low-point-EV frontier probe on otherwise-idle cores.
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
OUT = "/tmp/ch2_large_monotone_candidate.json"
CURRENT_BANK = 1048.9786
R1 = 424.62

WIN = float(os.environ.get("E577_WIN", "3.5"))
STEPS = int(os.environ.get("E577_STEPS", "24"))
TL = float(os.environ.get("E577_TL", "36000"))     # 10h default
SCREEN_K = int(os.environ.get("E577_SCREENK", "12"))  # verify top-K screened
# E-041: 654 legs >0.5d hold ALL 617d of excess. Only relocate nodes whose
# incident legs are long — cuts the screen loop ~3x and targets the excess.
LONG_THR = float(os.environ.get("E577_LONGTHR", "0.6"))
WALK = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)


def walk(kt, perm):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, perm, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return dict(times=times, tofs=tofs, x=x, mk=float(fit[0]),
                feas=bool(kt.is_feasible(fit)), exc=exc, viols=list(fit[1:]))


def screen_tof(kt, i, j, t):
    tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_thr, WIN, STEPS)
    if tof is None:
        tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_exc, WIN, STEPS)
    return tof  # may be None


def main():
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    neigh = [set(np.where(cheap[i])[0]) for i in range(n)]
    bank = json.load(open(BANK))[0]["decisionVector"]
    order = [int(round(v)) for v in bank[2 * (n - 1):]]

    cur = walk(kt, order)
    assert cur is not None and cur["feas"], "bank not feasibly walkable"
    print(f"[E-577] n={n} start mk={cur['mk']:.3f} feas={cur['feas']} "
          f"exc={cur['exc']} (bank {CURRENT_BANK}, r1 {R1})", flush=True)
    best_mk = cur["mk"]

    t_start = time.time()
    npass = 0
    while time.time() - t_start < TL:
        npass += 1
        pos = {node: k for k, node in enumerate(order)}
        times = cur["times"]
        tofs = cur["tofs"]
        # screen all neighbor-restricted single-node relocations
        cands = []  # (screened_delta, v, insert_after_pos)
        for p in range(1, n - 1):           # don't move the fixed start
            if max(tofs[p - 1], tofs[p]) < LONG_THR:
                continue                    # only relocate long-leg nodes
            v = order[p]
            a, b = order[p - 1], order[p + 1]
            t_a = times[p - 1]
            # cost removed around v at its current slot
            rem = tofs[p - 1] + tofs[p]      # a->v + v->b
            new_ab = screen_tof(kt, a, b, t_a)
            if new_ab is None:
                continue
            gain_remove = rem - new_ab       # >0 means slot a,b cheaper w/o v
            # try inserting v between cheap-neighbor consecutive pairs
            for c in neigh[v]:
                q = pos.get(int(c))
                if q is None or q >= n - 1 or abs(q - p) <= 1:
                    continue
                cc, dd = order[q], order[q + 1]
                t_c = times[q]
                old_cd = tofs[q]
                cv = screen_tof(kt, cc, v, t_c)
                if cv is None:
                    continue
                vd = screen_tof(kt, v, dd, t_c + cv)
                if vd is None:
                    continue
                add_insert = cv + vd - old_cd
                delta = add_insert - gain_remove  # <0 => screened improvement
                if delta < -1e-3:
                    cands.append((delta, p, q))
        if not cands:
            print(f"[pass {npass}] no screened-improving move — converged.",
                  flush=True)
            break
        cands.sort(key=lambda z: z[0])
        applied = False
        for delta, p, q in cands[:SCREEN_K]:
            v = order[p]
            new_order = order[:p] + order[p + 1:]
            qq = q if q < p else q - 1            # index shift after removal
            new_order = new_order[:qq + 1] + [v] + new_order[qq + 1:]
            if len(set(new_order)) != n:
                continue
            w = walk(kt, new_order)
            if w is None or not w["feas"]:
                continue
            if w["mk"] < cur["mk"] - 1e-4:
                order = new_order
                cur = w
                applied = True
                if cur["mk"] < best_mk:
                    best_mk = cur["mk"]
                    json.dump([{"decisionVector": cur["x"], "problem": "large",
                                "challenge": CHALLENGE}], open(OUT, "w"))
                print(f"[pass {npass}] ACCEPT relocate node{v} "
                      f"p{p}->q{q} screen={delta:.3f} -> mk={cur['mk']:.3f} "
                      f"exc={cur['exc']} ({time.time()-t_start:.0f}s)",
                      flush=True)
                break
        if not applied:
            print(f"[pass {npass}] {len(cands)} screened, none verified — "
                  f"converged. ({time.time()-t_start:.0f}s)", flush=True)
            break

    print(f"\n[FINAL] best feasible mk={best_mk:.3f} "
          f"(bank {CURRENT_BANK}, r1 {R1})", flush=True)
    if best_mk < R1:
        print("[FINAL] *** BEATS r1 -> RANK 1 ***", flush=True)
    elif best_mk < CURRENT_BANK - 1e-4:
        print(f"[FINAL] beats bank by {CURRENT_BANK-best_mk:.3f}d "
              f"(still r2 unless <424 — no points)", flush=True)
    else:
        print("[FINAL] no improvement over bank.", flush=True)
    print(f"[OUT] {OUT}", flush=True)


if __name__ == "__main__":
    main()
