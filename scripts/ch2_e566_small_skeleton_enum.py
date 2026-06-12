"""E-049 (script e566): Ch2 SMALL structured SKELETON enumerator.

E-564 converged the bank's comp0 INTERIORS (epoch-aware reorder null) and
its Phase-2 only relocated nodes WITHIN a comp0 run -> it provably never
touched the SKELETON. E-565 (windowed exc-allowing LNS) was operationally
REFUTED: its repair generates exception-heavy candidates whose ultrafine-DP
blows up (state-space spin, no iterations in 8min). The lesson: to stay
fast we must keep every candidate at the FORCED bridge count (exactly the
structurally-required inter-component exceptions), so the DP sees a clean
cheap-interior + few-exception perm (~bank, ~1s) instead of an exc-heavy
degenerate one.

This enumerator searches the genuine remaining small DoF *structurally*:
  - the ROLE of each of the 3 tiny comps (which is start / mid / end): 6
  - the comp0 SPLIT (where the mid tiny-comp breaks comp0 into run1|run2)
  - the bridge ENDPOINTS (implied by the comp0 open-path ends + split)
  - tiny-comp internal order (3!=6 each)

Construction per candidate (always exactly 4 inter-comp bridges => DP stays
fast):
  start_c(3) -> [comp0 open path, prefix s] -> mid_c(3)
             -> [comp0 open path, suffix] -> end_c(3)
The comp0 open Hamiltonian path is solved ONCE per role assignment with the
validated epoch-aware cheap-only OR-Tools open-path solver (free endpoints),
using the bank timing as reference epochs. Then we sweep the split index and
the tiny-comp orderings, DP-time the FULL perm ultrafine (exact n_exc<=5),
official kt.fitness, and guard-write the best strict feasible improvement to
/tmp ONLY. Banks NOTHING.

Gap rationale: small idle is 6.375 d forced; bank tof_sum~110.0; the dense
competitor cluster at 111.75 must achieve a lower tof via DIFFERENT bridge
placement -> exactly the comp0-split / bridge-endpoint DoF swept here.
"""
from __future__ import annotations
import json
import os
import sys
import time
from itertools import permutations
from pathlib import Path

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
sys.path.insert(0, f"{ROOT}/scripts")
from numba import njit  # noqa: E402
from ortools.constraint_solver import pywrapcp, routing_enums_pb2  # noqa: E402
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP  # noqa: E402
from ch2_e564_small_epoch_aware import (  # noqa: E402
    Table, dp_time_perm, score, build_leg_arrays, BIG, SCALE, INF_INT)


# Bounded copy of E-564's _forward_dp: same exact transitions, but aborts
# once the number of reachable states exceeds `max_states`. The fine grid
# (T~2600) makes the exact DP fan out to O(T) states per leg for skeletons
# with dense cheap-arc availability -> minutes per candidate (this is what
# stalled E-565 and the first E-566 build). The bank perm is tight (few
# reachable states) and evaluates in ~1s; any candidate that explodes past
# the cap is almost certainly not a tight, near-floor solution, so skipping
# it is a sound screen rather than a correctness loss.
@njit(cache=True)
def _forward_dp_capped(c_arr, e_arr, T, n_legs, n_exc_max, max_states):
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=np.bool_)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_ix = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True
    # `visits` counts processed reachable (k,t,e) states. Each visit drives
    # the O(T) tp-loops, so it is the true work proxy; new-state counts can
    # stay low while a dense leg re-scans tp endlessly (re-setting already
    # True states), so capping new states does NOT bound runtime. We cap
    # visits and check per departure bucket -> hard per-candidate bound.
    visits = 0
    for k in range(n_legs):
        any_r = False
        for t in range(T):
            for e in range(n_exc_max + 1):
                if not reach[k, t, e]:
                    continue
                any_r = True
                visits += 1
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
                        if arr < INF_INT and arr < T \
                                and not reach[k+1, arr, e+1]:
                            reach[k+1, arr, e+1] = True
                            pred_t[k+1, arr, e+1] = t
                            pred_e[k+1, arr, e+1] = e
                            pred_dep[k+1, arr, e+1] = tp
                            pred_ix[k+1, arr, e+1] = 1
            if visits > max_states:
                return reach, pred_t, pred_e, pred_dep, pred_ix, False
        if not any_r:
            break
    return reach, pred_t, pred_e, pred_dep, pred_ix, True


