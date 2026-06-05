"""E-519b — Ch2 small: iterative leg-wise continuous refinement on bank perm.

Background: E-519's DP-on-fine-table failed (verdict F1) because the 0.5 d
grid is too coarse to represent bank's continuous (times, tofs). To test
C6 (walk_perm_chrono greedy slop) without a grid, do continuous local
search per leg using direct Lambert calls.

Method:
  For each leg k (random order, multiple passes):
    Try to shave leg k's arrival time (t_k + tof_k) while keeping:
      - chronology: t_k ≥ t_{k-1} + tof_{k-1}
      - dv constraint: cheap dv ≤ 100 or exc dv ≤ 600 (counted as exc)
      - total exc count ≤ 5
    Variables: tof_k (continuous), and the departure shift dt ≥ 0 from
    earliest-feasible t. Both swept via fine 1D grid + parabolic polish.
    If a shorter arrival is found, accept and cascade subsequent legs
    to maintain chronology (they may then shift earlier too).

  Repeat passes until no leg improves.

If converged mk < 142.8913: walk_perm_chrono was suboptimal (C6/B1 confirmed);
auto-bank.
If converged mk == 142.8913 (within 1e-3): bank IS locally optimal under
continuous (times, tofs); C6 refuted (or only basin-hopping could help).
"""
from __future__ import annotations
import sys, os, json, time, random, copy
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260602.e519b"
RESULT = '/tmp/ch2_e519b_result.json'

BANK_MK = 142.8913
DV_CHEAP = 100.0
DV_EXC = 600.0
DT_MIN = 0.001
TOF_MIN = 0.001
TOF_MAX = 8.0

EPS_CHRONO = 1e-9


def leg_dv(kt, i, j, t_start, tof):
    """Lambert dv via kt.compute_transfer; return +inf if invalid."""
    try:
        return float(kt.compute_transfer(i, j, t_start, tof))
    except Exception:
        return float('inf')


def schedule_makespan(times, tofs):
    return times[-1] + tofs[-1]


def is_leg_feasible(dv, kind):
    return (kind == 'cheap' and dv <= DV_CHEAP + 1e-6) or \
           (kind == 'exc' and dv <= DV_EXC + 1e-6)


def classify_legs(kt, perm, times, tofs):
    """Return list of 'cheap' or 'exc' per leg based on current dv."""
    out = []
    for k in range(len(perm) - 1):
        dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
        out.append('exc' if dv > DV_CHEAP + 1e-6 else 'cheap')
    return out


def cascade_chronology(times, tofs):
    """Push all t forward so t[k+1] >= t[k] + tof[k]. Returns new list (no-mut)."""
    new_t = list(times); new_tof = list(tofs)
    for k in range(1, len(new_t)):
        earliest = new_t[k-1] + new_tof[k-1]
        if new_t[k] < earliest:
            new_t[k] = earliest
    return new_t, new_tof


def try_shorten_leg(kt, perm, times, tofs, kinds, k,
                    n_sweep_t=60, n_sweep_tof=120):
    """For leg k, search for (t_k', tof_k') with arrival t_k' + tof_k'
    smaller than current, keeping dv feasible for current kind.
    Returns (new_times, new_tofs, improved_bool, mk_delta).

    Departure window: [earliest_t, current_t_k + slack] where slack is
    bounded so we don't push beyond the immediate t-cap.
    """
    n = len(perm); n_exc = kt.n_exc
    earliest_t = (times[k-1] + tofs[k-1]) if k > 0 else 0.0
    cur_dep = times[k]; cur_tof = tofs[k]
    cur_arr = cur_dep + cur_tof
    kind = kinds[k]
    dv_cap = DV_EXC if kind == 'exc' else DV_CHEAP
    i, j = perm[k], perm[k+1]

    # Build sweep grids
    dep_lo = max(earliest_t, 0.0)
    dep_hi = cur_dep + 2.0  # allow more forward exploration
    dep_grid = np.linspace(dep_lo, dep_hi, n_sweep_t)
    tof_lo = max(TOF_MIN, min(cur_tof * 0.25, cur_tof - 2.5))
    tof_hi = min(TOF_MAX, max(cur_tof * 2.0, cur_tof + 2.5))
    tof_grid = np.linspace(tof_lo, tof_hi, n_sweep_tof)

    best_arr = cur_arr - 1e-6  # require strict improvement
    best = None
    for t in dep_grid:
        for tof in tof_grid:
            arr = t + tof
            if arr >= best_arr: continue
            dv = leg_dv(kt, i, j, float(t), float(tof))
            if dv > dv_cap + 1e-6: continue
            best_arr = arr
            best = (float(t), float(tof), float(dv))

    if best is None:
        return times, tofs, False, 0.0

    # Apply and cascade
    new_t = list(times); new_tof = list(tofs)
    new_t[k] = best[0]; new_tof[k] = best[1]
    new_t, new_tof = cascade_chronology(new_t, new_tof)
    # Re-validate chronology by direct dv recompute on subsequent legs
    # (their dv may now be infeasible at new earlier t)
    for k2 in range(k+1, n-1):
        d = leg_dv(kt, perm[k2], perm[k2+1], new_t[k2], new_tof[k2])
        kind2 = 'exc' if kinds[k2] == 'exc' else 'cheap'
        cap = DV_EXC if kind2 == 'exc' else DV_CHEAP
        if d > cap + 1e-6:
            # downstream broke; reject this leg change
            return times, tofs, False, 0.0
    mk_old = schedule_makespan(times, tofs)
    mk_new = schedule_makespan(new_t, new_tof)
    if mk_new >= mk_old - 1e-6:
        return times, tofs, False, 0.0
    return new_t, new_tof, True, mk_old - mk_new


