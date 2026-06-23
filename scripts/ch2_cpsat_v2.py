"""E-703 — Ch2-small CP-SAT v2: time-coupled TD-TSP with FLAW-A and FLAW-B fixed.

The bank-rep gate (ch2_cpsat_bankrep_check) proved the cache table is correct (47/48 bank legs
representable with no truncation) and that E-507's INFEASIBLE was the top_k-by-EARLIEST-ARRIVAL
truncation (FLAW B): a tour progresses in time, so late-tour legs depart at late epochs that
earliest-arrival truncation drops. Fixes here:
  FLAW B: candidate cells = cheapest-ARRIVAL cell per TIME-BIN (NBINS across [0,T]) -> full-horizon
          epoch coverage at bounded model size, instead of the 60 globally-earliest cells.
  FLAW A: objective = TRUE makespan = max-over-cities arrival (last-leg arrival), via per-city
          arrival IntVars, not max t_node (last departure).
Validates any solution via official kt.fitness; banks only if feasible AND <112.996.
Usage: python ch2_cpsat_v2.py [--time=1800] [--nbins=80] [--workers=4]"""
import sys, time, json
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ortools.sat.python import cp_model
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
TABLE = "/home/julian/Projects/esa_spoc_26_3/cache/ch2_small_tcoupled_ultrafine.npz"
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"


