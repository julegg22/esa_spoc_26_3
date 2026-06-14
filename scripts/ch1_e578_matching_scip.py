"""E-578: full-model exact SCIP on Ch1 matching (free uncapped B&B).

Deep-review 10:26 priced this as the #2 campaign lever: matching-i/ii are pure
binary set-packing ILPs where our free heuristics + HiGHS/CP-SAT plateau exactly
at the bank (deep local opt; CP-SAT-LNS solved 6000-var regions to OPTIMAL with
0 gain). The leaderboard r1 (33,555.61 / 73,714.03) is provably reachable by
SOME team, so the optimum >= r1. The one untried FREE exact engine is SCIP 10:
no size cap (unlike free Gurobi), strong clique cuts ideal for set-packing.

This measures the free-exact ceiling: SCIP reports both the incumbent (primal)
and the DUAL BOUND (proven upper bound on the optimum) — so we learn how much
headroom truly exists and whether a paid Gurobi license could buy anything SCIP
can't. Warm-started from the current bank. GUARD-BANKED: overwrite
solutions/upload/<problem>.json ONLY if strictly better AND feasible, after a
backup, with round-trip verify. Never submits.

Run:
  PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
    python -u scripts/ch1_e578_matching_scip.py matching-i 5400
  args: <problem> <time_limit_s> [threads]
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import time

import numpy as np
import pyscipopt as scip

from esa_spoc_26.ch1_matching import load_instance

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}
CHALLENGE = "spoc-4-luna-tomato-logistics"


def _feasible(e, ll, d, x):
    return all(arr[x == 1].size == np.unique(arr[x == 1]).size for arr in (e, ll, d))


def _groups(idx_arr):
    """node id -> list of transfer indices touching that node (size>1 only)."""
    order = np.argsort(idx_arr, kind="stable")
    g = {}
    for i in order:
        g.setdefault(int(idx_arr[i]), []).append(int(i))
    return [v for v in g.values() if len(v) > 1]


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-i"
    tlim = float(sys.argv[2]) if len(sys.argv) > 2 else 5400.0
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    path = INST[problem]
    bankp = f"solutions/upload/{problem}.json"

    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    bank_x = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
    assert bank_x.size == n, f"bank dim {bank_x.size} != instance {n}"
    assert _feasible(e, ll, d, bank_x), "current bank INFEASIBLE — abort"
    bank_mass = float(w[bank_x == 1].sum())
    print(f"{problem}: n={n}, bank mass {bank_mass:.3f} ({int(bank_x.sum())} sel); "
          f"SCIP tlim={tlim:.0f}s threads={threads}", flush=True)

    t0 = time.time()
    m = scip.Model(problem)
    m.setMaximize()
    xs = [m.addVar(vtype="B", obj=float(w[i]), name=f"x{i}") for i in range(n)]
    ncons = 0
    for arr in (e, ll, d):
        for grp in _groups(arr):
            m.addCons(scip.quicksum(xs[i] for i in grp) <= 1)
            ncons += 1
    print(f"model built: {n} vars, {ncons} packing constraints, "
          f"dt={time.time() - t0:.1f}s", flush=True)

    # warm-start from the bank (optimization only; guard-bank protects correctness)
    try:
        sol = m.createSol()
        for i in np.flatnonzero(bank_x == 1):
            m.setSolVal(sol, xs[int(i)], 1.0)
        accepted = m.addSol(sol)
        print(f"warm-start bank sol accepted={accepted}", flush=True)
    except Exception as ex:
        print(f"warm-start skipped ({ex})", flush=True)

    m.setParam("limits/time", tlim)
    if threads and threads > 1:
        m.setParam("parallel/maxnthreads", threads)
    # the dual gap is hopeless here (weak set-packing LP) — value comes from a
    # better INCUMBENT, so push primal heuristics hard.
    try:
        m.setHeuristics(scip.SCIP_PARAMSETTING.AGGRESSIVE)
    except Exception as ex:
        print(f"aggressive-heuristics setting skipped ({ex})", flush=True)
    m.optimize()

    status = m.getStatus()
    primal = m.getObjVal() if m.getNSols() > 0 else float("-inf")
    dual = m.getDualbound()
    print(f"\n=== SCIP {problem} status={status} ===", flush=True)
    print(f"  incumbent (primal) = {primal:.3f}", flush=True)
    print(f"  dual bound (ceil)  = {dual:.3f}  "
          f"(gap to optimum <= {dual - primal:.3f} = "
          f"{100 * (dual - primal) / max(primal, 1):.3f}%)", flush=True)
    print(f"  bank was {bank_mass:.3f}; SCIP delta = {primal - bank_mass:+.3f}",
          flush=True)
    print(f"  wall = {time.time() - t0:.0f}s", flush=True)

    # extract incumbent vector
    if m.getNSols() > 0:
        best = m.getBestSol()
        xb = np.array([1 if m.getSolVal(best, xs[i]) > 0.5 else 0
                       for i in range(n)], dtype=np.int8)
        xb_mass = float(w[xb == 1].sum())
    else:
        xb, xb_mass = bank_x.copy(), bank_mass

    if xb_mass > bank_mass + 1e-6 and _feasible(e, ll, d, xb):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("/tmp/bank_bak", exist_ok=True)
        shutil.copy(bankp, f"/tmp/bank_bak/{problem}_{ts}.json")
        shutil.copy(bankp, f"{bankp}.bak.scip")
        json.dump([{"decisionVector": xb.tolist(), "problem": problem,
                    "challenge": CHALLENGE}], open(bankp, "w"))
        rt = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
        rtm = float(w[rt == 1].sum())
        ok = _feasible(e, ll, d, rt) and abs(rtm - xb_mass) < 1e-6
        print(f"=== BANKED {problem} {bank_mass:.3f} -> {rtm:.3f} "
              f"(+{rtm - bank_mass:.3f}); round-trip {'OK' if ok else 'MISMATCH'} "
              f"===", flush=True)
    else:
        print(f"=== NO IMPROVEMENT over bank {bank_mass:.3f}; bank untouched. "
              f"Dual bound {dual:.3f} => "
              f"{'OPTIMAL/near-optimal, paid solver cannot help' if dual - bank_mass < 1 else f'headroom <= {dual - bank_mass:.1f} remains'} "
              f"===", flush=True)


if __name__ == "__main__":
    main()