def dp_time_perm_capped(tab, perm, n_exc_max, max_states):
    c_arr, c_tof, e_arr, e_tof = build_leg_arrays(tab, perm)
    n_legs = len(perm) - 1
    T = tab.T
    q = tab.q
    reach, pt, pe, pd, pix, ok_budget = _forward_dp_capped(
        c_arr, e_arr, T, n_legs, n_exc_max, max_states)
    if not ok_budget:
        return None, None, False, True   # aborted
    sink = reach[n_legs]
    rows = np.where(sink.any(axis=1))[0]
    if len(rows) == 0:
        return None, None, False, False
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
    return times, tofs, True, False

sys.stdout.reconfigure(line_buffering=True)

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/easy.kttsp")
BANK = f"{ROOT}/solutions/upload/small.json"
TABLE = "/tmp/ch2_small_tcoupled_ultrafine.npz"
STRUCT = "/tmp/ch2_small_struct.npz"
CURRENT_BANK = 116.37377097878698
R5_SMALL = 111.79
R3_SMALL = 108.77

CAND = os.environ.get("E566_OUT", "/tmp/ch2_small_skeleton_enum_cand.json")
TL = float(os.environ.get("E566_TL", "10800"))
TCAP = float(os.environ.get("E566_TCAP", "130"))
COMP0_SOLVE_S = int(os.environ.get("E566_C0SOLVE", "20"))
MAX_STATES = int(os.environ.get("E566_MAXSTATES", "1500000"))
SMOKE = os.environ.get("E566_SMOKE", "0") == "1"


def comp0_open_path(tab, nodes, depart_epoch, time_s):
    """Solve a cheap-only epoch-aware open Hamiltonian path over `nodes`
    with BOTH endpoints free (depot 0-cost to/from every node). Returns the
    node order or None. Cheap-only cost => the interior carries no exception;
    the only exceptions in the final perm are the 4 structural bridges."""
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
    depot = m
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    D[depot, depot] = 0
    D[depot, :m] = 0          # free START: depot -> any node
    D[:m, depot] = 0          # free END:   any node -> depot
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
    p.time_limit.FromSeconds(time_s)
    routing.CloseModelWithParameters(p)
    sol = routing.SolveWithParameters(p)
    if sol is None:
        return None
    order, it = [], routing.Start(0)
    while not routing.IsEnd(it):
        node = mgr.IndexToNode(it)
        if node != depot:
            order.append(node)
        it = sol.Value(routing.NextVar(it))
    if len(order) != m:
        return None
    return [int(nodes[k]) for k in order]


def tiny_orderings(nodes):
    """All distinct orderings (paths) of a tiny comp (<=3 nodes)."""
    return [list(p) for p in permutations(nodes)]


