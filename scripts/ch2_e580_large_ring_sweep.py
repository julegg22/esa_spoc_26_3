"""E-044 v1 — Ch2 LARGE: per-run ring PHASE-SWEEP on the bank skeleton.

E-579 showed ~500d of the 624d gap to r1 is intra-ring phase-miss: the
bank visits co-orbital ring members out of phase order and pays 0.5-3d
catch-up legs. This v1 keeps the bank's coarse skeleton (sequence of
same-ring runs, bridge endpoints, exception placement) and re-orders the
INTERIOR of each run by orbital phase (argument of latitude u = argp+M),
trying forward and backward sweeps, choosing per run by realized
chronological walk time (self-consistent epochs — each run is walked
from the actual arrival state, so there is no frozen-epoch proxy gap).

Output: candidate decision vector -> /tmp ONLY (guard-banked separately).
Never touches solutions/upload/.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = os.environ.get("E580_OUT", "/tmp/ch2_large_ringsweep_cand.json")

TOF_WINDOW = float(os.environ.get("E580_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E580_NSTEPS", "120"))
WAIT_STEPS = int(os.environ.get("E580_WAITSTEPS", "24"))
WAIT_DT = float(os.environ.get("E580_WAITDT", "0.25"))
CURRENT_BANK = 1048.9786


def ring_labels(kt):
    a = kt.opar[:, 0] / 1000.0
    inc = np.degrees(kt.opar[:, 2]) % 360.0
    shell = np.where(a < 8000, 0, 1)
    plane = (np.round(inc / 15.0).astype(int) * 15) % 360
    return shell, plane


def phase_u(kt):
    """Argument of latitude proxy (near-circular): u = argp + M mod 2pi."""
    return (kt.opar[:, 4] + kt.opar[:, 5]) % (2 * np.pi)


WAIT_STEPS_BOUNDARY = int(os.environ.get("E580_WAITB", "80"))


def leg(kt, i, j, t, allow_exc, wait_steps):
    """Earliest feasible leg i->j departing >= t. cheap (+wait);
    exception only if allow_exc. Returns (t_dep, tof, is_exc) or None."""
    tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_thr,
                                     TOF_WINDOW, N_STEPS)
    if tof is not None:
        return t, tof, False
    for w in range(1, wait_steps + 1):
        t_try = t + w * WAIT_DT
        if t_try >= kt.max_time - kt.min_tof:
            break
        tof, dv = find_earliest_transfer(kt, i, j, t_try, kt.dv_thr,
                                         TOF_WINDOW, N_STEPS)
        if tof is not None:
            return t_try, tof, False
    if allow_exc:
        tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_exc,
                                         TOF_WINDOW, N_STEPS)
        if tof is not None:
            return t, tof, True
        for w in range(1, wait_steps + 1):
            t_try = t + w * WAIT_DT
            if t_try >= kt.max_time - kt.min_tof:
                break
            tof, dv = find_earliest_transfer(kt, i, j, t_try, kt.dv_exc,
                                             TOF_WINDOW, N_STEPS)
            if tof is not None:
                return t_try, tof, True
    return None


def walk_seq(kt, prev, t, seq, exc_used, entry_exc_ok):
    """Walk prev->seq[0]->...->seq[-1] from epoch t. Exception allowed
    only on the entry leg (prev->seq[0]) and only if entry_exc_ok and
    budget left. Returns (times, tofs, end_t, exc_used, ok)."""
    times, tofs = [], []
    cur = prev
    for li, j in enumerate(seq):
        is_entry = (li == 0)
        allow_exc = (is_entry and entry_exc_ok and exc_used < kt.n_exc)
        ws = WAIT_STEPS_BOUNDARY if is_entry else WAIT_STEPS
        r = leg(kt, cur, j, t, allow_exc, ws)
        if r is None:
            return times, tofs, t, exc_used, False
        t_dep, tof, is_exc = r
        times.append(t_dep)
        tofs.append(tof)
        t = t_dep + tof
        if is_exc:
            exc_used += 1
        cur = j
    return times, tofs, t, exc_used, True


def sweep_orders(run, u):
    """Forward/backward circular phase sweeps of run, anchored at run[0]."""
    entry = run[0]
    rest = run[1:]
    if not rest:
        return []
    du = [(u[j] - u[entry]) % (2 * np.pi) for j in rest]
    fwd = [entry] + [j for _, j in sorted(zip(du, rest))]
    bwd = [entry] + [j for _, j in sorted(zip(du, rest), reverse=True)]
    return [fwd, bwd]


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    b_times = np.array(bank[:n - 1], dtype=float)
    b_tofs = np.array(bank[n - 1:2 * (n - 1)], dtype=float)
    perm = [int(round(v)) for v in bank[2 * (n - 1):]]
    fit = kt.fitness(bank)
    print(f"[E-580] bank mk={fit[0]:.4f} feas={kt.is_feasible(fit)}",
          flush=True)
    # bank exc legs: dv in (dv_thr, dv_exc]
    bank_exc_leg = set()
    for k in range(n - 1):
        dv = kt.compute_transfer(perm[k], perm[k + 1],
                                 float(b_times[k]), float(b_tofs[k]))
        if dv > kt.dv_thr + 1e-6:
            bank_exc_leg.add(k)
    print(f"[E-580] bank exc legs at indices {sorted(bank_exc_leg)}",
          flush=True)

    shell, plane = ring_labels(kt)
    ring = [(int(shell[i]), int(plane[i])) for i in range(n)]
    u = phase_u(kt)

    # decompose bank perm into maximal same-ring runs
    runs = []
    cur_run = [perm[0]]
    for k in range(1, n):
        if ring[perm[k]] == ring[cur_run[-1]]:
            cur_run.append(perm[k])
        else:
            runs.append(cur_run)
            cur_run = [perm[k]]
    runs.append(cur_run)
    sizes = sorted((len(r) for r in runs), reverse=True)
    print(f"[E-580] {len(runs)} same-ring runs, sizes top10={sizes[:10]}",
          flush=True)
    # map: which run-entry legs were exc in the bank, and bank cumulative
    # arrival time after each run (for apples-to-apples progress compare)
    run_entry_exc = [False]
    run_bank_t = []
    pos = 0
    for ri, run in enumerate(runs):
        if ri > 0:
            run_entry_exc.append((pos - 1) in bank_exc_leg)
        pos += len(run)
        kend = pos - 2  # leg index arriving at last node of this run
        run_bank_t.append(float(b_times[kend] + b_tofs[kend])
                          if kend >= 0 else 0.0)
    n_exc_entries = sum(run_entry_exc)
    print(f"[E-580] bank exc sits on {n_exc_entries} run-entry legs "
          f"(of {len(bank_exc_leg)} exc total)", flush=True)

    # chronological pass: per run pick best of {bank order, fwd, bwd}
    t0 = time.time()
    out_perm = [runs[0][0]]
    all_times, all_tofs = [], []
    exc_used = 0
    t = 0.0
    prev = runs[0][0]
    first = True
    n_better = 0
    gain = 0.0
    for ri, run in enumerate(runs):
        base = run
        # candidate orderings (all begin with the same entry node)
        cands = [base] + sweep_orders(base, u)
        best = None
        for ci, cand in enumerate(cands):
            seq = cand[1:] if first else cand
            if not seq:
                best = (t, [], [], exc_used, 0)
                break
            times, tofs, end_t, exc2, ok = walk_seq(
                kt, prev, t, seq, exc_used,
                entry_exc_ok=(not first and run_entry_exc[ri]))
            if ok and (best is None or end_t < best[0]):
                best = (end_t, times, tofs, exc2, ci)
        if best is None:
            print(f"[E-580] run {ri} UNWALKABLE in all orders — abort",
                  flush=True)
            return
        end_t, times, tofs, exc2, ci = best
        if ci > 0:
            n_better += 1
        # recompute chosen sequence to append perm nodes
        chosen = cands[ci] if cands else base
        seq = chosen[1:] if first else chosen
        out_perm.extend(seq)
        all_times.extend(times)
        all_tofs.extend(tofs)
        t = end_t
        exc_used = exc2
        prev = out_perm[-1]
        first = False
        if ri % 5 == 0 or ri == len(runs) - 1:
            print(f"[E-580] run {ri+1}/{len(runs)} t={t:.2f}d "
                  f"(bank {run_bank_t[ri]:.2f}d) exc={exc_used} "
                  f"swept_better={n_better} ({time.time()-t0:.0f}s)",
                  flush=True)

    assert len(out_perm) == n and len(set(out_perm)) == n
    mk = all_times[-1] + all_tofs[-1]
    print(f"\n[E-580] RESULT walk mk={mk:.4f}d exc={exc_used} "
          f"(bank {CURRENT_BANK})", flush=True)

    x = list(map(float, all_times)) + list(map(float, all_tofs)) + \
        [float(v) for v in out_perm]
    fit = kt.fitness(x)
    feas = kt.is_feasible(fit)
    print(f"[E-580] official fitness mk={fit[0]:.4f} feas={feas} "
          f"viol={fit[1:]}", flush=True)
    if feas and fit[0] < CURRENT_BANK - 1e-6:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        print(f"[E-580] CANDIDATE WRITTEN {OUT} mk={fit[0]:.4f}", flush=True)
    else:
        print("[E-580] no improvement — nothing written", flush=True)


if __name__ == "__main__":
    main()
