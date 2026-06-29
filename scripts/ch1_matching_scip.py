"""Attack the matching 'needs a stronger global exact solver than our restricted Gurobi' conclusion
(E-048/E-635): Gurobi is size-limited (can't load 25k vars), but SCIP (pyscipopt, free, UNLIMITED size)
is the strong global solver E-048 named and never ran. Full 3-index set-packing MIP, warm-started from
the bank, long time limit. Binary: SCIP finds > bank -> the 'walled' was an untested-solver artifact
(the leader's +65 is reachable); proves OPTIMAL at bank -> bank is the true optimum.
Guarded: writes candidate to /tmp + cache, banks NOTHING (re-score with official score()).
Usage: python ch1_matching_scip.py [matching-i|matching-ii] [time_s=1800]"""
import sys, json, time
from collections import defaultdict
import pyscipopt as scip
sys.path.insert(0, "scripts")
from ch1_matching_milp import parse_instance, score
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = {"matching-i": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
        "matching-ii": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt"}
BANK = {"matching-i": f"{ROOT}/solutions/upload/matching-i.json",
        "matching-ii": f"{ROOT}/solutions/upload/matching-ii.json"}


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-i"
    time_s = float(sys.argv[2]) if len(sys.argv) > 2 else 1800
    E, L, D, W = parse_instance(INST[problem]); n = len(W)
    bankvec = json.load(open(BANK[problem]))[0]["decisionVector"]
    bank_mass, bank_valid = score(bankvec, E, L, D, W)
    print(f"[SCIP {problem}] n={n} bank={bank_mass:.4f} valid={bank_valid} time={time_s}s", flush=True)

    m = scip.Model(problem)
    m.setParam("limits/time", time_s)
    m.setParam("display/freq", 5000)
    x = [m.addVar(vtype="B", name=f"x{i}", obj=W[i]) for i in range(n)]
    m.setMaximize()
    for arr in (E, L, D):
        groups = defaultdict(list)
        for i, v in enumerate(arr):
            groups[v].append(i)
        for idxs in groups.values():
            if len(idxs) > 1:
                m.addCons(scip.quicksum(x[i] for i in idxs) <= 1)
    # warm start from bank
    sol = m.createSol()
    for i in range(n):
        m.setSolVal(sol, x[i], float(int(round(bankvec[i]))))
    accepted = m.addSol(sol, free=True)
    print(f"[SCIP {problem}] warm-start bank accepted={accepted}", flush=True)

    t0 = time.time(); m.optimize(); el = time.time() - t0
    status = m.getStatus()
    obj = m.getObjVal() if m.getNSols() > 0 else 0.0
    bound = m.getDualbound()
    binvec = [int(round(m.getVal(x[i]))) for i in range(n)] if m.getNSols() > 0 else bankvec
    mass, valid = score(binvec, E, L, D, W)
    print(f"\n[SCIP {problem}] status={status} elapsed={el:.0f}s obj={obj:.4f} bound={bound:.4f} "
          f"gap={100*(bound-obj)/max(obj,1):.4f}% | rescore mass={mass:.4f} valid={valid} nsel={sum(binvec)}", flush=True)
    gain = mass - bank_mass
    verdict = "BEATS BANK" if (valid and mass > bank_mass + 1e-6) else "no gain"
    print(f"[SCIP {problem}] gain={gain:+.4f} vs bank {bank_mass:.4f} -> {verdict}", flush=True)
    if valid and mass > bank_mass + 1e-6:
        out = [{"decisionVector": [int(b) for b in binvec], "problem": problem,
                "challenge": "spoc-4-luna-tomato-logistics"}]
        json.dump(out, open(f"/tmp/ch1_{problem}_scip_candidate.json", "w"))
        json.dump(out, open(f"{ROOT}/cache/ch1_{problem}_scip_candidate.json", "w"))
        print(f"[SCIP {problem}] *** candidate saved -> ESCALATE (re-validate + submit) ***", flush=True)
    if status == "optimal":
        print(f"[SCIP {problem}] *** PROVEN OPTIMAL at {obj:.4f} ***", flush=True)


if __name__ == "__main__":
    main()
