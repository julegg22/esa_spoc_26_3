"""E-592 — Ch2 LARGE trap-free Or-opt relocation of the 14 epoch-locked
heavy source nodes, evaluated by the TRUE full chrono walk WITH per-leg
min-arrival retime (delay grid) and scored by kt.fitness.

Background (E-591 diagnostic, /tmp/ch2_large_epoch_conn.json):
  14 EPOCH-LOCKED heavy source nodes [181,261,277,293,300,347,487,529,
  665,684,783,910,971,1040] are cheap-out at SOME epoch but the chrono
  walk currently reaches them at a bad epoch. Pure reorder hits the
  epoch-shift trap, so the ONLY trap-free test is a FULL re-walk with
  waiting/retime after every candidate move, accepting strict full-walk
  improvements only.

Evaluator: per-leg min-ARRIVAL departure-delay search over DELAY_GRID
(the same retime machinery that floors the bank). The exception bridges
must stay on the SAME 5 ordered (src->dst) adjacencies; a move that would
break or duplicate a bridge is rejected. The full DV is scored by
kt.fitness (authoritative).

INCREMENTAL: a single-node Or-opt move from position i to j touches the
order only from min(i,j) onward; legs before that are identical, so we
reuse cached prefix dep/arr and only re-walk the suffix. A per-leg cache
keyed by (a,b,round(epoch,3)) makes repeated legs cheap.

GUARDED: writes a strictly-better FULL feasible 1051-perm DV to
/tmp/ch2_large_epoch_relocate_cand.json ONLY. No git, no solutions/upload/,
no submit. ~45 min wall budget.
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
OUT = "/tmp/ch2_large_epoch_relocate_cand.json"
CURRENT_BANK = 932.5304126719427

TOF_WINDOW = 40.0
N_STEPS = 2400
# Ordered exc-bridge adjacencies (src node -> dst node) in the bank perm.
# These MUST be preserved (same 5 directed pairs) for a move to be legal.
EXC_PAIRS_LEGS = [149, 416, 566, 807, 957]

DELAY_GRID = np.round(np.arange(0.0, 6.01, 0.25), 3)

TIME_BUDGET_S = float(os.environ.get("E592_BUDGET", "2700"))  # ~45 min

LOCKED = [181, 261, 277, 293, 300, 347, 487, 529, 665, 684, 783, 910, 971,
          1040]


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]

    fit = kt.fitness(bank)
    print(f"[E-592] BANK fitness mk={float(fit[0]):.6f} "
          f"feas={bool(kt.is_feasible(fit))} viols={list(fit[1:])}", flush=True)
    assert abs(float(fit[0]) - CURRENT_BANK) < 1e-3
    assert sorted(perm) == list(range(n))

    # The 5 directed exc adjacencies that must remain (and only these may be
    # exc) — identified by the bank perm at the exc legs.
    exc_pairs = {(perm[lg], perm[lg + 1]) for lg in EXC_PAIRS_LEGS}
    print(f"[E-592] exc pairs (must preserve): {sorted(exc_pairs)}", flush=True)

    leg_cache = {}

    def leg_tof(a, b, t, is_exc):
        thr = kt.dv_exc if is_exc else kt.dv_thr
        key = (a, b, round(t, 3), is_exc)
        v = leg_cache.get(key)
        if v is None:
            tof, _ = find_earliest_transfer(kt, a, b, t, thr,
                                            TOF_WINDOW, N_STEPS)
            v = tof
            leg_cache[key] = v
        return v

    def pair_is_exc(a, b):
        return (a, b) in exc_pairs

    # ref_arr[k] = greedy arrival epoch at best_perm[k]; set before search.
    ref_arr = {"v": None}

    def greedy_term_from(p, start, t_start, abort_floor=None):
        """FAST greedy (delay=0) terminus of p[start:] from epoch t_start at
        p[start]. Used as the inner screening objective. None if infeasible.
        Early-abort: if at any position k the running epoch already exceeds the
        reference greedy arrival at the SAME position by >= 0 (i.e. this path is
        already behind the incumbent and the tail tofs are >=0), and
        abort_floor is set, bail with None — it cannot beat the incumbent."""
        t = t_start
        ra = ref_arr["v"]
        for k in range(start, len(p) - 1):
            a, b = p[k], p[k + 1]
            tof = leg_tof(a, b, t, pair_is_exc(a, b))
            if tof is None:
                return None
            t = t + tof
            if t > kt.max_time:
                return None
            # Early-abort: greedy arrival is monotone in start epoch per leg, so
            # if we're already past the incumbent's terminus we cannot win.
            if abort_floor is not None and t >= abort_floor:
                return None
        return t

    def count_exc_pairs(p):
        """Count directed adjacencies in p that are in exc_pairs."""
        c = 0
        for k in range(len(p) - 1):
            if (p[k], p[k + 1]) in exc_pairs:
                c += 1
        return c

    def retime_walk_from(p, start, t_start, prefix_times, prefix_tofs):
        """Walk p[start:] from arrival epoch t_start at p[start]. Each leg:
        min-ARRIVAL departure delay over DELAY_GRID. A leg is exc iff its
        directed pair is in exc_pairs (cheap thr otherwise). Returns
        (term, times, tofs) or (None,None,None)."""
        times = list(prefix_times)
        tofs = list(prefix_tofs)
        t = t_start
        for k in range(start, len(p) - 1):
            a, b = p[k], p[k + 1]
            is_exc = pair_is_exc(a, b)
            best = None
            for d in DELAY_GRID:
                td = t + float(d)
                if td + 0.05 >= kt.max_time:
                    break
                tof = leg_tof(a, b, td, is_exc)
                if tof is None:
                    continue
                arr = td + tof
                if best is None or arr < best[0] - 1e-9:
                    best = (arr, td, tof)
            if best is None:
                return None, None, None
            arr, td, tof = best
            times.append(td)
            tofs.append(tof)
            t = arr
            if t > kt.max_time:
                return None, None, None
        return t, times, tofs

    # --- Two-stage evaluator -------------------------------------------------
    # STAGE A (screen): FAST greedy walk (delay=0). Establishes greedy baseline.
    # STAGE B (verify): full retime walk + kt.fitness, only on candidates that
    # IMPROVE the greedy baseline (the retime advantage is order-preserving, so
    # a relocation that helps under retime almost always also helps greedy; this
    # screen keeps cost tractable). Accept ONLY if fitness < true bank.
    t0 = time.time()
    base_arr_g = [0.0]
    t = 0.0
    for k in range(n - 1):
        a, b = perm[k], perm[k + 1]
        tof = leg_tof(a, b, t, pair_is_exc(a, b))
        t = t + tof
        base_arr_g.append(t)
    greedy_base = base_arr_g[-1]
    print(f"[E-592] greedy baseline (delay=0 over bank perm) term="
          f"{greedy_base:.6f}  (true bank {CURRENT_BANK:.6f})  "
          f"wall={time.time()-t0:.1f}s cache={len(leg_cache)}", flush=True)

    best_perm = list(perm)
    best_greedy = greedy_base
    best_arr = list(base_arr_g)  # greedy arrival epochs at best_perm positions
    best_fitness = CURRENT_BANK  # acceptance threshold: must beat true bank
    best_times = None
    best_tofs = None

    improved = True
    rounds = 0
    n_eval = 0
    n_screen_hit = 0
    n_improve = 0
    while improved and (time.time() - t0) < TIME_BUDGET_S:
        improved = False
        rounds += 1
        cur_pos = {nd: i for i, nd in enumerate(best_perm)}
        order = sorted(LOCKED, key=lambda nd: -cur_pos[nd])
        for nd in order:
            if (time.time() - t0) >= TIME_BUDGET_S:
                break
            i = cur_pos[nd]
            if i == 0 or i == n - 1:
                continue
            prev_nd = best_perm[i - 1]
            next_nd = best_perm[i + 1]
            if pair_is_exc(prev_nd, nd) or pair_is_exc(nd, next_nd):
                continue  # nd on an exc bridge — relocating breaks topology
            rest = best_perm[:i] + best_perm[i + 1:]
            cand_js = candidate_positions(i, len(rest))
            screen_best = None  # (greedy_term, j, cand, p)
            for j in cand_js:
                if (time.time() - t0) >= TIME_BUDGET_S:
                    break
                if j == i:
                    continue
                cand = rest[:j] + [nd] + rest[j:]
                if count_exc_pairs(cand) != len(exc_pairs):
                    continue
                p = min(i, j)
                if p == 0:
                    continue
                gterm = greedy_term_from(cand, p - 1, best_arr[p - 1],
                                         abort_floor=best_greedy)
                n_eval += 1
                if gterm is None:
                    continue
                if screen_best is None or gterm < screen_best[0] - 1e-9:
                    screen_best = (gterm, j, cand, p)
            if screen_best is None:
                continue
            gterm, j, cand, p = screen_best
            if gterm >= best_greedy - 1e-4:
                continue  # no greedy improvement from this node's best move
            n_screen_hit += 1
            # STAGE B: retime + fitness verification of the screened candidate.
            term_r, times, tofs = retime_walk_from(cand, 0, 0.0, [], [])
            if term_r is None:
                continue
            x = list(times) + list(tofs) + [float(v) for v in cand]
            f = kt.fitness(x)
            feas = bool(kt.is_feasible(f))
            mk = float(f[0])
            print(f"[E-592] r{rounds} node {nd} {i}->{j} greedy "
                  f"{best_greedy:.4f}->{gterm:.4f}  retime={term_r:.4f}  "
                  f"fitness={mk:.6f} feas={feas}", flush=True)
            if feas and mk < best_fitness - 1e-6:
                best_perm = cand
                best_greedy = gterm
                best_fitness = mk
                best_times = times
                best_tofs = tofs
                best_arr = [0.0]
                t = 0.0
                for k in range(n - 1):
                    a, b = cand[k], cand[k + 1]
                    tof = leg_tof(a, b, t, pair_is_exc(a, b))
                    t = t + tof
                    best_arr.append(t)
                improved = True
                n_improve += 1
                print(f"[E-592] *** ACCEPT node {nd} {i}->{j} "
                      f"fitness={mk:.6f} < bank {CURRENT_BANK:.6f}", flush=True)
                break
            elif gterm < best_greedy - 1e-4:
                # Greedy improved but fitness did not beat bank: the retime
                # coordination the bank uses recovers/exceeds the relocation
                # gain. Update greedy baseline so we don't re-screen the same.
                best_greedy = gterm
                best_perm = cand
                best_arr = [0.0]
                t = 0.0
                for k in range(n - 1):
                    a, b = cand[k], cand[k + 1]
                    tof = leg_tof(a, b, t, pair_is_exc(a, b))
                    t = t + tof
                    best_arr.append(t)
                improved = True
                print(f"[E-592]     (greedy-only improve; bank not beaten — "
                      f"epoch-shift trap recovered the gain downstream)",
                      flush=True)
                break
        print(f"[E-592] round {rounds} best_greedy={best_greedy:.6f} "
              f"best_fitness={best_fitness:.6f} evals={n_eval} "
              f"screen_hits={n_screen_hit} improves={n_improve} "
              f"{time.time()-t0:.0f}s cache={len(leg_cache)}", flush=True)

    n_improve = n_improve if best_fitness < CURRENT_BANK - 1e-6 else 0
    term0 = greedy_base
    best_term = best_fitness
    print(f"[E-592] DONE rounds={rounds} evals={n_eval} "
          f"screen_hits={n_screen_hit} accepts={n_improve} "
          f"best_fitness={best_fitness:.6f} greedy_baseline={greedy_base:.6f} "
          f"true_bank={CURRENT_BANK:.6f}", flush=True)

    if n_improve == 0 or best_fitness >= CURRENT_BANK - 1e-6:
        print(f"[E-592] NO improvement beat the TRUE bank "
              f"(best {best_fitness:.6f} >= bank {CURRENT_BANK:.6f}). "
              f"Epoch-shift trap holds: relocating an epoch-locked node to a "
              f"cheaper epoch shifts every downstream epoch and the net change "
              f"is >=0 under the full retime walk. Wrote nothing.", flush=True)
        return

    # best_term beat the true bank under fitness — write candidate.
    x = list(best_times) + list(best_tofs) + [float(v) for v in best_perm]
    f = kt.fitness(x)
    mk = float(f[0])
    feas = bool(kt.is_feasible(f))
    print(f"[E-592] FINAL fitness mk={mk:.6f} feas={feas} viols={list(f[1:])}",
          flush=True)
    # Independent fine chrono-walk sanity (greedy walk may report higher; the
    # fitness on our retimed DV is the authority).
    from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
    w = walk_perm_chrono(kt, best_perm, tof_window=40.0, n_steps=2400,
                         wait_steps=12, wait_dt=0.25)
    print(f"[E-592] walk_perm_chrono(fine) ok={w[3]} exc={w[4]} leg={w[5]}",
          flush=True)
    if feas and mk < CURRENT_BANK - 1e-6:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        f2 = kt.fitness(x)
        print(f"[E-592] WROTE {OUT}: REVAL mk={float(f2[0]):.6f} "
              f"feas={bool(kt.is_feasible(f2))} viols={list(f2[1:])}",
              flush=True)
    else:
        print("[E-592] did not beat bank under fitness — wrote nothing.",
              flush=True)


def candidate_positions(i, m):
    """Insertion positions in the `rest` list (length m). Dense local window
    around the removal point plus a coarse stride across the whole tour, to
    probe far-relocation to a different epoch regime. Returns sorted unique
    positions in [1, m]."""
    js = set()
    # dense local window
    for d in range(-25, 26):
        j = i + d
        if 1 <= j <= m:
            js.add(j)
    # coarse global stride (every 30 positions) to test far epoch regimes
    for j in range(1, m, 30):
        js.add(j)
    return sorted(js)


if __name__ == "__main__":
    main()
