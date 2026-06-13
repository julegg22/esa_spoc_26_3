"""Ch1 Beginner max-weight 3-D matching: scorer + CP-SAT MILP.

Usage:
    python scripts/ch1_matching_milp.py score <instance.txt> <solution.json>
    python scripts/ch1_matching_milp.py toy
    python scripts/ch1_matching_milp.py solve <instance.txt> <problem> <time_s> [out.json]
"""
import json
import sys
import time

INST_DIR = "reference/SpOC4/Challenge 1 Luna Tomato Logistics"
CHALLENGE = "spoc-4-luna-tomato-logistics"


def parse_instance(path):
    E, L, D, W = [], [], [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            e, l, d, w = line.split()
            E.append(int(e))
            L.append(int(l))
            D.append(int(d))
            W.append(float(w))
    return E, L, D, W


def score(binvec, E, L, D, W):
    """Return (mass, is_valid). Each e/l/d index may appear <=1 time among selected."""
    if len(binvec) != len(W):
        return 0.0, False
    used_e, used_l, used_d = set(), set(), set()
    mass = 0.0
    for i, x in enumerate(binvec):
        if x:
            if E[i] in used_e or L[i] in used_l or D[i] in used_d:
                return 0.0, False
            used_e.add(E[i])
            used_l.add(L[i])
            used_d.add(D[i])
            mass += W[i]
    return mass, True


def toy():
    rows = [
        (1, 1, 1, 6.202), (2, 2, 1, 6.386), (3, 2, 2, 2.641), (4, 3, 2, 0.577),
        (5, 3, 3, 0.254), (6, 4, 3, 8.042), (7, 4, 4, 8.221), (8, 5, 4, 8.800),
        (9, 5, 5, 0.213), (10, 6, 5, 4.275),
    ]
    E = [r[0] for r in rows]; L = [r[1] for r in rows]
    D = [r[2] for r in rows]; W = [r[3] for r in rows]
    v1 = [1, 0, 1, 0, 0, 0, 0, 0, 0, 0]
    v2 = [1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    print("toy [1,0,1,...] ->", score(v1, E, L, D, W), "(expect 8.843, True)")
    print("toy [1,1,0,...] ->", score(v2, E, L, D, W), "(expect 0.0, False)")


def load_solution(path):
    with open(path) as f:
        data = json.load(f)
    return data[0]["decisionVector"]


def solve(inst_path, problem, time_s, out_path=None, workers=2, hint_path=None):
    from ortools.sat.python import cp_model
    E, L, D, W = parse_instance(inst_path)
    n = len(W)
    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"x{i}") for i in range(n)]
    if hint_path:
        hv = load_solution(hint_path)
        for i in range(n):
            model.AddHint(x[i], int(hv[i]))
        print(f"  using hint from {hint_path}")
    # group transfers by each resource index
    from collections import defaultdict
    for arr in (E, L, D):
        groups = defaultdict(list)
        for i, v in enumerate(arr):
            groups[v].append(i)
        for idxs in groups.values():
            if len(idxs) > 1:
                model.Add(sum(x[i] for i in idxs) <= 1)
    SCALE = 1000  # weights have 3 decimals
    model.Maximize(sum(int(round(W[i] * SCALE)) * x[i] for i in range(n)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_s)
    solver.parameters.num_search_workers = workers
    t0 = time.time()
    st = solver.Solve(model)
    elapsed = time.time() - t0
    status = {cp_model.OPTIMAL: "OPTIMAL", cp_model.FEASIBLE: "FEASIBLE"}.get(st, str(st))
    binvec = [int(solver.Value(x[i])) for i in range(n)]
    best = solver.ObjectiveValue() / SCALE
    bound = solver.BestObjectiveBound() / SCALE
    mass, valid = score(binvec, E, L, D, W)
    gap = (bound - best) / bound if bound else 0.0
    print(f"[{problem}] status={status} elapsed={elapsed:.1f}s")
    print(f"  obj={best:.3f} bound={bound:.3f} gap={gap*100:.4f}%")
    print(f"  rescore mass={mass:.3f} valid={valid} nsel={sum(binvec)}")
    if out_path:
        rec = [{"decisionVector": binvec, "problem": problem, "challenge": CHALLENGE}]
        with open(out_path, "w") as f:
            json.dump(rec, f)
        print(f"  wrote {out_path}")
    return mass, valid, best, bound, gap, binvec


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "toy":
        toy()
    elif cmd == "score":
        E, L, D, W = parse_instance(sys.argv[2])
        bv = load_solution(sys.argv[3])
        print(score(bv, E, L, D, W))
    elif cmd == "solve":
        out = sys.argv[5] if len(sys.argv) > 5 else None
        hint = sys.argv[6] if len(sys.argv) > 6 else None
        solve(sys.argv[2], sys.argv[3], float(sys.argv[4]), out, hint_path=hint)
