"""E-563 — Ch2 MEDIUM epoch-aware component re-solve.

Ports the LARGE-instance recipe (E-561/E-562, 2225->1048.98d) to medium
(n=181). The bank (228.9748d) came from a DP-on-fine-table that fixed the
TIMING of a FIXED perm; later attempts only perm-MUTATED around it and
found nothing. The untried lever: re-ORDER each cheap-arc component's
internal Hamiltonian path EPOCH-AWARE (tof at the true arrival epoch),
re-assemble with fixed inter-component bridges, walk, validate via the
official kt.fitness, and ITERATE until makespan converges.

Medium cheap-arc structure (from /tmp/ch2_medium_fine_pair_set_v2.npz):
  4 strongly-connected components, sizes [121, 20, 20, 20].
  Inter-component bridge graph is a STAR centred on the big comp (1):
  smalls (0,2,3) connect ONLY to 1, never to each other. comp 2 has NO
  incoming bridge -> the tour MUST start in comp 2. Visiting comps 0 and
  3 forces out-and-back excursions from comp 1, so comp 1 is split into
  3 runs (this is FORCED by connectivity, not a flaw). The bank already
  realises this exact 6-segment / 5-bridge skeleton; we keep the skeleton
  (bridge endpoint nodes fixed) and only re-order each segment interior.

Epoch-aware cost: cheap[i,j,t]/exc[i,j,t] from the v2 fine table give the
earliest cheap/exc tof from i to j departing at epoch t (q=0.1d, T=5000).
Cost[a][b] for a segment = that tof at the epoch the walk DEPARTS node a.
BIG if never cheap-reachable (hard cheap-only constraint inside segments).

Guarded output: write /tmp/ch2_medium_epoch_candidate.json ONLY if the
official kt.fitness mk is strictly < 228.9748 and feasible. NEVER touch
solutions/upload/.
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

sys.stdout.reconfigure(line_buffering=True)

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/medium.kttsp")
BANK = f"{ROOT}/solutions/upload/medium.json"
TABLE = "/tmp/ch2_medium_fine_pair_set_v2.npz"
CAND = "/tmp/ch2_medium_epoch_candidate.json"

CURRENT_BANK = 228.9748
R3_MEDIUM = 216.95

BIG = 10_000_000          # truly non-cheap (forbidden inside a segment)
SCALE = 1000.0            # tof(days) -> int cost
N_ITERS = int(os.environ.get("E563_ITERS", "6"))


# ----------------------------------------------------------------------
# Epoch-aware cost table wrapper
# ----------------------------------------------------------------------
class Table:
    """Wraps the v2 fine table for epoch-aware tof lookups."""

    def __init__(self, path):
        d = np.load(path)
        self.cheap = d["cheap"]          # (n,n,T) earliest cheap tof or inf
        self.exc = d["exc"]              # (n,n,T) earliest exc(<=600) tof
        self.t_starts = d["t_starts"]    # (T,)
        self.q = float(self.t_starts[1] - self.t_starts[0])
        self.T = len(self.t_starts)
        self.n = self.cheap.shape[0]
        # precompute cheap-reachable adjacency (any epoch)
        self.cheap_any = np.isfinite(self.cheap).any(axis=2)
        np.fill_diagonal(self.cheap_any, False)

    def bucket(self, t):
        b = int(round(t / self.q))
        if b < 0:
            b = 0
        if b >= self.T:
            b = self.T - 1
        return b

    def cheap_tof(self, i, j, t):
        """Earliest cheap tof from i to j departing at/after epoch t.
        Searches forward a few buckets in case the exact epoch is a gap."""
        b0 = self.bucket(t)
        row = self.cheap[i, j]
        v = row[b0]
        if np.isfinite(v):
            return float(v)
        # small forward scan (cheap arcs finite at ~97% of epochs)
        for b in range(b0 + 1, min(b0 + 40, self.T)):
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
        for b in range(b0 + 1, min(b0 + 40, self.T)):
            v = row[b]
            if np.isfinite(v):
                return float(v)
        return None


def build_cost_epoch(tab, nodes, depart_epoch):
    """Epoch-aware cost over segment `nodes`. depart_epoch[a] = epoch at
    which the walk departs nodes[a] (estimated from the current walk).
    cost[a][b] = cheap tof(nodes[a]->nodes[b]) at that epoch; BIG if not
    cheap-reachable (keeps the segment a cheap-only Hamiltonian path)."""
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
            if tof is not None:
                C[a][b] = int(round(tof * SCALE))
            else:
                C[a][b] = BIG  # cheap somewhere but not at this epoch
    return C


def solve_open_path(C, start_idx, end_idx, time_limit_s, tag, seed_order=None):
    """Open Hamiltonian path start->end over all nodes minimising summed
    epoch-aware tof. Dummy depot links end->depot->start at 0."""
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
        if init is None:
            sol = routing.SolveWithParameters(p)
        else:
            sol = routing.SolveFromAssignmentWithParameters(init, p)
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
    big_jumps = sum(1 for k in range(1, len(order))
                    if C[order[k-1]][order[k]] >= BIG)
    return order, big_jumps


# ----------------------------------------------------------------------
# Chronological walk using the official-style find_transfer pattern.
# We use the fine TABLE for the cheap/exc tof (it IS a 0.1d-resolution
# scan equivalent), then ALWAYS re-score the final x with kt.fitness.
# ----------------------------------------------------------------------
def walk_table(tab, perm, n_exc_max):
    """Walk perm chronologically. For each leg use the table's epoch-aware
    earliest cheap tof; if none, spend an exception (earliest exc tof).
    Returns (times, tofs, ok, exc_used) or ok=False on dead-end."""
    t = 0.0
    times, tofs = [], []
    exc = 0
    cur = perm[0]
    for k in range(1, len(perm)):
        j = perm[k]
        tof = tab.cheap_tof(cur, j, t)
        is_exc = False
        if tof is None and exc < n_exc_max:
            tof = tab.exc_tof(cur, j, t)
            is_exc = tof is not None
        if tof is None:
            return times, tofs, False, exc, k
        times.append(t)
        tofs.append(tof)
        if is_exc:
            exc += 1
        t += tof
        cur = j
        if t > tab.t_starts[-1]:
            return times, tofs, False, exc, k
    return times, tofs, True, exc, len(perm) - 1


def score(kt, perm, times, tofs):
    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    return x, fit, bool(kt.is_feasible(fit)), float(fit[0])


# ----------------------------------------------------------------------
# DP-optimal timing for a FIXED perm (mirrors E-541's forward DP but
# pair-keyed). The greedy table-walk picks the EARLIEST cheap tof each
# leg; the DP can depart LATER to catch a shorter downstream tof — this
# is how the bank reached 228.97 vs a greedy walk. We build per-leg
# arrival-bucket tables from the v2 table then run the same forward DP.
# ----------------------------------------------------------------------
from numba import njit  # noqa: E402

INF_INT = 10 ** 9


def build_leg_arrays(tab, perm):
    """Per-leg (cheap/exc) arrival-bucket + tof tables for this perm."""
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
    """Return DP-optimal (times, tofs, ok) minimising makespan for the
    fixed perm under the exception budget, using the v2 table."""
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
        prev_t = int(pt[k, t, e])
        prev_e = int(pe[k, t, e])
        dep = int(pd[k, t, e])
        isx = int(pix[k, t, e])
        legs.append((dep, isx))
        k -= 1
        t, e = prev_t, prev_e
    legs.reverse()
    times = [dep * q for dep, _ in legs]
    tofs = [float(e_tof[k, dep] if isx else c_tof[k, dep])
            for k, (dep, isx) in enumerate(legs)]
    return times, tofs, True


# ----------------------------------------------------------------------
# FINE per-leg re-timing (matches E-540 bank resolution: 160 tof points,
# 0.1d t-quantum). The v2 table (40 tof points) is good enough to DRIVE
# the ordering search but ~19d too pessimistic on absolute makespan (it
# DP-times the bank perm at 248 vs the real 228.97). So the SINGLE best
# candidate perm gets a fine per-leg scan (parallel) before the final
# kt.fitness verdict. Cost ~ same as E-540 (180 legs) but we only do it
# for a handful of candidates, not every iteration.
# ----------------------------------------------------------------------
FINE_TOFS = np.linspace(0.025, 12.0, 160)
FINE_TQ = 0.1
FINE_TSTARTS = np.arange(0.0, 500.0, FINE_TQ)

_FKT = [None]


def _finit(inst):
    _FKT[0] = KTTSP(inst)


def _fscan(args):
    k, i, j = args
    kt = _FKT[0]
    nt = len(FINE_TSTARTS)
    cheap = np.full(nt, np.inf, dtype=np.float32)
    exc = np.full(nt, np.inf, dtype=np.float32)
    for ki, ts in enumerate(FINE_TSTARTS):
        if ts + FINE_TOFS[-1] > kt.max_time:
            break
        for tof in FINE_TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= 100.0:
                cheap[ki] = tof
                exc[ki] = tof
                break
            elif dv <= 600.0 and tof < exc[ki]:
                exc[ki] = tof
    return k, cheap, exc


def fine_time_perm(inst, perm, n_exc_max, workers=4):
    """Bank-faithful DP timing for `perm` via a fresh fine per-leg scan.
    Returns (times, tofs, ok). Expensive (~minutes); call sparingly."""
    import multiprocessing as mp
    n_legs = len(perm) - 1
    nt = len(FINE_TSTARTS)
    cheap = np.full((n_legs, nt), np.inf, dtype=np.float32)
    exc = np.full((n_legs, nt), np.inf, dtype=np.float32)
    legs = [(k, perm[k], perm[k + 1]) for k in range(n_legs)]
    with mp.Pool(workers, initializer=_finit, initargs=(inst,)) as p:
        for k, c, e in p.imap_unordered(_fscan, legs, chunksize=1):
            cheap[k] = c
            exc[k] = e
    # build arr buckets
    c_arr = np.full((n_legs, nt), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, nt), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, nt), INF_INT, dtype=np.int32)
    e_tof = np.full((n_legs, nt), np.nan, dtype=np.float32)
    for k in range(n_legs):
        for tp in range(nt):
            cv = cheap[k, tp]
            if np.isfinite(cv):
                c_tof[k, tp] = cv
                arr = tp + int(np.ceil(float(cv) / FINE_TQ))
                if arr < nt:
                    c_arr[k, tp] = arr
            ev = exc[k, tp]
            if np.isfinite(ev):
                e_tof[k, tp] = ev
                arr = tp + int(np.ceil(float(ev) / FINE_TQ))
                if arr < nt:
                    e_arr[k, tp] = arr
    reach, pt, pe, pd, pix = _forward_dp(c_arr, e_arr, nt, n_legs, n_exc_max)
    sink = reach[n_legs]
    rows = np.where(sink.any(axis=1))[0]
    if len(rows) == 0:
        return None, None, False
    min_t = int(rows.min())
    e_used = int(np.where(sink[min_t])[0].min())
    seq = []
    k, t, e = n_legs, min_t, e_used
    while k > 0:
        dep = int(pd[k, t, e])
        isx = int(pix[k, t, e])
        seq.append((dep, isx))
        prev_t = int(pt[k, t, e])
        prev_e = int(pe[k, t, e])
        k -= 1
        t, e = prev_t, prev_e
    seq.reverse()
    times = [dep * FINE_TQ for dep, _ in seq]
    tofs = [float(e_tof[k, dep] if isx else c_tof[k, dep])
            for k, (dep, isx) in enumerate(seq)]
    return times, tofs, True


# ----------------------------------------------------------------------
def decompose_bank(kt, lbl, perm):
    """Split the bank perm into component segments at the bridge legs.
    Returns list of (comp_id, [node ids]) preserving order."""
    comps = [int(lbl[p]) for p in perm]
    n = len(perm)
    bnds = [k for k in range(n - 1) if comps[k] != comps[k + 1]]
    segs = []
    s = 0
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
    tab = Table(TABLE)
    s = np.load("/tmp/ch2_e563_struct.npz")
    lbl = s["lbl"]

    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(x) for x in bank[2 * (n - 1):]]
    bank_mk = float(kt.fitness(bank)[0])
    print(f"[BASE] bank mk={bank_mk:.4f} (official)", flush=True)

    segs0, bnds = decompose_bank(kt, lbl, perm0)
    print(f"[STRUCT] segments: "
          f"{[(c, len(sg)) for c, sg in segs0]} bridges@{bnds}", flush=True)

    # Reproduce the bank via BOTH greedy table-walk and DP timing.
    full0 = assemble(segs0)
    tt, tf, ok, exc, _ = walk_table(tab, full0, kt.n_exc)
    if ok:
        _x, fit, feas, mk = score(kt, full0, tt, tf)
        print(f"[REPRO] greedy table-walk of bank perm: mk={mk:.4f} "
              f"feas={feas} exc={exc} viols={list(fit[1:])}", flush=True)
    print("[REPRO] DP-timing warmup (numba jit)...", flush=True)
    t0 = time.time()
    dtt, dtf, dok = dp_time_perm(tab, full0, kt.n_exc)
    bank_v2dp = None
    if dok:
        _x, fit, feas, mk = score(kt, full0, dtt, dtf)
        bank_v2dp = mk
        print(f"[REPRO] v2-DP-timing of bank perm: mk={mk:.4f} feas={feas} "
              f"viols={list(fit[1:])} ({time.time()-t0:.0f}s)", flush=True)
    print(f"[REPRO] NOTE: v2 table (40 tof) is ~{bank_v2dp - bank_mk:.1f}d "
          f"pessimistic vs the official bank ({bank_mk:.2f}). It drives the "
          f"RELATIVE ordering search; the single best perm is FINE-re-timed "
          f"(160 tof) before the official verdict.", flush=True)

    # Track best perm by the RELATIVE v2-DP metric (bank perm = baseline).
    best_v2dp = bank_v2dp if bank_v2dp is not None else 1e9
    best_full = full0          # best perm found
    best_x = list(bank)        # its decision vector (v2-DP timing)

    cur_segs = segs0
    cur_times = list(dtt) if dok else list(bank[:n - 1])
    cur_full = full0

    for it in range(N_ITERS):
        print(f"\n===== EPOCH-AWARE ITER {it} =====", flush=True)
        # departure epoch per node from the current walk's times
        ep = {}
        for k in range(len(cur_full) - 1):
            ep[cur_full[k]] = float(cur_times[k])
        ep[cur_full[-1]] = float(cur_times[-1])  # terminus (unused)

        new_segs = []
        ok_iter = True
        for si, (cid, sg) in enumerate(cur_segs):
            if len(sg) <= 2:
                new_segs.append((cid, sg))
                continue
            # Fixed endpoints: a segment's first node is the bridge target
            # (entry), its last node is the bridge source (exit). Keep both.
            start_node, end_node = sg[0], sg[-1]
            depart_epoch = [ep.get(nd, 0.0) for nd in sg]
            C = build_cost_epoch(tab, sg, depart_epoch)
            sidx = 0
            eidx = len(sg) - 1
            seed = list(range(len(sg)))  # identity = bank order (valid)
            tl = 15 if len(sg) <= 25 else 90
            t0 = time.time()
            order_idx, big = solve_open_path(
                C, sidx, eidx, tl, f"seg{si}c{cid}", seed_order=seed)
            if order_idx is None or big > 0:
                # fall back to bank order for this segment
                order_idx = list(range(len(sg)))
                big = 0
            new_sg = [int(sg[k]) for k in order_idx]
            new_segs.append((cid, new_sg))
            print(f"  seg{si} comp{cid} n={len(sg)} "
                  f"reorder big={big} {time.time()-t0:.0f}s", flush=True)

        full = assemble(new_segs)
        assert len(full) == n and len(set(full)) == n, "bad perm"

        # DP-optimal timing (bank-faithful); fall back to greedy walk.
        tt, tf, dok = dp_time_perm(tab, full, kt.n_exc)
        if not dok:
            tt, tf, gok, _exc, leg = walk_table(tab, full, kt.n_exc)
            if not gok:
                print(f"  timing FAILED at leg {leg} "
                      f"({full[leg]}->{full[leg+1]}); abort iter.", flush=True)
                break
        x, fit, feas, mk = score(kt, full, tt, tf)
        tof_arr = np.array(tf)
        print(f"  [iter {it}] v2-DP mk={mk:.4f} feas={feas} "
              f"viols={list(fit[1:])} tof_sum={tof_arr.sum():.1f} "
              f"max={tof_arr.max():.2f} >3d={int((tof_arr>3).sum())}",
              flush=True)

        if feas and mk < best_v2dp - 1e-6:
            best_v2dp = mk
            best_x = x
            best_full = full
            print(f"  [iter {it}] *** NEW BEST (v2-DP) mk={best_v2dp:.4f} "
                  f"vs bank-v2dp {bank_v2dp:.4f} ***", flush=True)

        # iterate from this timing (epochs shifted)
        cur_segs = new_segs
        cur_times = tt  # departure epochs for legs 0..n-2
        cur_full = full

    print(f"\n[FINAL] best v2-DP mk={best_v2dp:.4f} "
          f"(bank-v2dp {bank_v2dp:.4f}, official bank {CURRENT_BANK})",
          flush=True)

    if best_full == full0 or best_v2dp >= (bank_v2dp or 1e9) - 1e-6:
        print("[OUT] reordering gave NO relative v2-DP improvement over the "
              "bank perm — fine re-timing cannot recover the gap. "
              "Writing NOTHING.", flush=True)
        return

    # The reordered perm beats the bank perm on the v2-DP proxy. Now do the
    # bank-faithful FINE re-time (160 tof) and the OFFICIAL verdict.
    print(f"[FINE] re-timing best perm with 160-tof fine scan "
          f"(parallel, ~minutes)...", flush=True)
    t0 = time.time()
    ftt, ftf, fok = fine_time_perm(INST, best_full, kt.n_exc, workers=4)
    if not fok:
        print("[FINE] fine timing found no feasible DP sink — NOTHING.",
              flush=True)
        return
    best_x, _fit, _feas, fmk = score(kt, best_full, ftt, ftf)
    print(f"[FINE] fine-timed best perm: official mk={fmk:.4f} "
          f"feas={_feas} viols={list(_fit[1:])} ({time.time()-t0:.0f}s)",
          flush=True)

    if not (_feas and fmk < CURRENT_BANK - 1e-4):
        print(f"[OUT] fine-timed mk {fmk:.4f} did NOT beat bank "
              f"{CURRENT_BANK} (or infeasible) — writing NOTHING.", flush=True)
        return

    # Independent re-validation via official scorer
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
        "decisionVector": best_x, "problem": "medium",
        "challenge": CHALLENGE}]))
    print(f">>> WROTE candidate mk={mk:.4f}d -> {CAND}", flush=True)


if __name__ == "__main__":
    main()
