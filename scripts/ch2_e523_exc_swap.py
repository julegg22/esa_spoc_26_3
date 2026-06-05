"""E-523 — Ch2 small: exception-placement swap search on bank perm.

Bank's 5 exc legs are [2, 7, 21, 24, 45] (dvs near 600 m/s). The SLSQP
polish (E-520, E-521) holds the exc set fixed. What if a DIFFERENT
5-subset of legs as exceptions would yield a shorter polished tour?

Method: 1-leg swap LNS over exc placement.
  For each (drop, promote) pair where drop ∈ bank's 5 exc and promote
  ∈ the 43 cheap legs:
    1. New exc_set = bank_exc \ {drop} ∪ {promote}.
    2. Initial guess: bank's (times, tofs).
    3. SLSQP polish with new exc_set as constraint.
    4. If feasible and mk < bank → bank.

Total: 5 × 43 = 215 swap candidates. ~5-10 min wall on 6 workers.

Caveat: SLSQP starting from bank's schedule may not converge for many
exc-swap variants (the new exc/cheap classification likely violates
dv constraints initially). Use bank's schedule as warm start; penalty
will steer SLSQP. If penalty is insufficient, fall back to a couple
of random perturbations.
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np
import multiprocessing as mp
from scipy.optimize import minimize

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260604.e523"
RESULT = '/tmp/ch2_e523_result.json'
HIST = '/tmp/ch2_e523_history.jsonl'

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


def try_swap(args):
    """One exc-swap candidate."""
    sw_id, perm, drop, promote, bank_times, bank_tofs, current_exc = args
    kt = _GLOB['kt']
    new_exc = (current_exc - {drop}) | {promote}
    # Try SLSQP from bank schedule
    res, mk, feas = slsqp_polish(kt, perm, bank_times, bank_tofs, new_exc)
    return {
        'sw_id': sw_id, 'drop_leg': int(drop), 'promote_leg': int(promote),
        'mk': mk, 'feas': bool(feas),
        'new_exc': sorted(new_exc),
        'perm': perm if feas else None,
        'ts': res[0] if (res and feas) else None,
        'tfs': res[1] if (res and feas) else None,
    }


def main(n_workers=6):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_times = list(dv[:n-1]); bank_tofs = list(dv[n-1:2*(n-1)])
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(bank_times + bank_tofs +
                                 [float(p) for p in bank_perm])[0])

    # Identify bank's exc legs
    n_legs = len(bank_perm) - 1
    bank_exc = set()
    for k in range(n_legs):
        d = leg_dv(kt, bank_perm[k], bank_perm[k+1],
                    bank_times[k], bank_tofs[k])
        if d > DV_CHEAP + 1e-6:
            bank_exc.add(k)
    print(f"E-523 exc-swap search. bank_mk={bank_mk:.4f}d  "
          f"bank_exc={sorted(bank_exc)}", flush=True)
    assert len(bank_exc) == kt.n_exc

    # Build swap candidates
    cheap_legs = [k for k in range(n_legs) if k not in bank_exc]
    args = []
    sw_id = 0
    for drop in bank_exc:
        for promote in cheap_legs:
            args.append((sw_id, bank_perm, drop, promote,
                          bank_times, bank_tofs, bank_exc))
            sw_id += 1
    print(f"Total swap candidates: {len(args)} = {len(bank_exc)} drops × "
          f"{len(cheap_legs)} promotions", flush=True)

    best = (bank_mk, None, None, None, None)  # (mk, drop, promote, ts, tfs, perm)
    feas_count = 0
    under_bank = 0
    t0 = time.time()
    hist = open(HIST, 'w')
    with mp.Pool(n_workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(try_swap, args):
            slim = {k: v for k, v in rec.items()
                    if k not in ('perm', 'ts', 'tfs')}
            hist.write(json.dumps(slim) + '\n'); hist.flush()
            if rec['feas']:
                feas_count += 1
                if rec['mk'] < bank_mk - 1e-4:
                    under_bank += 1
                    print(f"  swap drop={rec['drop_leg']:2d} "
                          f"prom={rec['promote_leg']:2d} → "
                          f"mk={rec['mk']:.4f}d feas=YES <<< UNDER",
                          flush=True)
                    if rec['mk'] < best[0]:
                        best = (rec['mk'], rec['drop_leg'],
                                rec['promote_leg'], rec['ts'], rec['tfs'])
                        print(f"    new best: {best[0]:.4f}d", flush=True)
                else:
                    # log feasibles regardless
                    pass
            if rec['sw_id'] % 50 == 0:
                elapsed = time.time() - t0
                print(f"  sw_id={rec['sw_id']}/{len(args)} "
                      f"elapsed={elapsed:.0f}s feas={feas_count} "
                      f"under_bank={under_bank}", flush=True)
    hist.close()
    wall = time.time() - t0
    print(f"\n=== E-523 done in {wall/60:.1f}min ===", flush=True)
    print(f"  feasible swaps: {feas_count}/{len(args)}", flush=True)
    print(f"  under bank ({bank_mk:.4f}): {under_bank}", flush=True)
    print(f"  best mk: {best[0]:.4f}d", flush=True)

    banked = False
    if best[3] is not None and best[0] < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_final = list(best[3]) + list(best[4]) + [float(p) for p in bank_perm]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {best[0]:.4f}d  drop={best[1]} prom={best[2]}  "
              f"({bank_mk - best[0]:.4f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_entry': float(bank_mk), 'best': float(best[0]),
        'best_drop': int(best[1]) if best[1] is not None else None,
        'best_promote': int(best[2]) if best[2] is not None else None,
        'n_swaps': len(args),
        'feasible': feas_count, 'under_bank': under_bank,
        'banked': banked, 'wall_s': wall,
    }))


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    main(n_workers=nw)