def main():
    kt = KTTSP(INST)
    n = kt.n
    tab = Table(TABLE, t_cap=TCAP)
    lbl = np.load(STRUCT)["lbl"]
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]

    # reference epochs from bank DP-timing (uncapped — bank is tight)
    tt0, tf0, dok0, _ = dp_time_perm_capped(tab, perm0, kt.n_exc, MAX_STATES)
    assert dok0, "bank not DP-timable"
    _x0, fit0, feas0, mk0 = score(kt, perm0, tt0, tf0)
    assert feas0, "bank infeasible under DP-timing"
    ep = {perm0[k]: float(tt0[k]) for k in range(len(tt0))}
    ep[perm0[-1]] = float(tt0[-1])

    comp_nodes = {c: [int(x) for x in np.where(lbl == c)[0]]
                  for c in sorted(set(int(v) for v in lbl))}
    c0 = comp_nodes[0]
    tiny_ids = [c for c in comp_nodes if c != 0]
    assert len(c0) == 40 and len(tiny_ids) == 3
    print(f"[E-566] n={n} bank mk={mk0:.4f} comp0={len(c0)} "
          f"tiny={tiny_ids} (each {[len(comp_nodes[c]) for c in tiny_ids]}) "
          f"bank tof_sum={np.array(tf0).sum():.2f}", flush=True)

    # comp0 open path per role-assignment depends only on the depart epochs,
    # which we hold at the bank reference -> solve ONCE, reuse for all roles.
    depart_c0 = [ep.get(nd, 0.0) for nd in c0]
    t_c0 = time.time()
    c0path = comp0_open_path(tab, c0, depart_c0, COMP0_SOLVE_S)
    if c0path is None:
        print("[E-566] comp0 open-path solve FAILED — abort.", flush=True)
        return
    print(f"[E-566] comp0 open path solved ({time.time()-t_c0:.0f}s), "
          f"ends {c0path[0]}..{c0path[-1]}", flush=True)

    best_mk = mk0
    best_x = None
    t0 = time.time()
    tried = 0
    feas_cnt = 0
    abort_cnt = 0
    dp_times = []

    role_perms = list(permutations(tiny_ids))  # 6: (start, mid, end)
    # split range: keep both comp0 runs non-trivial (>=2 nodes each)
    splits = list(range(2, len(c0) - 1))
    # The fine-grid DP costs ~seconds per candidate (the bank itself needs
    # 120k-800k reachable-state visits), so an exhaustive nested sweep would
    # only cover one corner of the skeleton space in any reasonable budget.
    # We RANDOM-SAMPLE (role, split, tiny-orderings) uniformly so a
    # time-bounded run explores the whole space, and the visit cap bounds
    # each evaluation. Banks nothing; best feasible improvement -> /tmp.
    rng = np.random.default_rng(int(os.environ.get("E566_SEED", "0")))
    ords = {c: tiny_orderings(comp_nodes[c]) for c in tiny_ids}

    while time.time() - t0 < TL:
        sc, mc, ec = role_perms[rng.integers(len(role_perms))]
        s = int(rng.choice(splits))
        run1, run2 = c0path[:s], c0path[s:]
        s_ord = ords[sc][rng.integers(len(ords[sc]))]
        m_ord = ords[mc][rng.integers(len(ords[mc]))]
        e_ord = ords[ec][rng.integers(len(ords[ec]))]
        perm = list(s_ord) + run1 + list(m_ord) + run2 + list(e_ord)
        if len(set(perm)) != n:
            continue
        tdp = time.time()
        tt, tf, dok, aborted = dp_time_perm_capped(
            tab, perm, kt.n_exc, MAX_STATES)
        dp_times.append(time.time() - tdp)
        tried += 1
        if aborted:
            abort_cnt += 1
        elif dok:
            _x, fit, feas, mk = score(kt, perm, tt, tf)
            if feas:
                feas_cnt += 1
            if feas and mk < best_mk - 1e-4:
                best_mk = mk
                best_x = _x
                tag = (" BEATS r3!" if mk < R3_SMALL else
                       " BEATS r5!" if mk < R5_SMALL else " <bank")
                Path(CAND).write_text(json.dumps([{
                    "decisionVector": _x, "problem": "small",
                    "challenge": CHALLENGE}]))
                print(f"[NEW BEST] mk={mk:.4f}{tag} roles(s{sc},m{mc},e{ec}) "
                      f"split={s} ({time.time()-t0:.0f}s, try {tried}) "
                      f"-> wrote cand", flush=True)
        if SMOKE and tried >= 30:
            dts = np.array(dp_times)
            print(f"[SMOKE] {tried} candidates, DP mean={dts.mean():.3f}s "
                  f"max={dts.max():.3f}s feas={feas_cnt} abort={abort_cnt}",
                  flush=True)
            return
        if tried % 100 == 0:
            dts = np.array(dp_times[-100:])
            print(f"[prog] tried={tried} feas={feas_cnt} abort={abort_cnt} "
                  f"best={best_mk:.4f} DPmean={dts.mean():.3f}s "
                  f"({time.time()-t0:.0f}s)", flush=True)

    _finish(best_mk, best_x, mk0, kt, n, CAND, tried, feas_cnt, abort_cnt,
            dp_times)


def _finish(best_mk, best_x, mk0, kt, n, cand, tried, feas_cnt, abort_cnt,
            dp_times):
    dts = np.array(dp_times) if dp_times else np.array([0.0])
    print(f"\n[FINAL] tried={tried} feas={feas_cnt} abort={abort_cnt} "
          f"best={best_mk:.4f} (bank {CURRENT_BANK}) "
          f"DPmean={dts.mean():.3f}s", flush=True)
    if best_x is None or not (best_mk < CURRENT_BANK - 1e-4):
        print("[FINAL] no improvement over bank — wrote nothing useful.",
              flush=True)
        return
    fit = kt.fitness(best_x)
    feas = bool(kt.is_feasible(fit))
    perm = [int(round(v)) for v in best_x[2 * (n - 1):]]
    covered = len(set(perm)) == n and len(perm) == n
    ok = feas and float(fit[0]) < CURRENT_BANK and covered \
        and all(v == 0 for v in fit[1:])
    print(f"[REVAL] mk={float(fit[0]):.4f} feas={feas} "
          f"viols={list(fit[1:])} covered={covered} ok={ok}", flush=True)
    if ok:
        Path(cand).write_text(json.dumps([{
            "decisionVector": best_x, "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> candidate stands mk={float(fit[0]):.4f}d -> {cand} "
              f"(beats bank by {CURRENT_BANK-float(fit[0]):.4f}d)", flush=True)


if __name__ == "__main__":
    main()
