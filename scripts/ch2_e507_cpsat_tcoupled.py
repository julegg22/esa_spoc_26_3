"""E-507 — CP-SAT with full time coupling.

Uses the precomputed time-coupled edge table. For each ordered (i, j) and
feasible t_start quantum t_q, the tof is known. Model variables and
constraints:

  x[i,j,t_q] = 1 ⟺ use edge (i,j) with depart at t_q quantum
  per (i,j): sum_q x[i,j,q] <= 1   (at most one t_q chosen)
  per (i,j): use[i,j] = sum_q x[i,j,q]   (link to circuit)
  is_exc[i,j,q] = 1 if cell is exc-only (no cheap at this t_q)
  total_exc = sum (x*is_exc) <= 5
  Hamiltonian path via AddCircuit on dummy graph
  Chronological coupling:
    t_dep[i] = sum_q,j of x[i,j,q] * q
    For each (i,j,q) with x=1: t_dep[j] >= q + ceil(tof[i,j,q] / quantum)

Default: coarse 1d table; pass `fine=True` for the 0.25d table once ready.
"""
from __future__ import annotations
import sys, time, json
import numpy as np
from itertools import product
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

try:
    from ortools.sat.python import cp_model
except ImportError:
    print("ortools not installed", flush=True)
    sys.exit(1)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"


def load_table(fine: bool):
    if fine:
        d = np.load('/tmp/ch2_small_tcoupled_fine.npz')
    else:
        d = np.load('/tmp/ch2_small_tcoupled.npz')
    return d['cheap'], d['exc'], d['t_starts']