def build_candidates(cheap, exc, T, q, nbins):
    """FLAW-B fix: per (i,j), keep the cheapest-ARRIVAL cell in each of `nbins` time-bins over [0,T)."""
    n = cheap.shape[0]; binw = max(1, T // nbins); cand = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            bins = {}
            cq = np.where(np.isfinite(cheap[i, j]))[0]
            for qi in cq:
                tof_q = int(np.ceil(cheap[i, j, qi] / q)); b = int(qi) // binw
                key = int(qi) + tof_q
                if b not in bins or key < bins[b][3]:
                    bins[b] = (int(qi), tof_q, False, key)
            eq = np.where(np.isfinite(exc[i, j]))[0]
            for qi in eq:
                if np.isfinite(cheap[i, j, qi]):
                    continue
                tof_q = int(np.ceil(exc[i, j, qi] / q)); b = int(qi) // binw
                key = int(qi) + tof_q
                if b not in bins:                       # cheap preferred; exc only fills empty bins
                    bins[b] = (int(qi), tof_q, True, key)
            if bins:
                cand[i, j] = [(c[0], c[1], c[2]) for c in bins.values()]
    return cand


def main(time_limit=1800, nbins=80, workers=4):
    kt = KTTSP(INST); n = kt.n
    d = np.load(TABLE); cheap, exc, t_starts = d["cheap"], d["exc"], d["t_starts"]
    T = len(t_starts); q = float(t_starts[1] - t_starts[0])
    print(f"[CPSAT-v2] T={T} q={q}d nbins={nbins}", flush=True)
    cand = build_candidates(cheap, exc, T, q, nbins)
    ncell = sum(len(v) for v in cand.values())
    print(f"[CPSAT-v2] {len(cand)} pairs, {ncell} cells (time-binned)", flush=True)

    m = cp_model.CpModel()
    x = {}; use = {}; exc_lit = {}
    for (i, j), cells in cand.items():
        ps = []; es = []
        for qi, tof_q, is_e in cells:
            v = m.NewBoolVar(f"x_{i}_{j}_{qi}"); x[i, j, qi] = v; ps.append(v)
            if is_e:
                es.append(v)
        use[i, j] = m.NewBoolVar(f"u_{i}_{j}"); m.Add(sum(ps) == use[i, j])
        if es:
            ev = m.NewBoolVar(f"e_{i}_{j}"); m.Add(sum(es) == ev); m.Add(ev <= use[i, j]); exc_lit[i, j] = ev

    # Hamiltonian path via dummy
    dummy = n; arcs = []
    for (i, j), v in use.items():
        arcs.append((i, j, v))
    for i in range(n):
        arcs.append((dummy, i, m.NewBoolVar(f"s_{i}")))
        arcs.append((i, dummy, m.NewBoolVar(f"e_{i}")))
    arcs.append((dummy, dummy, m.NewConstant(0)))
    m.AddCircuit(arcs)
    m.Add(sum(v for v in exc_lit.values()) <= kt.n_exc)

    # chronological coupling + arrival vars (FLAW-A)
    t_node = [m.NewIntVar(0, T - 1, f"t_{i}") for i in range(n)]
    arr = [m.NewIntVar(0, T + 200, f"a_{i}") for i in range(n)]
    for (i, j), cells in cand.items():
        for qi, tof_q, _ in cells:
            v = x[i, j, qi]
            m.Add(t_node[i] == qi).OnlyEnforceIf(v)
            m.Add(arr[j] == qi + tof_q).OnlyEnforceIf(v)        # arrival at j via this edge
            m.Add(t_node[j] >= qi + tof_q).OnlyEnforceIf(v)     # depart j after arriving
    mk = m.NewIntVar(0, T + 200, "mk")
    for j in range(n):
        m.Add(mk >= arr[j])
    m.Minimize(mk)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers
    solver.parameters.log_search_progress = True
    print(f"[CPSAT-v2] solving (limit={time_limit}s, workers={workers}) ...", flush=True)
    t0 = time.time(); st = solver.Solve(m); wall = time.time() - t0
    name = solver.StatusName(st)
    print(f"[CPSAT-v2] status={name} wall={wall:.0f}s", flush=True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"[CPSAT-v2] no solution ({name}). If INFEASIBLE-after-gate-pass -> coupling/binning bug; reaudit.", flush=True)
        return
    mk_q = solver.Value(mk); print(f"[CPSAT-v2] model makespan {mk_q} quanta = {mk_q*q:.3f}d", flush=True)

    # reconstruct order
    nxt = {}; dep = {}; tof = {}
    for (i, j), cells in cand.items():
        if solver.Value(use[i, j]):
            for qi, tq, _ in cells:
                if solver.Value(x[i, j, qi]):
                    nxt[i] = j; dep[i] = qi * q; tof[i] = tq * q; break
    inset = set(nxt.values()); starts = [i for i in range(n) if i not in inset]
    if not starts:
        print("[CPSAT-v2] no start (cycle?) — reaudit", flush=True); return
    cur = starts[0]; perm = [cur]
    while cur in nxt:
        perm.append(nxt[cur]); cur = nxt[cur]
    print(f"[CPSAT-v2] order len {len(perm)} (need {n})", flush=True)
    if len(perm) != n:
        print("[CPSAT-v2] incomplete path — reaudit", flush=True); return

    # OFFICIAL validation: score the model-derived schedule via kt.fitness
    times = [dep[perm[k]] for k in range(n - 1)]; tofs = [tof[perm[k]] for k in range(n - 1)]
    fit = kt.fitness(list(times) + list(tofs) + [float(p) for p in perm])
    feas = kt.is_feasible(fit)
    print(f"[CPSAT-v2] OFFICIAL (model schedule): mk={fit[0]:.4f}d feas={feas} fit={list(fit)}", flush=True)
    if feas and fit[0] < 112.996 - 1e-3:
        print(f"[CPSAT-v2] *** OFFICIAL-VALID < 112.996: {fit[0]:.4f}d — guard-bank candidate (order saved) ***", flush=True)
        json.dump({"makespan": float(fit[0]), "perm": list(perm)}, open("/tmp/ch2_cpsat_v2_winner.json", "w"))
    else:
        print(f"[CPSAT-v2] model schedule not official-valid-better; the order may still retime better — "
              f"run S1-style free-epoch retime on perm before discarding.", flush=True)


if __name__ == "__main__":
    tl = 1800; nb = 80; w = 4
    for a in sys.argv[1:]:
        if a.startswith("--time="):
            tl = int(a.split("=")[1])
        elif a.startswith("--nbins="):
            nb = int(a.split("=")[1])
        elif a.startswith("--workers="):
            w = int(a.split("=")[1])
    main(time_limit=tl, nbins=nb, workers=w)
