"""E-520 — Ch2 small: SLSQP multi-start on (times, tofs) for bank perm.

Builds the proper (times, tofs) optimizer that E-519c needed but couldn't
afford in coarse grid form. Uses scipy.optimize.minimize with method='SLSQP'
and numerical Jacobian. Penalty formulation for Lambert dv and chronology.

Per perm: launch SLSQP from N start points (bank + N-1 perturbations),
keep best. With perm fixed and the 5 exception slots assigned to the
current 5 highest-dv legs, the search space is 96 continuous variables
with ~143 nonlinear inequality constraints (chronology + per-leg dv).

If best < current bank (142.8359), auto-bank.
"""
from __future__ import annotations
import sys, os, json, time, random
from pathlib import Path
import numpy as np
from scipy.optimize import minimize

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260603.e520"
RESULT = '/tmp/ch2_e520_result.json'

DV_CHEAP = 100.0
DV_EXC = 600.0
DT_MIN = 0.001
TOF_MIN = 0.001
TOF_MAX = 8.0
MAX_T = 200.0
PEN_CHRONO = 1e6
PEN_DV = 1e4


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return 1e9


def make_penalized_objective(kt, perm, exc_set):
    """Return f(x) where x = concat(times[0..n-2], tofs[0..n-2])."""
    n = kt.n
    n_legs = n - 1

    def f(x):
        times = x[:n_legs]
        tofs = x[n_legs:]
        # chronology penalty
        chrono_pen = 0.0
        for k in range(1, n_legs):
            slack = times[k] - (times[k-1] + tofs[k-1])
            if slack < 0:
                chrono_pen += -slack
        # dv penalty
        dv_pen = 0.0
        n_exc_violations = 0
        n_cheap_violations = 0
        for k in range(n_legs):
            cap = DV_EXC if k in exc_set else DV_CHEAP
            dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
            if dv > cap:
                dv_pen += (dv - cap)
                if k in exc_set:
                    n_exc_violations += 1
                else:
                    n_cheap_violations += 1
        # makespan
        mk = times[-1] + tofs[-1]
        return mk + PEN_CHRONO * chrono_pen + PEN_DV * dv_pen

    return f


def get_exc_legs(kt, perm, times, tofs):
    """Identify which legs are exceptions in the current schedule."""
    exc_set = set()
    n_legs = len(perm) - 1
    for k in range(n_legs):
        dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
        if dv > DV_CHEAP + 1e-6:
            exc_set.add(k)
    return exc_set


def perturb(times, tofs, rng, scale_t=0.5, scale_tof=0.3):
    """Random perturbation around (times, tofs)."""
    n = len(times)
    nt = np.array(times)
    ntof = np.array(tofs)
    # Perturbation respecting bounds
    nt = nt + rng.normal(0, scale_t, n)
    ntof = ntof + rng.normal(0, scale_tof, n)
    nt = np.clip(nt, 0, MAX_T)
    ntof = np.clip(ntof, TOF_MIN, TOF_MAX)
    # Push to satisfy basic chronology
    for k in range(1, n):
        nt[k] = max(nt[k], nt[k-1] + ntof[k-1])
    return list(nt), list(ntof)


def run_slsqp(kt, perm, exc_set, times0, tofs0, maxiter=200):
    """SLSQP from one start, then polish via re-run with increased
    penalties if infeasible. Returns (best_x, best_mk, success)."""
    n_legs = len(perm) - 1
    x0 = np.array(list(times0) + list(tofs0))
    f = make_penalized_objective(kt, perm, exc_set)
    bounds = [(0, MAX_T)] * n_legs + [(TOF_MIN, TOF_MAX)] * n_legs
    t0 = time.time()
    try:
        result = minimize(f, x0, method='SLSQP', bounds=bounds,
                          options={'maxiter': maxiter, 'ftol': 1e-7})
    except Exception as e:
        return None, 1e9, False
    x = result.x
    times = list(x[:n_legs]); tofs = list(x[n_legs:])
    x_udp = times + tofs + [float(p) for p in perm]
    fit = kt.fitness(x_udp)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0]) if len(fit) > 0 else 1e9

    # If infeasible but objective is good, try re-polishing with even
    # higher penalty to push into feasibility
    if not feas and mk < 1e8:
        global PEN_CHRONO, PEN_DV
        old_cp, old_dv = PEN_CHRONO, PEN_DV
        PEN_CHRONO *= 100
        PEN_DV *= 100
        try:
            f2 = make_penalized_objective(kt, perm, exc_set)
            result2 = minimize(f2, x, method='SLSQP', bounds=bounds,
                                options={'maxiter': maxiter, 'ftol': 1e-7})
            x = result2.x
            times = list(x[:n_legs]); tofs = list(x[n_legs:])
            x_udp = times + tofs + [float(p) for p in perm]
            fit = kt.fitness(x_udp)
            feas = bool(kt.is_feasible(fit))
            mk = float(fit[0]) if len(fit) > 0 else 1e9
        finally:
            PEN_CHRONO, PEN_DV = old_cp, old_dv

    wall = time.time() - t0
    return (times, tofs, feas, wall), mk, result.success