def main(max_passes=10):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    times = list(dv[:n-1]); tofs = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]

    # Verify bank fitness matches expectations
    x0 = times + tofs + [float(p) for p in perm]
    fit0 = kt.fitness(x0)
    feas0 = bool(kt.is_feasible(fit0))
    mk0 = schedule_makespan(times, tofs)
    print(f"E-519b leg refinement on bank perm. "
          f"start={perm[0]} end={perm[-1]}", flush=True)
    print(f"Bank: mk={mk0:.4f}d  fit={fit0}  feasible={feas0}", flush=True)

    kinds = classify_legs(kt, perm, times, tofs)
    n_exc = kinds.count('exc')
    print(f"Legs: {len(perm)-1}; cheap={kinds.count('cheap')} exc={n_exc}",
           flush=True)

    rng = random.Random(0)
    total_imp = 0.0
    for pass_i in range(max_passes):
        order = list(range(n-1)); rng.shuffle(order)
        pass_imp = 0.0
        n_improved = 0
        for k in order:
            new_t, new_tof, ok, delta = try_shorten_leg(
                kt, perm, times, tofs, kinds, k)
            if ok:
                times = new_t; tofs = new_tof
                pass_imp += delta; total_imp += delta
                n_improved += 1
                mk_cur = schedule_makespan(times, tofs)
                print(f"  pass {pass_i} leg {k}: shaved {delta:.4f}d "
                      f"→ mk={mk_cur:.4f}d", flush=True)
        mk_pass = schedule_makespan(times, tofs)
        print(f"  -- pass {pass_i}: {n_improved} improvements, "
              f"total shaved {pass_imp:.4f}d, mk={mk_pass:.4f}d", flush=True)
        if pass_imp < 1e-4:
            print(f"  no more improvements; stopping.", flush=True)
            break

    # Final UDP validation
    x_final = times + tofs + [float(p) for p in perm]
    fit_final = kt.fitness(x_final)
    feas_final = bool(kt.is_feasible(fit_final))
    mk_final = schedule_makespan(times, tofs)
    print(f"\nFinal: mk={mk_final:.4f}d  fit={fit_final}  feasible={feas_final}",
           flush=True)
    print(f"Total shaved from bank: {mk0 - mk_final:.4f}d", flush=True)

    # Bank update
    banked = False
    if feas_final and mk_final < BANK_MK - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {mk_final:.4f}d "
              f"({BANK_MK - mk_final:.4f}d under prev)", flush=True)

    # Verdict
    if not feas_final:
        verdict = 'inconclusive (refinement broke feasibility)'
    elif mk_final < BANK_MK - 1e-4:
        verdict = 'refutes walk_perm_chrono-as-optimal (C6 confirmed)'
    elif abs(mk_final - mk0) < 1e-4:
        verdict = 'supports bank as locally optimal under continuous (times, tofs)'
    else:
        verdict = 'inconclusive'

    print(f"\n=== E-519b VERDICT ===  {verdict}", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_mk_before': float(mk0),
        'mk_after': float(mk_final),
        'shaved_d': float(mk0 - mk_final),
        'udp_feasible': feas_final,
        'verdict': verdict, 'banked': banked,
    }))


if __name__ == '__main__':
    main()
