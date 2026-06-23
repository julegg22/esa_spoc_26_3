"""E-703 pivot — FAITHFUL fast table-walk scheduler for Ch2-small, + bank positive control.

The CP-SAT stalled (intractable) and OR-Tools routing violates the time-coupling. The untested path:
order search scored by a FAITHFUL fast evaluator (prior order search used the +5.5d DP proxy or
coupling-violating relaxations). The ultrafine table (bank-representable per the gate) enables a fast
chronological earliest-cheap walk WITHOUT per-call Lambert.

DECISIVE positive control: does the table-walk of the BANK ORDER reproduce ~112.996d? If yes -> the
walk is faithful -> SA/LKH order search on it directly optimizes the true makespan. If it over-reports
(like the naive Lambert greedy's 161d), the greedy is too myopic and needs DP-over-epochs.

Usage: python ch2_faithful_walk.py"""
import sys, json
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
TABLE = "/home/julian/Projects/esa_spoc_26_3/cache/ch2_small_tcoupled_ultrafine.npz"
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
kt = KTTSP(INST); n = kt.n
d = np.load(TABLE); CHEAP, EXC, TS = d["cheap"], d["exc"], d["t_starts"]
Q = float(TS[1] - TS[0]); T = len(TS)


def walk(order, n_exc=5):
    """Chronological earliest-arrival table-walk. Per leg: from current epoch, take the earliest epoch
    with a finite CHEAP tof; else (budget) the earliest finite EXC tof. Returns (times, tofs, makespan, ok, exc_used)."""
    t_idx = 0; times = []; tofs = []; exc_used = 0
    for k in range(n - 1):
        i, j = order[k], order[k + 1]
        ci = CHEAP[i, j]; ei = EXC[i, j]
        # MIN-ARRIVAL cheap epoch >= t_idx (earliest-departure != earliest-arrival: a later q may have a
        # shorter tof and arrive sooner; min-arrival is optimal for a fixed order by domination).
        chosen = None
        qs = np.arange(t_idx, T)
        cvals = ci[t_idx:]; fin = np.isfinite(cvals)
        if fin.any():
            arr = qs[fin] * Q + cvals[fin]
            bi = int(np.argmin(arr)); q = int(qs[fin][bi]); chosen = (q, float(ci[q]), False)
        if chosen is None and exc_used < n_exc:
            evals = ei[t_idx:]; efin = np.isfinite(evals)
            if efin.any():
                arr = qs[efin] * Q + evals[efin]
                bi = int(np.argmin(arr)); q = int(qs[efin][bi]); chosen = (q, float(ei[q]), True)
        if chosen is None:
            return times, tofs, float("inf"), False, exc_used
        q, tof, is_e = chosen
        dep = q * Q
        times.append(dep); tofs.append(tof)
        if is_e:
            exc_used += 1
        # next departure must be >= arrival
        t_idx = int(np.ceil((dep + tof) / Q))
        if t_idx >= T:
            return times, tofs, float("inf"), False, exc_used
    return times, tofs, times[-1] + tofs[-1], True, exc_used


def main():
    x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    bank_order = [round(v) for v in x[2 * (n - 1):]]
    bank_mk = x[:n - 1][-1] + x[n - 1:2 * (n - 1)][-1]
    print(f"[FAITHFUL] bank official makespan = {bank_mk:.4f}d", flush=True)
    times, tofs, mk, ok, exc = walk(bank_order)
    print(f"[FAITHFUL] table-walk of BANK ORDER: mk={mk:.4f}d ok={ok} exc_used={exc}", flush=True)
    if not ok:
        print("[FAITHFUL] walk STRANDED on bank order -> greedy too myopic / table gap; needs DP-over-epochs.", flush=True)
        return
    # official re-score of the walk's schedule (must match within Lambert tol if table is faithful)
    fit = kt.fitness(list(times) + list(tofs) + [float(o) for o in bank_order])
    print(f"[FAITHFUL] OFFICIAL re-score of walk schedule: mk={fit[0]:.4f}d feas={kt.is_feasible(fit)} fit={list(fit)}", flush=True)
    gap = mk - bank_mk
    if abs(gap) < 2.0 and kt.is_feasible(fit):
        print(f"[FAITHFUL] VERDICT: walk reproduces bank within {gap:+.3f}d AND official-feasible -> FAITHFUL. "
              f"Order search (SA/LKH) on this walk directly optimizes the true makespan. PROCEED.", flush=True)
    else:
        print(f"[FAITHFUL] VERDICT: walk over-reports by {gap:+.3f}d (or infeasible) -> earliest-cheap greedy too "
              f"myopic. The faithful evaluator needs DP over (city, epoch) layers, not a greedy walk.", flush=True)


if __name__ == "__main__":
    main()
