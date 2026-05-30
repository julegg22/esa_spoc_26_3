"""Chronological re-walk of a permutation using the time-coupled edge table.

Replaces the old walk_perm_chrono (with hostile-default wait_dt=1.0 and
grid step 0.1d) with a table lookup that uses the actual per-(t_start)
min-tof for each pair.

Returns (times, tofs, dvs, ok). Backward-compatible signature.
"""
from __future__ import annotations
import sys, json
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

TABLE_PATH = '/tmp/ch2_small_tcoupled.npz'


def load_tables():
    d = np.load(TABLE_PATH)
    return d['cheap'], d['exc']


def rewalk(perm, cheap_tbl, exc_tbl, n_exc_budget=5, T=200):
    """Walk perm chronologically with the time-coupled table.

    For each leg, pick earliest-arrival edge (cheap preferred unless exc
    is strictly faster AND budget allows).
    """
    cur = perm[0]
    t = 0.0
    times, tofs, dvs = [], [], []
    exc_used = 0
    for k in range(1, len(perm)):
        j = perm[k]
        t_min = int(np.ceil(t))
        if t_min >= T:
            return times, tofs, dvs, False, exc_used, k
        # Cheap candidates
        cs = cheap_tbl[cur, j, t_min:]
        ci = np.where(np.isfinite(cs))[0]
        best = None  # (t_dep, tof, arr, is_exc)
        if len(ci) > 0:
            # Take earliest-arrival in window (scan more than 5 since tof varies)
            for idx in ci[:min(50, len(ci))]:
                td = t_min + idx
                tf = cs[idx]
                arr = td + tf
                if best is None or arr < best[2]:
                    best = (int(td), float(tf), float(arr), False)
        # Exc candidates if budget allows
        if exc_used < n_exc_budget:
            es = exc_tbl[cur, j, t_min:]
            ei = np.where(np.isfinite(es))[0]
            for idx in ei[:min(50, len(ei))]:
                td = t_min + idx
                tf = es[idx]
                arr = td + tf
                # Only accept exc if strictly faster than cheap best (or cheap unavailable)
                if best is None or arr < best[2]:
                    best = (int(td), float(tf), float(arr), True)
        if best is None:
            return times, tofs, dvs, False, exc_used, k
        td, tf, arr, is_exc = best
        times.append(float(td))
        tofs.append(float(tf))
        dvs.append(None)  # placeholder; recompute via UDP if needed
        if is_exc:
            exc_used += 1
        t = arr
        cur = j
        if t > T:
            return times, tofs, dvs, False, exc_used, k
    return times, tofs, dvs, True, exc_used, len(perm) - 1


def validate_via_udp(kt, perm, times, tofs):
    x = times + tofs + [float(p) for p in perm]
    fit = kt.fitness(x)
    return fit, kt.is_feasible(fit)


def main():
    INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
            "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(INST)
    cheap_tbl, exc_tbl = load_tables()

    # 1. Re-walk BANK perm
    bank = json.load(open("/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_times = list(dv[:n-1])
    bank_tofs = list(dv[n-1:2*(n-1)])
    bank_mk = bank_times[-1] + bank_tofs[-1]
    print(f"Bank perm: mk={bank_mk:.4f}d  (UDP-validated)", flush=True)

    times, tofs, _dvs, ok, exc, leg = rewalk(
        bank_perm, cheap_tbl, exc_tbl, n_exc_budget=kt.n_exc)
    if not ok:
        print(f"  Table-rewalk INFEASIBLE at leg {leg}, exc={exc}", flush=True)
    else:
        new_mk = times[-1] + tofs[-1]
        fit, feas = validate_via_udp(kt, bank_perm, times, tofs)
        print(f"  Table-rewalk: mk={new_mk:.4f}d  exc={exc}  UDP={list(fit)}  feas={feas}",
              flush=True)
        if feas and new_mk < bank_mk - 0.01:
            print(f"  >>> IMPROVED by {bank_mk - new_mk:.4f}d via better grid",
                  flush=True)

    # 2. Diagnostic: per-leg comparison
    print(f"\n--- Per-leg cmp (bank vs table-rewalk) ---", flush=True)
    print(f"{'leg':>3} {'i->j':>7} {'bank_td':>8} {'bank_tof':>9} {'tbl_td':>7} {'tbl_tof':>8} {'cum_bank':>9} {'cum_tbl':>8}", flush=True)
    t_bank = 0; t_tbl = 0
    for i in range(min(15, n-1)):
        if i < len(times):
            t_bank = bank_times[i] + bank_tofs[i]
            t_tbl = times[i] + tofs[i]
            print(f"{i:>3} {bank_perm[i]:>2}->{bank_perm[i+1]:>2} "
                  f"{bank_times[i]:>8.3f} {bank_tofs[i]:>9.3f} "
                  f"{times[i]:>7.1f} {tofs[i]:>8.3f} "
                  f"{t_bank:>9.3f} {t_tbl:>8.3f}", flush=True)


if __name__ == "__main__":
    main()
