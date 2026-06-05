"""E-524 — Ch2 small: multi-start (greedy + insert_lns + SLSQP) pipeline.

Mirrors the bank's original construction route:
  greedy_findxfer(start=v) → insert_lns(missing nodes) → walk_perm_chrono
but adds a SLSQP polish step at the end, fixing the C6 evaluator bug
that E-519b/E-521 exposed.

Per starting node v ∈ [0, n-1]:
  1. Run greedy_findxfer with WIDE params (tof_window=18, n_steps=240,
     wait_steps=12, wait_dt=0.5) to maximize coverage.
  2. If partial covers ≥ n-4 nodes, run insert_lns to complete the tour
     (k! × (L+1) candidates ≤ 24 × 46 = 1104 walks per start).
  3. For each complete UDP-feasible tour: SLSQP-polish (times, tofs).
  4. Track the global best. Bank if mk < 142.2897 d.

Compute estimate (49 starts on 6 workers):
  Greedy phase: ~10-15 min wall.
  Insert phase: depends on how many starts have ≤4 missing — likely
    ~5-10 starts → 10-30 min wall on 6 workers.
  Polish phase: fast (~1s/tour, ≤50 successful tours = ~1 min).
  Total: 25-50 min.

If a start's partial has > 4 missing, it's skipped (k! intractable).
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np
import multiprocessing as mp
from scipy.optimize import minimize

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_findtransfer_greedy import greedy_findxfer
from esa_spoc_26.ch2_insert_lns import insert_lns, walk_perm_chrono

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260604.e524"
RESULT = '/tmp/ch2_e524_result.json'
HIST = '/tmp/ch2_e524_history.jsonl'

DV_CHEAP = 100.0
DV_EXC = 600.0
TOF_MIN = 0.001
TOF_MAX = 8.0
MAX_T = 200.0
PEN_CHRONO = 1e6
PEN_DV = 1e4
MAX_MISSING = 5  # skip insert_lns if missing > this (k! intractable)

_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return 1e9


def make_obj(kt, perm, exc_set):
    n_legs = len(perm) - 1

    def f(x):
        times = x[:n_legs]; tofs = x[n_legs:]
        pc = 0.0
        for k in range(1, n_legs):
            s = times[k] - (times[k-1] + tofs[k-1])
            if s < 0: pc -= s
        pd = 0.0
        for k in range(n_legs):
            cap = DV_EXC if k in exc_set else DV_CHEAP
            dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
            if dv > cap: pd += dv - cap
        return times[-1] + tofs[-1] + PEN_CHRONO * pc + PEN_DV * pd
    return f


def slsqp_polish(kt, perm, times0, tofs0, exc_set, maxiter=200):
    n_legs = len(perm) - 1
    x0 = np.array(list(times0) + list(tofs0))
    bounds = [(0, MAX_T)] * n_legs + [(TOF_MIN, TOF_MAX)] * n_legs
    f = make_obj(kt, perm, exc_set)
    try:
        r = minimize(f, x0, method='SLSQP', bounds=bounds,
                     options={'maxiter': maxiter, 'ftol': 1e-7})
    except Exception:
        return None, 1e9, False
    x = r.x
    ts = list(x[:n_legs]); tfs = list(x[n_legs:])
    fit = kt.fitness(ts + tfs + [float(p) for p in perm])
    feas = bool(kt.is_feasible(fit))
    return (ts, tfs), (float(fit[0]) if len(fit) > 0 else 1e9), feas


def process_start(args):
    """One start node: greedy + (maybe) insert_lns + polish."""
    start, tof_window, n_steps, wait_steps, wait_dt = args
    kt = _GLOB['kt']
    rec = {'start': int(start)}
    t0 = time.time()
    try:
        partial, p_times, p_tofs, p_dvs, ok = greedy_findxfer(
            kt, start, tof_window=tof_window, n_steps=n_steps,
            wait_steps=wait_steps, wait_dt=wait_dt)
    except Exception as e:
        rec['greedy_err'] = str(e)[:80]
        return rec
    rec['greedy_wall_s'] = time.time() - t0
    rec['partial_len'] = len(partial)
    if not ok and len(partial) == kt.n:
        ok = True  # full tour from greedy

    if len(partial) == kt.n:
        # Full from greedy — directly polish
        exc_set = {k for k in range(kt.n - 1)
                   if p_dvs[k] > DV_CHEAP + 1e-6}
        rec['from_greedy'] = True
        rec['walk_mk'] = float(p_times[-1] + p_tofs[-1])
        rec['exc_count'] = len(exc_set)
        if len(exc_set) <= kt.n_exc:
            res, mk, feas = slsqp_polish(kt, partial, p_times, p_tofs,
                                           exc_set)
            rec['slsqp_mk'] = mk; rec['slsqp_feas'] = feas
            if feas:
                rec['perm'] = partial; rec['ts'] = res[0]; rec['tfs'] = res[1]
        return rec

    # Partial — try insert_lns if missing count is small
    missing = sorted(set(range(kt.n)) - set(partial))
    rec['n_missing'] = len(missing)
    if len(missing) > MAX_MISSING:
        return rec

    rec['from_insert'] = True
    t1 = time.time()
    try:
        full_perm, sched, n_feas = insert_lns(kt, partial, missing,
                                                 verbose=False)
    except Exception as e:
        rec['insert_err'] = str(e)[:80]
        return rec
    rec['insert_wall_s'] = time.time() - t1
    rec['insert_n_feasible'] = n_feas
    if full_perm is None:
        return rec

    times, tofs, dvs = sched
    walk_mk = times[-1] + tofs[-1]
    exc_set = {k for k in range(len(full_perm) - 1)
                if dvs[k] > DV_CHEAP + 1e-6}
    rec['walk_mk'] = float(walk_mk)
    rec['exc_count'] = len(exc_set)
    if len(exc_set) > kt.n_exc:
        return rec

    res, mk, feas = slsqp_polish(kt, full_perm, times, tofs, exc_set)
    rec['slsqp_mk'] = mk; rec['slsqp_feas'] = feas
    if feas:
        rec['perm'] = list(full_perm); rec['ts'] = res[0]; rec['tfs'] = res[1]
    return rec


def main(n_workers=6):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    bank_mk = float(kt.fitness(bank[0]['decisionVector'])[0])
    print(f"E-524 multi-start (greedy + insert_lns + SLSQP). "
          f"bank_mk={bank_mk:.4f}d  workers={n_workers}", flush=True)

    # Use wide params to maximize coverage
    args = [(v, 18.0, 240, 12, 0.5) for v in range(n)]
    print(f"Starts: {n}, params: tof_window=18, n_steps=240, "
          f"wait_steps=12, wait_dt=0.5", flush=True)

    t0 = time.time()
    best = (bank_mk, None, None, None, None)  # (mk, start, perm, ts, tfs)
    n_processed = 0
    n_full = 0
    n_polished_feas = 0
    n_under_bank = 0
    hist = open(HIST, 'w')

    with mp.Pool(n_workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(process_start, args):
            n_processed += 1
            slim = {k: v for k, v in rec.items()
                    if k not in ('perm', 'ts', 'tfs')}
            hist.write(json.dumps(slim) + '\n'); hist.flush()
            if 'slsqp_mk' in rec:
                n_full += 1
                if rec.get('slsqp_feas'):
                    n_polished_feas += 1
                    print(f"  start={rec['start']:2d} "
                          f"partial={rec['partial_len']:2d} "
                          f"walk_mk={rec['walk_mk']:7.2f} → "
                          f"slsqp_mk={rec['slsqp_mk']:7.4f} "
                          f"exc={rec['exc_count']} feas=YES", flush=True)
                    if rec['slsqp_mk'] < bank_mk - 1e-4:
                        n_under_bank += 1
                        print(f"    >>> UNDER BANK", flush=True)
                        if rec['slsqp_mk'] < best[0]:
                            best = (rec['slsqp_mk'], rec['start'],
                                     rec['perm'], rec['ts'], rec['tfs'])
                            print(f"    >>> NEW BEST: {best[0]:.4f}d",
                                  flush=True)
            elif rec.get('n_missing') is not None:
                msg = (f"  start={rec['start']:2d} partial={rec['partial_len']:2d}"
                       f" missing={rec['n_missing']}")
                if rec['n_missing'] > MAX_MISSING:
                    msg += " (insert skipped)"
                else:
                    msg += f" insert→{'FAILED' if 'insert_err' in rec or 'insert_n_feasible' not in rec else f'n_feas={rec.get('insert_n_feasible', 0)}'}"
                print(msg, flush=True)
            if n_processed % 10 == 0:
                elapsed = time.time() - t0
                print(f"  [{n_processed}/{n}] elapsed={elapsed:.0f}s "
                      f"full={n_full} feas={n_polished_feas} "
                      f"under_bank={n_under_bank}", flush=True)
    hist.close()
    wall = time.time() - t0

    print(f"\n=== E-524 done in {wall/60:.1f}min ===", flush=True)
    print(f"  full tours obtained: {n_full}/{n}", flush=True)
    print(f"  SLSQP-feasible:      {n_polished_feas}", flush=True)
    print(f"  under bank ({bank_mk:.4f}): {n_under_bank}", flush=True)
    print(f"  best polished mk: {best[0]:.4f}d "
          f"(start={best[1]})", flush=True)

    banked = False
    if best[2] is not None and best[0] < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_final = list(best[3]) + list(best[4]) + [float(p) for p in best[2]]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {best[0]:.4f}d  start={best[1]}  "
              f"({bank_mk - best[0]:.4f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_entry': float(bank_mk), 'best': float(best[0]),
        'best_start': int(best[1]) if best[1] is not None else None,
        'n_starts': n, 'n_full': n_full, 'n_feas': n_polished_feas,
        'under_bank': n_under_bank, 'banked': banked, 'wall_s': wall,
    }))


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    main(n_workers=nw)
