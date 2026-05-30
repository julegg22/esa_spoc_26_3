"""E-501 — Ch2 small time-expanded CP-SAT lower bound.

Audit prescribes: build a global LB to test whether R3 = 111.76 d is
reachable in the impulsive architecture.

Model: time-expanded ATSP with chronological constraint.
  variables:
    x[i][j][k] ∈ {0,1}  use edge i→j at sequence-position k (k=0..n-2)
    t[k] ∈ [0, T_max]  integer 0.1d quanta — departure time of leg k
    tof[k] ∈ feasible-set per leg — also 0.1d quanta
    exc_used[k] ∈ {0,1}  is leg k an exception
  objective: minimise t[n-2] + tof[n-2]
  constraints:
    Hamiltonian path on order (exactly one out per node, one in)
    chronological: t[k+1] >= t[k] + tof[k]
    sum exc_used <= 5
    per-leg: if x[i][j][k]=1 then (t[k], tof[k]) must satisfy
             dv(i,j,t[k],tof[k]) <= 100 OR (exc_used[k]=1 AND dv <= 600)

Direct encoding of dv per (i,j,t,tof) is intractable. Reduction:
- Pre-compute for each ordered (i,j), the set of feasible (t_q, tof_q)
  (t in 5d quanta, tof in 0.5d quanta) with dv ≤ 100 (cheap) or 600 (exc).
- Replace x[i][j][k] with x[i][j][q][k] (q = quantized (t,tof) cell).

This gives the LP relaxation a strong LB even without full multistart.

Aggressive simplification (this script): drop the per-leg dv table from
CP-SAT and use the precomputed per-pair min_tof matrix directly. Then:
- ATSP on the directed graph with cost min_tof_cheap[i,j] (or
  min_tof_exc[i,j] if cheap is inf and exc-budget allows).
- Add chronological constraint: t[k+1] >= t[k] + min_tof_used[k].
  (THIS IS A RELAXATION: real t-coupling is tighter.)
- Solve with CP-SAT.

If the relaxed LB > 111.76, the architecture cannot reach R3 and we
have proof. If LB < bank − 5, levers exist.

Run: python scripts/ch2_e501_cpsat_lb.py
"""
from __future__ import annotations
import sys, time, json
import numpy as np
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("ortools not installed; install via pip install ortools", flush=True)
    sys.exit(1)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
MTC_PATH = '/tmp/ch2_small_mtc.npy'
MTE_PATH = '/tmp/ch2_small_mte.npy'

# Quantization: 0.01 d = 14.4 min — fine enough for makespan reasoning
QUANTUM = 0.01


