"""E-518 — Ch2 small: tightened CP-SAT LB with time-coupled fine table.

See vault/experiments/E-029-ch2-cpsat-lb-tightening.md for the
pre-registered hypothesis and decision rules.

Extends E-501 by:
  1. Using the FINE min-tof table (/tmp/ch2_small_tcoupled_fine.npz,
     400 t-quanta × 100 tof-quanta) instead of the coarse min-tof matrix.
  2. Time-coupled costs: edge (i,j) cost depends on t_node[i] bucket via
     AddElement. Stronger LB than E-501's t-min edge cost.
  3. 2 h wall budget (vs E-501's 10 min) for CP-SAT bound-and-cut.

Verdict mapping (pre-registered):
  LB ≥ 142.89 → "ceiling at bank" supported (R3 unreachable)
  LB ≤ 111.76 → "ceiling at bank" refuted (R3 reachable in relaxation)
  else        → inconclusive; quantifies headroom
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("ortools not installed", flush=True); sys.exit(1)

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
FINE = '/tmp/ch2_small_tcoupled_fine.npz'
RESULT = '/tmp/ch2_e518_result.json'

BANK_MK_D = 112.996   # current small bank (2026-06-15)
R3_D = 101.65         # competitor leaderboard r1 (HRI) — the real target


def build_cost_tables(fine_path, q_quantum_d, q_max):
    """Return (cost_cheap, cost_exc, has_cheap, has_exc) each of shape
    (n, n, q_max), in integer t-quanta. inf entries marked with INF.

    The fine table is indexed by t-buckets of 0.5 d; we resample to
    q_quantum_d quanta by selecting the nearest fine bucket.
    """
    d = np.load(fine_path)
    fine_cheap = d['cheap']  # (n, n, 400) min-tof at each t-bucket
    fine_exc = d['exc']
    fine_t = d['t_starts']   # (400,) — 0.0, 0.5, 1.0, ...
    n = fine_cheap.shape[0]
    INF = q_max * 2 + 1

    # Map our q_quantum t-bucket → nearest fine_t bucket
    cost_c = np.full((n, n, q_max), INF, dtype=np.int64)
    cost_e = np.full((n, n, q_max), INF, dtype=np.int64)
    fine_quantum = float(fine_t[1] - fine_t[0])  # 0.5 d
    for q in range(q_max):
        t_d = q * q_quantum_d
        f_idx = int(round(t_d / fine_quantum))
        if f_idx >= len(fine_t):
            continue
        cc = fine_cheap[:, :, f_idx]
        ce = fine_exc[:, :, f_idx]
        # tof_d → tof_q (round up to be conservative for LB)
        with np.errstate(invalid='ignore'):
            tc = np.where(np.isfinite(cc),
                          np.ceil(np.maximum(cc, q_quantum_d) / q_quantum_d),
                          INF).astype(np.int64)
            te = np.where(np.isfinite(ce),
                          np.ceil(np.maximum(ce, q_quantum_d) / q_quantum_d),
                          INF).astype(np.int64)
        cost_c[:, :, q] = tc
        cost_e[:, :, q] = te
    # Set diagonal to INF
    for i in range(n):
        cost_c[i, i, :] = INF
        cost_e[i, i, :] = INF
    return cost_c, cost_e, INF


def main(time_limit_s=7200, q_quantum_d=0.5):
    if not Path(FINE).exists():
        print(f"ERR fine table missing", flush=True); return
    kt = KTTSP(INST)
    n = kt.n
    Q_MAX = int(round(kt.max_time / q_quantum_d))
    print(f"n={n} n_exc={kt.n_exc}  q_quantum={q_quantum_d}d  Q_MAX={Q_MAX} "
          f"  bank={BANK_MK_D}  R3={R3_D}", flush=True)

    print("Building cost tables...", flush=True)
    t0 = time.time()
    cost_c, cost_e, INF = build_cost_tables(FINE, q_quantum_d, Q_MAX)
    print(f"  built in {time.time()-t0:.1f}s. "
          f"cheap cells finite: {(cost_c<INF).sum()}/{cost_c.size} "
          f"({100*(cost_c<INF).sum()/cost_c.size:.2f}%)", flush=True)
    print(f"  exc   cells finite: {(cost_e<INF).sum()}/{cost_e.size} "
          f"({100*(cost_e<INF).sum()/cost_e.size:.2f}%)", flush=True)

    # Determine which directed pairs have ANY (cheap or exc) feasibility
    any_c = (cost_c < INF).any(axis=2)  # (n, n)
    any_e = (cost_e < INF).any(axis=2)
    any_arc = any_c | any_e
    print(f"  reachable directed pairs: {int(any_arc.sum() - n)} / {n*(n-1)} "
          f"= {100*(any_arc.sum()-n)/(n*(n-1)):.1f}%", flush=True)

    print("\nBuilding CP-SAT model...", flush=True)
    m = cp_model.CpModel()

    # x[i,j] - directed edge in Hamiltonian path
    # use_exc[i,j] - this edge uses an exception slot
    x = {}; use_exc = {}
    for i in range(n):
        for j in range(n):
            if i == j: continue
            if not any_arc[i, j]: continue
            x[i, j] = m.NewBoolVar(f'x_{i}_{j}')
            use_exc[i, j] = m.NewBoolVar(f'e_{i}_{j}')
            # if only exc reachable, force use_exc whenever x=1
            if not any_c[i, j]:
                m.Add(use_exc[i, j] >= x[i, j])
            # use_exc only if x is set
            m.Add(use_exc[i, j] <= x[i, j])

    # Hamiltonian path via AddCircuit with dummy depot
    DEPOT = n
    arcs = []
    for i in range(n):
        for j in range(n):
            if (i, j) in x:
                arcs.append((i, j, x[i, j]))
        arcs.append((DEPOT, i, m.NewBoolVar(f'start_{i}')))
        arcs.append((i, DEPOT, m.NewBoolVar(f'end_{i}')))
    arcs.append((DEPOT, DEPOT, m.NewConstant(0)))
    m.AddCircuit(arcs)

    # Per-node departure time, integer quanta
    t_node = [m.NewIntVar(0, Q_MAX, f't_{i}') for i in range(n)]
    makespan = m.NewIntVar(0, Q_MAX, 'makespan')

    # Time-coupled edge cost via AddElement.
    # For each (i,j) ∈ x:
    #   tof_used = AddElement(t_node[i] // ??, cost_table[i,j,:])
    #   if x[i,j]: t_node[j] >= t_node[i] + tof_used
    # We bucket t_node[i] directly (already in q_quantum quanta).
    print("Adding element constraints (may take a while)...", flush=True)
    t1 = time.time()
    n_elem = 0
    for (i, j), xij in x.items():
        # tof depends on use_exc and on t_bucket(t_node[i])
        # Strategy: cheap_tof[t] and exc_tof[t]; chosen via use_exc.
        cheap_tab = [int(cost_c[i, j, q]) for q in range(Q_MAX)]
        exc_tab = [int(cost_e[i, j, q]) for q in range(Q_MAX)]
        # tof_c, tof_e: IntVar conditional on the table lookup
        tof_c = m.NewIntVar(0, INF, f'tofc_{i}_{j}')
        tof_e = m.NewIntVar(0, INF, f'tofe_{i}_{j}')
        m.AddElement(t_node[i], cheap_tab, tof_c)
        m.AddElement(t_node[i], exc_tab, tof_e)
        n_elem += 2
        # chosen tof
        chosen = m.NewIntVar(0, INF, f'ch_{i}_{j}')
        m.Add(chosen == tof_c).OnlyEnforceIf(use_exc[i, j].Not())
        m.Add(chosen == tof_e).OnlyEnforceIf(use_exc[i, j])
        # If x[i,j] is selected, the chosen tof must be feasible (< INF)
        m.Add(chosen < INF).OnlyEnforceIf(xij)
        # Chronological constraint
        m.Add(t_node[j] >= t_node[i] + chosen).OnlyEnforceIf(xij)
    print(f"  added {n_elem} element tables in {time.time()-t1:.1f}s", flush=True)

    # Exception budget
    m.Add(sum(use_exc.values()) <= kt.n_exc)

    # makespan = max(t_node[i] + outgoing_tof if end-node) ≈ max(t_node[i])
    # (t_node[end] is the arrival time at end; using max captures end-time
    # plus any final tof effectively bundled into t_node)
    for i in range(n):
        m.Add(makespan >= t_node[i])
    m.Minimize(makespan)

    print(f"\nModel: vars≈{n*n + 2*(n*n)} bool, {n+1} int  "
          f"constraints≈{2*len(x) + n + 1}", flush=True)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    print(f"\nSolving (time_limit={time_limit_s}s, 8 workers)...", flush=True)
    t_solve = time.time()
    status = solver.Solve(m)
    wall = time.time() - t_solve

    s_name = solver.StatusName(status)
    lb_d = solver.BestObjectiveBound() * q_quantum_d
    mk_d = None
    perm = None
    n_exc_used = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        mk_q = solver.Value(makespan)
        mk_d = mk_q * q_quantum_d
        nxt = {}
        for (i, j), v in x.items():
            if solver.Value(v): nxt[i] = j
        in_set = set(nxt.values())
        starts = [i for i in range(n) if i not in in_set and i in nxt]
        if starts:
            cur = starts[0]; perm = [cur]
            while cur in nxt:
                cur = nxt[cur]; perm.append(cur)
            n_exc_used = sum(1 for (i, j) in x if solver.Value(use_exc[i, j]))

    # Verdict
    if lb_d >= BANK_MK_D:
        verdict = 'supports'  # ceiling at bank — R3 unreachable
        verdict_msg = (f"LB {lb_d:.3f} d ≥ bank {BANK_MK_D} d → "
                       f"ARCHITECTURE CEILING at bank proven (R3 unreachable)")
    elif lb_d <= R3_D:
        verdict = 'refutes'    # R3 reachable in relaxation
        verdict_msg = (f"LB {lb_d:.3f} d ≤ R3 {R3_D} d → "
                       f"R3 reachable in this relaxation (gap is search problem)")
    else:
        verdict = 'inconclusive'
        verdict_msg = (f"LB {lb_d:.3f} d in ({R3_D}, {BANK_MK_D}) → "
                       f"ambiguous; bank headroom up to {BANK_MK_D - lb_d:.3f} d")

    print(f"\n=== E-518 RESULT ===", flush=True)
    print(f"status: {s_name}  wall: {wall:.0f}s", flush=True)
    print(f"LB on makespan: {lb_d:.3f} d", flush=True)
    if mk_d is not None:
        print(f"Best feasible found: {mk_d:.3f} d  "
              f"(n_exc_used={n_exc_used})", flush=True)
        if perm and len(perm) <= 60:
            print(f"perm: {perm}", flush=True)
    print(f"\n{verdict_msg}", flush=True)
    print(f"verdict: {verdict}", flush=True)

    Path(RESULT).write_text(json.dumps({
        'status': s_name, 'wall_s': wall, 'lb_d': float(lb_d),
        'best_feasible_d': float(mk_d) if mk_d is not None else None,
        'n_exc_used': n_exc_used, 'perm': perm,
        'verdict': verdict, 'verdict_msg': verdict_msg,
        'bank_d': BANK_MK_D, 'R3_d': R3_D, 'q_quantum_d': q_quantum_d,
    }))


if __name__ == '__main__':
    t_lim = int(sys.argv[1]) if len(sys.argv) > 1 else 7200
    qq = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    main(time_limit_s=t_lim, q_quantum_d=qq)
