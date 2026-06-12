"""E-044 (script e575): Ch1 matching — Gurobi exact 3-index set-packing.

E-039 audit: the matching model/evaluator is faithful; the gap to the
leaderboard is EXACT-SOLVER POWER on the pure ILP. CP-SAT got bound 34,339
(gap 2.92%) and HiGHS timed out at 122%. Gurobi (now available, 13.0.2) is
the stronger solver E-039 named. 25k (matching-i) / 92k (matching-ii) binary
vars with 3 GUB constraint families is small for Gurobi.

Maximize sum_i w_i x_i  s.t.  for each e/l/d index, sum of x over rows
sharing that index <= 1. Warm-start (MIPStart) from the current bank.

GUARDED: writes candidate to /tmp ONLY; re-scores with the official-faithful
score(); banks NOTHING. Reports BEATS only if valid AND strictly > bank.
"""
import json
import sys
import time
from collections import defaultdict

import gurobipy as gp
from gurobipy import GRB

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/scripts")
from ch1_matching_milp import parse_instance, score  # noqa: E402

CHALLENGE = "spoc-4-luna-tomato-logistics"
INST = {
    "matching-i": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato "
                  "Logistics/matching-i.txt",
    "matching-ii": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato "
                   "Logistics/matching-ii.txt",
}
BANK = {
    "matching-i": f"{ROOT}/solutions/upload/matching-i.json",
    "matching-ii": f"{ROOT}/solutions/upload/matching-ii.json",
}


def solve(problem, time_s, threads):
    inst = INST[problem]
    E, L, D, W = parse_instance(inst)
    n = len(W)
    bankvec = json.load(open(BANK[problem]))[0]["decisionVector"]
    bank_mass, bank_valid = score(bankvec, E, L, D, W)
    print(f"[{problem}] n={n} bank={bank_mass:.4f} valid={bank_valid}",
          flush=True)

    m = gp.Model(problem)
    m.Params.OutputFlag = 1
    m.Params.TimeLimit = float(time_s)
    m.Params.Threads = int(threads)
    m.Params.MIPFocus = 2          # prove optimality / improve bound
    m.Params.MIPGap = 0.0

    x = m.addVars(n, vtype=GRB.BINARY, name="x")
    m.setObjective(gp.quicksum(W[i] * x[i] for i in range(n)), GRB.MAXIMIZE)

    for arr in (E, L, D):
        groups = defaultdict(list)
        for i, v in enumerate(arr):
            groups[v].append(i)
        for idxs in groups.values():
            if len(idxs) > 1:
                m.addConstr(gp.quicksum(x[i] for i in idxs) <= 1)

    for i in range(n):
        x[i].Start = int(round(bankvec[i]))

    t0 = time.time()
    m.optimize()
    elapsed = time.time() - t0

    binvec = [int(round(x[i].X)) for i in range(n)]
    mass, valid = score(binvec, E, L, D, W)
    bound = m.ObjBound
    obj = m.ObjVal
    status = m.Status
    print(f"\n[{problem}] status={status} elapsed={elapsed:.0f}s "
          f"obj={obj:.4f} bound={bound:.4f} gap={m.MIPGap*100:.4f}%",
          flush=True)
    print(f"[{problem}] rescore mass={mass:.4f} valid={valid} "
          f"nsel={sum(binvec)}", flush=True)

    out = f"/tmp/ch1_{problem}_gurobi_candidate.json"
    json.dump([{"decisionVector": binvec, "problem": problem,
                "challenge": CHALLENGE}], open(out, "w"))
    gain = mass - bank_mass
    verdict = ("BEATS BANK" if (valid and mass > bank_mass + 1e-6)
               else "no gain")
    print(f"[OUT] {out} gain={gain:+.4f} vs bank {bank_mass:.4f} -> {verdict}",
          flush=True)
    if status == GRB.OPTIMAL:
        print(f"[{problem}] *** PROVEN OPTIMAL at {obj:.4f} ***", flush=True)


if __name__ == "__main__":
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-i"
    time_s = float(sys.argv[2]) if len(sys.argv) > 2 else 1800
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    solve(problem, time_s, threads)