def main(n_starts=8, max_iter=80):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_times = list(dv[:n-1]); bank_tofs = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]

    # Verify bank
    x0 = bank_times + bank_tofs + [float(p) for p in perm]
    fit0 = kt.fitness(x0)
    feas0 = bool(kt.is_feasible(fit0))
    mk0 = float(fit0[0])
    print(f"E-520 SLSQP multi-start on bank perm.", flush=True)
    print(f"Current bank: mk={mk0:.6f}d  feasible={feas0}  "
          f"start={perm[0]} end={perm[-1]}", flush=True)

    exc_set = get_exc_legs(kt, perm, bank_times, bank_tofs)
    print(f"Exception legs: {sorted(exc_set)} (count={len(exc_set)})",
          flush=True)
    if len(exc_set) > kt.n_exc:
        print(f"WARN: more exc legs than budget ({kt.n_exc}); aborting",
              flush=True)
        return

    best = (mk0, bank_times, bank_tofs, True)
    rng = np.random.default_rng(0)

    # Start 0: bank itself (test of E-519b's claim that bank is loc-opt)
    print(f"\n--- Start 0: bank ---", flush=True)
    res, mk_s, ok = run_slsqp(kt, perm, exc_set, bank_times, bank_tofs,
                                maxiter=max_iter)
    if res is None:
        print(f"  SLSQP crashed", flush=True)
    else:
        ts, tfs, feas, wall = res
        print(f"  mk={mk_s:.6f}d  feasible={feas}  wall={wall:.1f}s  "
              f"slsqp_ok={ok}", flush=True)
        if feas and mk_s < best[0] - 1e-5:
            best = (mk_s, ts, tfs, feas)
            print(f"  >>> new best: {mk_s:.6f}d", flush=True)

    # Starts 1..n_starts-1: perturbations
    for s in range(1, n_starts):
        # vary perturbation scale
        scale = 0.1 * (1 + s)  # 0.2, 0.3, ..., up to ~0.8
        t_pert, tof_pert = perturb(bank_times, bank_tofs, rng,
                                     scale_t=scale, scale_tof=scale*0.5)
        print(f"\n--- Start {s} (scale={scale:.2f}) ---", flush=True)
        res, mk_s, ok = run_slsqp(kt, perm, exc_set, t_pert, tof_pert,
                                    maxiter=max_iter)
        if res is None:
            print(f"  SLSQP crashed", flush=True)
            continue
        ts, tfs, feas, wall = res
        print(f"  mk={mk_s:.6f}d  feasible={feas}  wall={wall:.1f}s",
              flush=True)
        if feas and mk_s < best[0] - 1e-5:
            best = (mk_s, ts, tfs, feas)
            print(f"  >>> new best: {mk_s:.6f}d", flush=True)

    # Report and bank
    print(f"\n=== E-520 best: mk={best[0]:.6f}d feasible={best[3]} ===",
          flush=True)
    print(f"  delta from bank entry: {mk0 - best[0]:+.6f}d", flush=True)

    banked = False
    if best[3] and best[0] < mk0 - 1e-5:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_final = list(best[1]) + list(best[2]) + [float(p) for p in perm]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {best[0]:.6f}d "
              f"({mk0 - best[0]:.6f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'mk_entry': float(mk0), 'mk_best': float(best[0]),
        'shaved_d': float(mk0 - best[0]),
        'udp_feasible': best[3], 'banked': banked,
        'n_starts': n_starts, 'exc_legs': sorted(exc_set),
    }))


if __name__ == '__main__':
    n_starts = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(n_starts=n_starts)
