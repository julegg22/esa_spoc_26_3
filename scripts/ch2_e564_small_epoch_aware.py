"""E-564 — Ch2 SMALL (easy.kttsp, n=49) epoch-aware component re-solve.

Ports the LARGE/MEDIUM recipe (E-561/562, E-563: medium 228.97->195.77d)
to small. Prior small attempts (E-508/509/529) were DP-on-fine + LNS
*permutation* search around the bank perm and are exhausted. The untried
lever (the one that broke medium): re-ORDER each cheap-arc component's
internal Hamiltonian path EPOCH-AWARE (tof at the TRUE arrival epoch of
the preceding leg, not a fixed reference time), keeping the inter-comp
bridge skeleton fixed, then DP-time bank-faithfully and re-score with the
official kt.fitness. Iterate to convergence.

Small cheap-arc structure (from /tmp/ch2_small_struct.npz):
  4 undirected components, sizes [40, 3, 3, 3]. comp0 (40) is one cheap
  SCC (7.7% dense). The three small comps (1,2,3) have ZERO cheap arcs to
  each other or to comp0 — EVERY inter-comp bridge is an EXCEPTION
  (dv in (100,600]). Bridge graph is a STAR on comp0. The bank skeleton:
    comp3(3) -> comp0(24) -> comp1(3) -> comp0(16) -> comp2(3)
  i.e. start in comp3 (no incoming bridge), out-and-back to comp1 mid-way,
  end in comp2; comp0 split into two runs (24, 16). Bridges @ legs
  [2,26,29,45]. That is 4 bridge exceptions. The bank ALSO spends a 5th,
  INTERNAL comp0 exception (leg 17, 31->30) — comp0 is cheap-SCC so a
  fully-cheap interior MAY exist; epoch-aware reordering is the lever to
  find it (or simply shorten the makespan).

Budget: n_exc=5. The 4 bridges are forced exceptions; the DP may spend the
remaining 1 on an internal comp0 hop if no cheap arc is reachable at the
walk epoch. We keep the bridge endpoint nodes fixed and only permute each
comp0 run's interior.

Table: /tmp/ch2_small_tcoupled_ultrafine.npz is the FULL dense fine table
(49x49x4000, q=0.05d, 160 tof pts to 8d) — it serves as BOTH the
epoch-aware ordering driver AND the bank-faithful final DP timing (no
separate coarse/fine split needed at n=49).

Guarded output: write /tmp/ch2_small_epoch_candidate.json ONLY if the
official kt.fitness mk is strictly < the current bank and feasible.
NEVER touch solutions/upload/.
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from numba import njit
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

sys.stdout.reconfigure(line_buffering=True)

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
BANK = f"{ROOT}/solutions/upload/small.json"
TABLE = "/tmp/ch2_small_tcoupled_ultrafine.npz"
STRUCT = "/tmp/ch2_small_struct.npz"
CAND = "/tmp/ch2_small_epoch_candidate.json"

CURRENT_BANK = 116.37377097878698
R5_SMALL = 111.79

BIG = 10_000_000
SCALE = 1000.0
INF_INT = 10 ** 9
N_ITERS = int(os.environ.get("E564_ITERS", "8"))


class Table:
    def __init__(self, path, t_cap=None):
        d = np.load(path)
        self.cheap = d["cheap"]
        self.exc = d["exc"]
        self.t_starts = d["t_starts"]
        self.q = float(self.t_starts[1] - self.t_starts[0])
        if t_cap is not None:
            # truncate departure buckets above t_cap (days). The makespan is
            # ~116d; no leg of a sub-bank tour departs above ~120d, so the
            # higher buckets are pure overhead for the DP. tof depth keeps the
            # full 8d range (only the t-axis is capped).
            keep = int(t_cap / self.q)
            self.cheap = self.cheap[:, :, :keep]
            self.exc = self.exc[:, :, :keep]
            self.t_starts = self.t_starts[:keep]
        self.T = len(self.t_starts)
        self.n = self.cheap.shape[0]
        self.cheap_any = np.isfinite(self.cheap).any(axis=2)
        np.fill_diagonal(self.cheap_any, False)

    def bucket(self, t):
        b = int(round(t / self.q))
        return min(max(b, 0), self.T - 1)

    def cheap_tof(self, i, j, t):
        b0 = self.bucket(t)
        row = self.cheap[i, j]
        v = row[b0]
        if np.isfinite(v):
            return float(v)
        for b in range(b0 + 1, min(b0 + 60, self.T)):
            v = row[b]
            if np.isfinite(v):
                return float(v)
        return None

    def exc_tof(self, i, j, t):
        b0 = self.bucket(t)
        row = self.exc[i, j]
        v = row[b0]
        if np.isfinite(v):
            return float(v)
        for b in range(b0 + 1, min(b0 + 60, self.T)):
            v = row[b]
            if np.isfinite(v):
                return float(v)
        return None


def build_cost_epoch(tab, nodes, depart_epoch):
    """Epoch-aware cheap-only cost over a comp0 segment. BIG if not
    cheap-reachable at the walk epoch (keeps the interior cheap)."""
    m = len(nodes)
    C = np.full((m, m), BIG, dtype=np.int64)
    for a in range(m):
        i = nodes[a]
        t_i = depart_epoch[a]
        for b in range(m):
            if a == b:
                C[a][b] = 0
                continue
            j = nodes[b]
            if not tab.cheap_any[i, j]:
                continue
            tof = tab.cheap_tof(i, j, t_i)
            C[a][b] = int(round(tof * SCALE)) if tof is not None else BIG
    return C


def solve_open_path(C, start_idx, end_idx, time_limit_s, seed_order=None):
    m = C.shape[0]
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, :] = BIG
    D[:, depot] = BIG
    D[depot, depot] = 0
    D[depot, start_idx] = 0
    D[end_idx, depot] = 0

    mgr = pywrapcp.RoutingIndexManager(N, 1, depot)
    routing = pywrapcp.RoutingModel(mgr)

    def cb(fi, ti):
        return int(D[mgr.IndexToNode(fi)][mgr.IndexToNode(ti)])

    idx = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(idx)
    p = pywrapcp.DefaultRoutingSearchParameters()
    p.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION)
    p.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    p.time_limit.FromSeconds(time_limit_s)
    p.log_search = False
    if seed_order is not None:
        routing.CloseModelWithParameters(p)
        init = routing.ReadAssignmentFromRoutes([list(seed_order)], True)
        sol = (routing.SolveFromAssignmentWithParameters(init, p)
               if init is not None else routing.SolveWithParameters(p))
    else:
        sol = routing.SolveWithParameters(p)
    if sol is None:
        return None, None
    order, idx_ = [], routing.Start(0)
    while not routing.IsEnd(idx_):
        node = mgr.IndexToNode(idx_)
        if node != depot:
            order.append(node)
        idx_ = sol.Value(routing.NextVar(idx_))
    big = sum(1 for k in range(1, len(order))
              if C[order[k-1]][order[k]] >= BIG)
    return order, big


def build_leg_arrays(tab, perm):
    n_legs = len(perm) - 1
    T = tab.T
    q = tab.q
    c_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    e_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    for k in range(n_legs):
        i, j = perm[k], perm[k + 1]
        crow = tab.cheap[i, j]
        erow = tab.exc[i, j]
        for tp in range(T):
            cv = crow[tp]
            if np.isfinite(cv):
                c_tof[k, tp] = cv
                arr = tp + int(np.ceil(float(cv) / q))
                if arr < T:
                    c_arr[k, tp] = arr
            ev = erow[tp]
            if np.isfinite(ev):
                e_tof[k, tp] = ev
                arr = tp + int(np.ceil(float(ev) / q))
                if arr < T:
                    e_arr[k, tp] = arr
    return c_arr, c_tof, e_arr, e_tof


@njit(cache=True)
def _forward_dp(c_arr, e_arr, T, n_legs, n_exc_max):
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=np.bool_)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_ix = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True
    for k in range(n_legs):
        any_r = False
        for t in range(T):
            for e in range(n_exc_max + 1):
                if not reach[k, t, e]:
                    continue
                any_r = True
                for tp in range(t, T):
                    arr = c_arr[k, tp]
                    if arr < INF_INT and arr < T and not reach[k+1, arr, e]:
                        reach[k+1, arr, e] = True
                        pred_t[k+1, arr, e] = t
                        pred_e[k+1, arr, e] = e
                        pred_dep[k+1, arr, e] = tp
                        pred_ix[k+1, arr, e] = 0
                if e < n_exc_max:
                    for tp in range(t, T):
                        arr = e_arr[k, tp]
                        if arr < INF_INT and arr < T and not reach[k+1, arr, e+1]:
                            reach[k+1, arr, e+1] = True
                            pred_t[k+1, arr, e+1] = t
                            pred_e[k+1, arr, e+1] = e
                            pred_dep[k+1, arr, e+1] = tp
                            pred_ix[k+1, arr, e+1] = 1
        if not any_r:
            break
    return reach, pred_t, pred_e, pred_dep, pred_ix


def dp_time_perm(tab, perm, n_exc_max):
    c_arr, c_tof, e_arr, e_tof = build_leg_arrays(tab, perm)
    n_legs = len(perm) - 1
    T = tab.T
    q = tab.q
    reach, pt, pe, pd, pix = _forward_dp(c_arr, e_arr, T, n_legs, n_exc_max)
    sink = reach[n_legs]
    rows = np.where(sink.any(axis=1))[0]
    if len(rows) == 0:
        return None, None, False
    min_t = int(rows.min())
    e_used = int(np.where(sink[min_t])[0].min())
    legs = []
    k, t, e = n_legs, min_t, e_used
    while k > 0:
        dep = int(pd[k, t, e])
        isx = int(pix[k, t, e])
        legs.append((dep, isx))
        prev_t, prev_e = int(pt[k, t, e]), int(pe[k, t, e])
        k -= 1
        t, e = prev_t, prev_e
    legs.reverse()
    times = [dep * q for dep, _ in legs]
    tofs = [float(e_tof[k, dep] if isx else c_tof[k, dep])
            for k, (dep, isx) in enumerate(legs)]
    return times, tofs, True


def score(kt, perm, times, tofs):
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return x, fit, bool(kt.is_feasible(fit)), float(fit[0])


def decompose_bank(lbl, perm):
    comps = [int(lbl[p]) for p in perm]
    n = len(perm)
    bnds = [k for k in range(n - 1) if comps[k] != comps[k + 1]]
    segs, s = [], 0
    for b in bnds:
        segs.append((comps[s], list(perm[s:b + 1])))
        s = b + 1
    segs.append((comps[s], list(perm[s:])))
    return segs, bnds


def assemble(segs):
    full = []
    for _c, sg in segs:
        full.extend(sg)
    return full


def main():
    kt = KTTSP(INST)
    n = kt.n
    tab = Table(TABLE, t_cap=float(os.environ.get("E564_TCAP", "130")))
    lbl = np.load(STRUCT)["lbl"]

    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(x) for x in bank[2 * (n - 1):]]
    bank_mk = float(kt.fitness(bank)[0])
    print(f"[BASE] bank mk={bank_mk:.4f} (official) n={n} n_exc={kt.n_exc}",
          flush=True)

    segs0, bnds = decompose_bank(lbl, perm0)
    print(f"[STRUCT] segments(comp,len): "
          f"{[(c, len(sg)) for c, sg in segs0]} bridges@{bnds}", flush=True)

    full0 = assemble(segs0)
    print("[REPRO] DP-timing warmup (numba jit)...", flush=True)
    t0 = time.time()
    dtt, dtf, dok = dp_time_perm(tab, full0, kt.n_exc)
    bank_dp = None
    if dok:
        _x, fit, feas, mk = score(kt, full0, dtt, dtf)
        bank_dp = mk
        print(f"[REPRO] ultrafine-DP of bank perm: mk={mk:.4f} feas={feas} "
              f"viols={list(fit[1:])} ({time.time()-t0:.0f}s)", flush=True)
        # how many exc does the DP spend on the bank perm?
        nexc = sum(1 for k in range(len(full0)-1)
                   if (lambda i, j, t, tof:
                       kt.compute_transfer(i, j, float(t), float(tof)) > 100.0)
                   (full0[k], full0[k+1], dtt[k], dtf[k]))
        print(f"[REPRO] DP exc used on bank perm: {nexc}/{kt.n_exc}", flush=True)

    # Best perm tracked by the (now bank-faithful) ultrafine-DP metric.
    best_dp = bank_dp if bank_dp is not None else 1e9
    best_x = list(bank)
    best_full = full0

    cur_segs = segs0
    cur_times = list(dtt) if dok else list(bank[:n - 1])
    cur_full = full0

    for it in range(N_ITERS):
        print(f"\n===== EPOCH-AWARE ITER {it} =====", flush=True)
        ep = {}
        for k in range(len(cur_full) - 1):
            ep[cur_full[k]] = float(cur_times[k])
        ep[cur_full[-1]] = float(cur_times[-1])

        new_segs = []
        for si, (cid, sg) in enumerate(cur_segs):
            if len(sg) <= 3:
                new_segs.append((cid, sg))
                continue
            depart_epoch = [ep.get(nd, 0.0) for nd in sg]
            C = build_cost_epoch(tab, sg, depart_epoch)
            sidx, eidx = 0, len(sg) - 1
            seed = list(range(len(sg)))
            tl = 30 if len(sg) <= 30 else 60
            t0 = time.time()
            order_idx, big = solve_open_path(
                C, sidx, eidx, tl, seed_order=seed)
            if order_idx is None or big > 0:
                order_idx, big = list(range(len(sg))), 0
            new_sg = [int(sg[k]) for k in order_idx]
            new_segs.append((cid, new_sg))
            print(f"  seg{si} comp{cid} n={len(sg)} reorder big={big} "
                  f"{time.time()-t0:.0f}s", flush=True)

        full = assemble(new_segs)
        assert len(full) == n and len(set(full)) == n, "bad perm"

        tt, tf, dok = dp_time_perm(tab, full, kt.n_exc)
        if not dok:
            print(f"  [iter {it}] DP infeasible for reordered perm; "
                  f"keep iterating from prior.", flush=True)
            cur_segs = new_segs
            continue
        x, fit, feas, mk = score(kt, full, tt, tf)
        tof_arr = np.array(tf)
        print(f"  [iter {it}] DP mk={mk:.4f} feas={feas} viols={list(fit[1:])} "
              f"tof_sum={tof_arr.sum():.1f} max={tof_arr.max():.2f}",
              flush=True)
        if feas and mk < best_dp - 1e-6:
            best_dp, best_x, best_full = mk, x, full
            print(f"  [iter {it}] *** NEW BEST mk={best_dp:.4f} "
                  f"vs bank {bank_mk:.4f} ***", flush=True)

        cur_segs, cur_times, cur_full = new_segs, tt, full

    # ------------------------------------------------------------------
    # PHASE 2: bridge-endpoint perturbation search. The interior reorder
    # converged to the bank; the remaining DoF is WHICH comp0 nodes serve
    # as the 4 bridge endpoints (8-13 candidates each) and the comp0 split
    # position. We try, for each excursion, swapping its comp0-side
    # endpoint to an alternative cheap-reachable comp0 node, re-running the
    # interior reorder + DP-time, keeping anything that beats best.
    # Budget-bounded random restarts seeded from the best perm so far.
    # ------------------------------------------------------------------
    import random
    random.seed(0)
    exc_any = np.load(STRUCT)["exc_any"]
    c0_nodes = set(int(x) for x in np.where(lbl == 0)[0])
    budget_s = float(os.environ.get("E564_PHASE2_S", "5400"))
    t_start = time.time()
    tries = 0
    accepts = 0
    base_segs = decompose_bank(lbl, best_full)[0]
    while time.time() - t_start < budget_s:
        tries += 1
        # pick a random comp0 segment and a random alternative endpoint swap:
        # move a boundary comp0 node (first/last of a comp0 run) to a
        # different comp0 node that is exc-reachable to the adjacent small
        # comp, by relocating it within the run.
        segs = [(_c, list(sg)) for _c, sg in base_segs]
        # choose a comp0 run with >3 nodes
        c0runs = [si for si, (c, sg) in enumerate(segs)
                  if c == 0 and len(sg) > 4]
        if not c0runs:
            break
        si = random.choice(c0runs)
        cid, sg = segs[si]
        # relocate a random interior node to a random new position
        k = random.randrange(1, len(sg) - 1)
        node = sg.pop(k)
        ins = random.randrange(1, len(sg))
        sg.insert(ins, node)
        segs[si] = (cid, sg)
        full_p = assemble(segs)
        if len(set(full_p)) != n:
            continue
        # epoch-aware interior reorder of all comp0 runs from current timing
        ttp, tfp, dokp = dp_time_perm(tab, full_p, kt.n_exc)
        if not dokp:
            continue
        xp, fitp, feasp, mkp = score(kt, full_p, ttp, tfp)
        if feasp and mkp < best_dp - 1e-6:
            best_dp, best_x, best_full = mkp, xp, full_p
            base_segs = decompose_bank(lbl, best_full)[0]
            accepts += 1
            print(f"  [P2 try{tries}] *** NEW BEST mk={best_dp:.4f} ***",
                  flush=True)
        if tries % 2000 == 0:
            print(f"  [P2] {tries} tries, {accepts} accepts, "
                  f"best={best_dp:.4f}, {time.time()-t_start:.0f}s",
                  flush=True)
    print(f"[P2] done: {tries} tries, {accepts} accepts in "
          f"{time.time()-t_start:.0f}s", flush=True)

    print(f"\n[FINAL] best DP mk={best_dp:.4f} (official bank {CURRENT_BANK})",
          flush=True)

    if best_full == full0 or not (best_dp < CURRENT_BANK - 1e-4):
        print("[OUT] reordering gave NO improvement over the bank "
              f"({best_dp:.4f} vs {CURRENT_BANK:.4f}) — writing NOTHING.",
              flush=True)
        return

    # Independent re-validation through the official scorer.
    fit = kt.fitness(best_x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    perm = [int(round(v)) for v in best_x[2 * (n - 1):]]
    covered = len(set(perm)) == n and len(perm) == n
    print(f"[REVAL] mk={mk:.4f} feas={feas} viols={list(fit[1:])} "
          f"covered={covered}", flush=True)
    if not (feas and mk < CURRENT_BANK and covered
            and all(v == 0 for v in fit[1:])):
        print("[OUT] re-validation failed — writing NOTHING.", flush=True)
        return
    Path(CAND).write_text(json.dumps([{
        "decisionVector": best_x, "problem": "small",
        "challenge": CHALLENGE}]))
    print(f">>> WROTE candidate mk={mk:.4f}d -> {CAND} "
          f"(beats bank by {CURRENT_BANK - mk:.4f}d"
          f"{', BEATS r5!' if mk < R5_SMALL else ''})", flush=True)


if __name__ == "__main__":
    main()