def main(time_limit_s=600):
    kt = KTTSP(INST)
    n = kt.n
    mtc = np.load(MTC_PATH)
    mte = np.load(MTE_PATH)

    # Edge costs in quanta. We allow each edge to be used either as cheap or exc.
    Q_MAX = int(round(kt.max_time / QUANTUM))  # 20000 quanta over 200 d
    print(f"n={n}  Q_MAX={Q_MAX}  cheap edges={(mtc<np.inf).sum()}  exc edges={(mte<np.inf).sum()}",
           flush=True)

    # Build cost matrices in quanta. Cheap is preferred; exc has a flag.
    INF = Q_MAX * 2
    cost_cheap = np.full((n, n), INF, dtype=np.int64)
    cost_exc = np.full((n, n), INF, dtype=np.int64)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if np.isfinite(mtc[i, j]):
                cost_cheap[i, j] = int(round(max(mtc[i, j], 0.01) / QUANTUM))
            if np.isfinite(mte[i, j]):
                cost_exc[i, j] = int(round(max(mte[i, j], 0.01) / QUANTUM))

    print(f"cost stats — cheap min/median = {cost_cheap[cost_cheap<INF].min()} / "
          f"{int(np.median(cost_cheap[cost_cheap<INF]))} quanta", flush=True)

    m = cp_model.CpModel()
    # Binary x[i][j] = use directed edge i->j (Hamiltonian path)
    x = {}
    use_exc = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if cost_cheap[i, j] < INF or cost_exc[i, j] < INF:
                x[i, j] = m.NewBoolVar(f'x_{i}_{j}')
                use_exc[i, j] = m.NewBoolVar(f'e_{i}_{j}')
                # If only exc-reachable, force use_exc
                if cost_cheap[i, j] >= INF:
                    m.Add(use_exc[i, j] >= x[i, j])
                # use_exc only if x is set
                m.Add(use_exc[i, j] <= x[i, j])

    # Out-degree: exactly one out per node, except sink (last)
    # Use position-based encoding via single Hamiltonian-path with AddCircuit-like trick.
    # Simpler: in-degree and out-degree constraints + subtour elim via timing.
    # We use CP-SAT's AddCircuit, but for HAMILTONIAN PATH we need a dummy node trick:
    # add dummy node n connected to all with cost 0; then circuit = Hamiltonian path.
    arcs = []
    dummy = n
    for i in range(n):
        for j in range(n):
            if (i, j) in x:
                arcs.append((i, j, x[i, j]))
        # dummy → i (start) with literal
        s = m.NewBoolVar(f'start_{i}')
        arcs.append((dummy, i, s))
        # i → dummy (end) with literal
        e = m.NewBoolVar(f'end_{i}')
        arcs.append((i, dummy, e))
    # self-loop on dummy (required for circuit)
    arcs.append((dummy, dummy, m.NewConstant(0)))

    m.AddCircuit(arcs)

    # Position-based timing: t[k] for k in 0..n-1 (node times)
    t_node = [m.NewIntVar(0, Q_MAX, f't_n{i}') for i in range(n)]
    # For each used arc (i,j) with cost c, t_node[j] >= t_node[i] + c
    M = Q_MAX + 1
    for (i, j) in x:
        # cost depends on use_exc: if cheap available use it, else exc cost
        # We use a max-trick: chosen cost = use_exc ? cost_exc : cost_cheap (if exists)
        if cost_cheap[i, j] < INF and cost_exc[i, j] < INF:
            cij = m.NewIntVar(min(cost_cheap[i,j], cost_exc[i,j]),
                              max(cost_cheap[i,j], cost_exc[i,j]),
                              f'c_{i}_{j}')
            m.Add(cij == int(cost_cheap[i,j])).OnlyEnforceIf(use_exc[i,j].Not())
            m.Add(cij == int(cost_exc[i,j])).OnlyEnforceIf(use_exc[i,j])
        elif cost_cheap[i, j] < INF:
            cij = int(cost_cheap[i, j])
        else:
            cij = int(cost_exc[i, j])
        # t_node[j] >= t_node[i] + cij  IFF x[i,j]=1
        m.Add(t_node[j] >= t_node[i] + cij).OnlyEnforceIf(x[i, j])

    # Exception count <= 5
    m.Add(sum(use_exc.values()) <= kt.n_exc)

    # Objective: maximise t_end - t_start of the path → minimise the end time
    # Path start: t_node[start_node] = 0 (it's the first)
    # We don't know start a priori; use max(t_node) as the makespan (sink time)
    # = max time among all nodes.
    makespan = m.NewIntVar(0, Q_MAX, 'makespan')
    for i in range(n):
        m.Add(makespan >= t_node[i])
    m.Minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    print(f"\nSolving CP-SAT (time_limit={time_limit_s}s, 8 workers)...", flush=True)
    t0 = time.time()
    status = solver.Solve(m)
    wall = time.time() - t0
    s_name = solver.StatusName(status)
    print(f"\nStatus: {s_name}  wall={wall:.0f}s", flush=True)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        mk = solver.Value(makespan) * QUANTUM
        print(f"Makespan (best feasible found): {mk:.3f} d", flush=True)
        # Reconstruct path
        nxt = {}
        for (i, j), v in x.items():
            if solver.Value(v):
                nxt[i] = j
        # start = node with no in-edge in nxt
        in_set = set(nxt.values())
        starts = [i for i in range(n) if i not in in_set]
        if starts:
            cur = starts[0]
            path = [cur]
            while cur in nxt:
                cur = nxt[cur]
                path.append(cur)
            print(f"Path: {path}", flush=True)
            n_exc = sum(1 for (i, j) in x if solver.Value(use_exc.get((i, j), 0)))
            print(f"# exc used: {n_exc}/{kt.n_exc}", flush=True)
        lb = solver.BestObjectiveBound() * QUANTUM
        print(f"\n>>> LB on makespan: {lb:.3f} d  (vs R3=111.76, bank=142.92)", flush=True)
        print(f">>> If LB < R3: R3 reachable in this RELAXED model", flush=True)
        print(f">>> If LB > bank: bank is sub-optimal in the relaxed model (gain available)",
               flush=True)
        return {"status": s_name, "makespan_d": mk,
                "lb_d": lb, "wall_s": wall}
    return {"status": s_name, "wall_s": wall}


if __name__ == "__main__":
    t_lim = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    print(json.dumps(main(time_limit_s=t_lim), indent=2))