def build_and_solve(fine=False, time_limit_s=1800, top_k_per_pair=60,
                     warm_start_perm=None):
    kt = KTTSP(INST)
    cheap, exc, t_starts = load_table(fine)
    n = kt.n
    T = len(t_starts)
    quantum = float(t_starts[1] - t_starts[0])
    # Quantize tof in same units
    print(f"Loading {'FINE' if fine else 'coarse'} table: T={T}, quantum={quantum}d",
           flush=True)

    # Build candidate cells per (i,j). Keep only top-K cheapest per pair.
    # Each cell: (i, j, q, tof_quanta, is_exc, is_cheap)
    candidates = {}  # (i,j) -> list of (q, tof_q, is_exc_only)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            cells = []
            cheap_qs = np.where(np.isfinite(cheap[i, j]))[0]
            for q in cheap_qs:
                tof_q = int(np.ceil(cheap[i, j, q] / quantum))
                cells.append((int(q), tof_q, False))
            # Add exc cells only where cheap not available at this q
            exc_qs = np.where(np.isfinite(exc[i, j]))[0]
            for q in exc_qs:
                if not np.isfinite(cheap[i, j, q]):
                    tof_q = int(np.ceil(exc[i, j, q] / quantum))
                    cells.append((int(q), tof_q, True))
            # Keep top-K by arrival time (q + tof_q)
            cells.sort(key=lambda c: c[0] + c[1])
            cells = cells[:top_k_per_pair]
            if cells:
                candidates[i, j] = cells

    n_pairs = len(candidates)
    n_cells = sum(len(v) for v in candidates.values())
    print(f"Candidate pairs: {n_pairs}/{n*(n-1)}, cells (top-{top_k_per_pair}): {n_cells}",
           flush=True)

    m = cp_model.CpModel()
    # x[(i,j,q)] = 1 iff edge (i,j) used with depart at quantum q
    x = {}
    use_pair = {}  # use_pair[i,j] = sum_q x[i,j,q]
    is_exc_cell = {}  # 1 if x[i,j,q] active AND cell is exc
    for (i, j), cells in candidates.items():
        ps = []
        excs = []
        for q, tof_q, is_e in cells:
            v = m.NewBoolVar(f'x_{i}_{j}_{q}')
            x[i, j, q] = v
            ps.append(v)
            if is_e:
                excs.append(v)
        use_pair[i, j] = m.NewBoolVar(f'u_{i}_{j}')
        m.Add(sum(ps) == use_pair[i, j])
        if excs:
            is_exc_pair = m.NewBoolVar(f'ep_{i}_{j}')
            m.Add(sum(excs) == is_exc_pair)
            m.Add(is_exc_pair <= use_pair[i, j])
            is_exc_cell[i, j] = is_exc_pair
        else:
            is_exc_cell[i, j] = None

    # Hamilton path via dummy node
    dummy = n
    arcs = []
    for (i, j), v in use_pair.items():
        arcs.append((i, j, v))
    start_lits = []
    end_lits = []
    for i in range(n):
        s = m.NewBoolVar(f'start_{i}')
        e = m.NewBoolVar(f'end_{i}')
        arcs.append((dummy, i, s))
        arcs.append((i, dummy, e))
        start_lits.append(s)
        end_lits.append(e)
    arcs.append((dummy, dummy, m.NewConstant(0)))
    m.AddCircuit(arcs)

    # Exception count constraint
    excs_total = [v for v in is_exc_cell.values() if v is not None]
    m.Add(sum(excs_total) <= kt.n_exc)

    # Chronological coupling
    # t_node[i] = depart quantum at i. Range [0, T-1].
    t_node = [m.NewIntVar(0, T - 1, f't_n{i}') for i in range(n)]
    M = T  # big-M
    for (i, j), cells in candidates.items():
        # If use_pair[i,j]=1 and cell q chosen, t_node[i] == q AND t_node[j] >= q + tof_q
        for q, tof_q, _ in cells:
            v = x[i, j, q]
            # t_node[i] == q when v=1
            m.Add(t_node[i] == q).OnlyEnforceIf(v)
            # t_node[j] >= q + tof_q when v=1
            arr_q = min(q + tof_q, T - 1)
            m.Add(t_node[j] >= arr_q).OnlyEnforceIf(v)

    # Objective: minimize max t_node (= makespan in quanta)
    # Actually makespan = arrival at sink = max over all nodes of (t_node + outgoing_tof if any)
    # Simpler: minimize max t_node — proxy for last departure; add arrival of last leg via end_lits
    makespan_q = m.NewIntVar(0, T - 1, 'mk_q')
    for i in range(n):
        # For end node, makespan >= t_node[i] + tof of incoming edge.
        # Simplify: makespan >= t_node[i] always
        m.Add(makespan_q >= t_node[i])
    # Better: add for each used (i,j,q), makespan >= q + tof_q if it's the LAST edge.
    # AddCircuit handles end via end_lits. For each i, if end_lits[i]=1, then makespan >= t_node[i] + max_outgoing_tof
    # Simplification: relax — makespan = max t_node + small constant (1 quantum)
    m.Minimize(makespan_q)

    # Warm start (optional)
    if warm_start_perm is not None:
        # Set hints for x[i,j,q]: use perm to determine sequence
        pass  # skip for now

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True
    print(f"\nSolving (time_limit={time_limit_s}s)...", flush=True)
    t0 = time.time()
    status = solver.Solve(m)
    wall = time.time() - t0
    s_name = solver.StatusName(status)
    print(f"\nStatus: {s_name}, wall={wall:.0f}s", flush=True)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"status": s_name, "wall_s": wall}

    mk_q = solver.Value(makespan_q)
    mk = mk_q * quantum
    print(f"Makespan (LB on departure): {mk_q} quanta = {mk:.3f} d",
           flush=True)

    # Reconstruct path
    nxt = {}
    edge_t = {}
    edge_tof = {}
    edge_exc = {}
    for (i, j), cells in candidates.items():
        if solver.Value(use_pair[i, j]):
            for q, tof_q, is_e in cells:
                if solver.Value(x[i, j, q]):
                    nxt[i] = j
                    edge_t[i] = q
                    edge_tof[i] = tof_q * quantum
                    edge_exc[i] = is_e
                    break

    # Find start
    in_set = set(nxt.values())
    starts = [i for i in range(n) if i not in in_set]
    if not starts:
        print("WARN: no start found (cycle?)", flush=True)
        return {"status": s_name, "wall_s": wall, "mk_d_lb": mk}
    cur = starts[0]
    perm = [cur]
    times = []
    tofs = []
    while cur in nxt:
        nxt_n = nxt[cur]
        times.append(float(edge_t[cur] * quantum))
        tofs.append(float(edge_tof[cur]))
        perm.append(nxt_n)
        cur = nxt_n
    print(f"Path: {perm}", flush=True)
    n_exc = sum(1 for k in edge_exc.values() if k)
    print(f"# exc used: {n_exc}", flush=True)

    real_mk = times[-1] + tofs[-1] if times else 0.0
    print(f"Reconstructed mk (table units): {real_mk:.3f} d", flush=True)

    # VALIDATE via UDP + walk_perm_chrono (full Lambert)
    print("\n--- Validating with full-Lambert chronological walk ---",
           flush=True)
    times_lw, tofs_lw, _dvs, ok, exc_lw, _k = walk_perm_chrono(
        kt, perm, tof_window=18.0, n_steps=180, wait_steps=12, wait_dt=1.0)
    if ok:
        mk_lw = times_lw[-1] + tofs_lw[-1]
        x_full = times_lw + tofs_lw + [float(p) for p in perm]
        fit = kt.fitness(x_full)
        feas = kt.is_feasible(fit)
        print(f"Lambert walk: mk={mk_lw:.4f}d  fitness={list(fit)}  feas={feas}",
               flush=True)
        # Try finer-grid Lambert walks
        for ns, ws, wd in [(360, 100, 0.1), (480, 200, 0.05)]:
            times_v, tofs_v, _, ok_v, _, _ = walk_perm_chrono(
                kt, perm, tof_window=18.0, n_steps=ns,
                wait_steps=ws, wait_dt=wd)
            if ok_v:
                mk_v = times_v[-1] + tofs_v[-1]
                fit_v = kt.fitness(times_v + tofs_v + [float(p) for p in perm])
                feas_v = kt.is_feasible(fit_v)
                print(f"  ns={ns} wd={wd}: mk={mk_v:.4f}d feas={feas_v}",
                       flush=True)
                if feas_v and mk_v < mk_lw:
                    mk_lw, times_lw, tofs_lw = mk_v, times_v, tofs_v
                    feas, fit = feas_v, fit_v
        # Try with the BEST (mk_lw, times_lw, tofs_lw) so far
        # Bank update if improved
        if feas and mk_lw < 142.9183:
            from pathlib import Path
            bak = OUT + ".bak.20260530"
            if Path(OUT).exists() and not Path(bak).exists():
                Path(bak).write_bytes(Path(OUT).read_bytes())
                print(f"Backed up bank to {bak}", flush=True)
            Path(OUT).write_text(json.dumps([{
                "decisionVector": list(times_lw + tofs_lw + [float(p) for p in perm]),
                "problem": "small",
                "challenge": CHALLENGE}]))
            print(f">>> BANKED: mk={mk_lw:.4f}d ({142.9183 - mk_lw:.4f}d under)",
                   flush=True)
    else:
        print(f"Lambert walk INFEASIBLE at leg {_k}", flush=True)

    return {"status": s_name, "wall_s": wall, "mk_d_table": real_mk,
            "perm": perm}


if __name__ == "__main__":
    fine = '--fine' in sys.argv
    tl = 600
    for a in sys.argv[1:]:
        if a.startswith('--time='):
            tl = int(a.split('=')[1])
    print(json.dumps(build_and_solve(fine=fine, time_limit_s=tl), indent=2,
                     default=str))
