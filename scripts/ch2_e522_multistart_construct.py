"""E-522 — Ch2 small: greedy_findxfer × all start nodes + SLSQP polish.

Round 4 of E-521 confirmed bank-adjacent perm space is exhausted under
SLSQP polish. Bank starts at node 34; the other 48 starts are
unexplored under the SLSQP-polish evaluator. This script:
  1. For each starting node v ∈ [0, n-1], run greedy_findxfer(start=v)
     with the standard tof_window=12, n_steps=120, wait_dt=0.5 params.
  2. For each FEASIBLE full tour from that start, identify exc legs and
     SLSQP-polish (times, tofs).
  3. Also pad short tours: greedy may return a partial; skip those.
  4. Compare polished mks across all 49 starts. Bank if any beats
     current bank (142.2897 d).

Each greedy call ~10-30s; 49 starts × 6 workers ≈ 5 min. Then 49
SLSQP calls × ~2s = 100s. Total ~10 min wall.
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

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260604.e522"
RESULT = '/tmp/ch2_e522_result.json'
HIST = '/tmp/ch2_e522_history.jsonl'

DV_CHEAP = 100.0
DV_EXC = 600.0
TOF_MIN = 0.001
TOF_MAX = 8.0
MAX_T = 200.0
PEN_CHRONO = 1e6
PEN_DV = 1e4

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


def slsqp_polish(kt, perm, times0, tofs0, exc_set, maxiter=120):
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


def construct_and_polish(args):
    """One start node → greedy → polish."""
    start, tof_window, n_steps, wait_steps, wait_dt = args
    kt = _GLOB['kt']
    t0 = time.time()
    try:
        perm, times, tofs, dvs, ok = greedy_findxfer(
            kt, start, tof_window=tof_window, n_steps=n_steps,
            wait_steps=wait_steps, wait_dt=wait_dt)
    except Exception as e:
        return {'start': start, 'err': str(e)[:80]}
    construct_wall = time.time() - t0
    if not ok or len(perm) != kt.n:
        return {'start': start, 'construct_ok': False,
                'partial_len': len(perm),
                'construct_wall_s': construct_wall}
    walk_mk = times[-1] + tofs[-1]
    exc_set = {k for k in range(len(perm)-1) if dvs[k] > DV_CHEAP + 1e-6}
    res, slsqp_mk, feas = slsqp_polish(kt, perm, times, tofs, exc_set)
    polish_wall = time.time() - t0 - construct_wall
    return {
        'start': start, 'construct_ok': True, 'walk_mk': float(walk_mk),
        'exc_count': len(exc_set),
        'slsqp_mk': slsqp_mk, 'slsqp_feas': feas,
        'perm': perm if feas else None,
        'ts': res[0] if (res and feas) else None,
        'tfs': res[1] if (res and feas) else None,
        'construct_wall_s': construct_wall,
        'polish_wall_s': polish_wall,
    }


def main(n_workers=6):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    bank_mk = float(kt.fitness(bank[0]['decisionVector'])[0])
    print(f"E-522 multi-start greedy + SLSQP polish. bank_mk={bank_mk:.4f}d  "
          f"n_starts={n} workers={n_workers}", flush=True)

    # Param variations to try per start (cross-product of tof_window, etc.)
    # Start with the standard config; if time permits, add variants.
    param_sets = [
        (12.0, 120, 4, 0.5),    # standard
        (18.0, 180, 8, 0.5),    # wider tof_window
        (12.0, 240, 4, 0.25),   # finer tof + wait
    ]
    args = []
    for v in range(n):
        for ps in param_sets:
            args.append((v, *ps))
    print(f"Total constructive runs: {len(args)} "
          f"= {n} starts × {len(param_sets)} param sets", flush=True)

    t0 = time.time()
    best = (bank_mk, None, None, None, None)  # (mk, start, perm, ts, tfs)
    feas_count = 0
    constructed = 0
    under_bank = 0
    hist = open(HIST, 'w')
    with mp.Pool(n_workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(construct_and_polish, args):
            slim = {k: v for k, v in rec.items()
                    if k not in ('perm', 'ts', 'tfs')}
            hist.write(json.dumps(slim) + '\n'); hist.flush()
            if rec.get('construct_ok'):
                constructed += 1
                if rec.get('slsqp_feas'):
                    feas_count += 1
                    print(f"  start={rec['start']:2d} "
                          f"walk_mk={rec['walk_mk']:8.4f} → "
                          f"slsqp_mk={rec['slsqp_mk']:8.4f} "
                          f"exc={rec['exc_count']} "
                          f"feas=YES", flush=True)
                    if rec['slsqp_mk'] < bank_mk - 1e-4:
                        under_bank += 1
                        if rec['slsqp_mk'] < best[0]:
                            best = (rec['slsqp_mk'], rec['start'],
                                     rec['perm'], rec['ts'], rec['tfs'])
                            print(f"    >>> NEW BEST: {best[0]:.4f}d",
                                   flush=True)
    hist.close()
    wall = time.time() - t0
    print(f"\n=== E-522 done in {wall/60:.1f}min ===", flush=True)
    print(f"  constructed full tours: {constructed}/{len(args)}", flush=True)
    print(f"  SLSQP-polished feasible: {feas_count}", flush=True)
    print(f"  under bank ({bank_mk:.4f}): {under_bank}", flush=True)
    print(f"  best polished mk: {best[0]:.4f}d", flush=True)

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
        'n_starts_tried': len(args),
        'constructed': constructed, 'feasible': feas_count,
        'under_bank': under_bank, 'banked': banked,
        'wall_s': wall,
    }))


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    main(n_workers=nw)
