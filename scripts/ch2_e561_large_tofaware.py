"""E-561 — Ch2 LARGE tof-aware re-ordering.

The working 2225.16d bank used an OR-Tools cheap-Hamiltonian whose edge
cost was 1 for every cheap edge -> it minimised the *number* of
non-cheap edges (0 big-jumps) but treated all cheap edges as equal,
yielding a heavy tail (220 legs > 3d summing ~1040d).

This re-orders for SHORT tof instead. We keep the PROVEN 5-bridge
"comp0-last" topology and the exact bridge endpoint nodes (so 5 exc /
0 internal big-jumps is guaranteed), and only re-order the INTERIOR of
each of the 6 endpoint-constrained open paths:

  oa : small3  free-start  -> tail 51
  segA: comp0  start 2      -> end 557
  ob : small1  head 462     -> tail 673
  segB: comp0  start 543    -> end 450
  oc : small0  head 69      -> tail 267
  segC: comp0  start 445    -> end 931 (dead-tail terminus)

Cost[i][j] = representative earliest cheap tof (min over a few ref
times); BIG if no cheap transfer found at any ref time (keeps cheap
connectivity a hard constraint -> big_jumps stays 0).
"""
import sys, os, json, time
sys.path.insert(0, "src")
from pathlib import Path
import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
PLAN = "/tmp/ch2_e559_assembly_plan.json"
NEWPLAN = "/tmp/ch2_e561_assembly_plan.json"

BIG = 10_000_000          # cost for a TRULY non-cheap (forbidden) edge
PENALTY = 60_000          # 60d-equiv: cheap-reachable but proxy found no tof
SCALE = 1000.0            # tof(days) -> int cost
REF_TIMES = [100.0, 600.0, 1500.0, 2500.0]  # min over these (proxy only)
TOF_WINDOW = 5.0
N_STEPS = 40


def build_cost(kt, nodes, cheap):
    """Cost matrix over `nodes`.
    - BIG  if (i,j) is NOT cheap-reachable (boolean adj False) -> truly
      forbidden; using it would be a real big-jump.
    - tof  (SCALE*days) if cheap-reachable and proxy found a feasible tof.
    - PENALTY if cheap-reachable but the proxy ref-times missed it
      (edge IS cheap at some unsampled time) -> keep connectivity, avoid.
    This keeps cheap-reachability the HARD constraint (big_jumps=0) while
    only the tof drives the ordering."""
    m = len(nodes)
    C = np.full((m, m), BIG, dtype=np.int64)
    t0 = time.time()
    n_pen = 0
    for a in range(m):
        i = nodes[a]
        cand = np.where(cheap[i])[0]
        cand_set = set(int(c) for c in cand)
        for b in range(m):
            if a == b:
                C[a][b] = 0
                continue
            j = nodes[b]
            if j not in cand_set:
                continue  # leave BIG (truly non-cheap)
            best = None
            for tr in REF_TIMES:
                tof, dv = find_earliest_transfer(
                    kt, i, j, tr, kt.dv_thr, TOF_WINDOW, N_STEPS)
                if tof is not None and (best is None or tof < best):
                    best = tof
            if best is not None:
                C[a][b] = int(round(best * SCALE))
            else:
                C[a][b] = PENALTY  # cheap-reachable but proxy missed
                n_pen += 1
        if (a + 1) % 100 == 0:
            print(f"    cost row {a+1}/{m} ({time.time()-t0:.0f}s)",
                  flush=True)
    n_forbid = int((C == BIG).sum())
    print(f"  cost {m}x{m}: forbidden(BIG)={n_forbid} "
          f"({n_forbid/(m*m)*100:.1f}%) penalty_edges={n_pen} "
          f"wall={time.time()-t0:.0f}s", flush=True)
    return C


def solve_open_path(C, start_idx, end_idx, time_limit_s, tag, seed_order=None):
    """Open Hamiltonian path over all nodes from start_idx to end_idx,
    minimising summed cost. Dummy depot links end->depot->start at 0.

    seed_order: optional list of LOCAL node indices giving a known-valid
    cheap-Ham path (start..end). Used as the initial solution so GLS only
    improves tof; guarantees big_jumps=0 is reachable on dense blocks where
    a cold first-solution heuristic cannot find a cheap-Ham path in time."""
    m = C.shape[0]
    depot = m  # virtual
    N = m + 1
    D = np.full((N, N), BIG, dtype=np.int64)
    D[:m, :m] = C
    # depot only connects: depot->start (0) and end->depot (0); all else BIG
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

    t0 = time.time()
    if seed_order is not None:
        # Seed depot path: depot -> start ... end -> depot. Route nodes
        # exclude depot (it is the implicit single vehicle start/end).
        routing.CloseModelWithParameters(p)
        init = routing.ReadAssignmentFromRoutes([list(seed_order)], True)
        if init is None:
            print(f"  [{tag}] WARN seed rejected, cold start", flush=True)
            sol = routing.SolveWithParameters(p)
        else:
            sol = routing.SolveFromAssignmentWithParameters(init, p)
    else:
        sol = routing.SolveWithParameters(p)
    if sol is None:
        print(f"  [{tag}] NO SOLUTION", flush=True)
        return None, None
    # extract order (skip depot)
    order, idx_ = [], routing.Start(0)
    cost_sum = 0
    prev = None
    while not routing.IsEnd(idx_):
        node = mgr.IndexToNode(idx_)
        if node != depot:
            order.append(node)
        nxt = sol.Value(routing.NextVar(idx_))
        idx_ = nxt
    # compute path cost over real edges (consecutive in order)
    big_jumps = 0
    pen_edges = 0
    for k in range(1, len(order)):
        c = C[order[k-1]][order[k]]
        if c >= BIG:
            big_jumps += 1
        elif c >= PENALTY:
            pen_edges += 1
        else:
            cost_sum += c
    obj = sol.ObjectiveValue()
    print(f"  [{tag}] solved {time.time()-t0:.0f}s obj={obj} "
          f"path_cost~{cost_sum/SCALE:.1f}d big_jumps={big_jumps} "
          f"penalty_edges_used={pen_edges} "
          f"len={len(order)} start={order[0]} end={order[-1]}", flush=True)
    return order, big_jumps


def main():
    kt = KTTSP(INST)
    d = np.load(ADJ)
    cheap, labels = d["cheap"], d["labels"]
    plan = json.load(open(PLAN))
    g = plan["g_order"]
    s1, s2 = plan["s1"], plan["s2"]
    oa, ob, oc = plan["order_a"], plan["order_b"], plan["order_c"]

    # Fixed bridge endpoint nodes from the proven plan
    G_HEAD, G_S1m1, G_S1, G_S2m1, G_S2, G_TAIL = (
        g[0], g[s1-1], g[s1], g[s2-1], g[s2], g[-1])
    OA_TAIL = oa[-1]
    OB_HEAD, OB_TAIL = ob[0], ob[-1]
    OC_HEAD, OC_TAIL = oc[0], oc[-1]

    # Node sets per segment (same membership as the working plan)
    segA_nodes = g[0:s1]
    segB_nodes = g[s1:s2]
    segC_nodes = g[s2:]
    oa_nodes, ob_nodes, oc_nodes = list(oa), list(ob), list(oc)

    subproblems = [
        ("oa",   oa_nodes,   None,    OA_TAIL),     # free start, tail 51
        ("segA", segA_nodes, G_HEAD,  G_S1m1),
        ("ob",   ob_nodes,   OB_HEAD, OB_TAIL),
        ("segB", segB_nodes, G_S1,    G_S2m1),
        ("oc",   oc_nodes,   OC_HEAD, OC_TAIL),
        ("segC", segC_nodes, G_S2,    G_TAIL),
    ]

    new = {}
    for tag, nodes, start_node, end_node in subproblems:
        print(f"[{tag}] n={len(nodes)} start={start_node} end={end_node}",
              flush=True)
        cpath = f"/tmp/ch2_e561_cost_{tag}.npy"
        if Path(cpath).exists():
            C = np.load(cpath)
            print(f"  [{tag}] loaded cached cost {C.shape}", flush=True)
        else:
            C = build_cost(kt, nodes, cheap)
            np.save(cpath, C)
        # free-start case: add a virtual no-cost start -> handle by trying
        # the recorded original start? Simpler: if start_node is None, we
        # pick the best start by leaving start free => use AddDisjunction
        # trick. Instead, for oa we fix start to original oa[0] (free leaf
        # is allowed; original is a valid leaf) to keep it simple.
        if start_node is None:
            start_node = nodes[0]  # original free-leaf start (valid)
        si = nodes.index(start_node)
        ei = nodes.index(end_node)
        tl = 480 if len(nodes) > 400 else 240
        # `nodes` is the ORIGINAL valid cheap-Ham ordering (start..end), so
        # identity local-index order is a known-feasible seed when its
        # endpoints match the fixed start/end. Seed every segment with it so
        # GLS only improves tof and never has to discover cheap-Ham cold.
        seed = list(range(len(nodes))) if (si == 0 and ei == len(nodes) - 1) \
            else None
        order_idx, big = solve_open_path(C, si, ei, tl, tag, seed_order=seed)
        if order_idx is None or big > 0:
            print(f"[{tag}] FAIL big_jumps={big} — abort (would break "
                  f"cheap-only constraint).", flush=True)
            return
        new[tag] = [int(nodes[k]) for k in order_idx]

    # Reassemble new plan in the SAME topology
    new_g = new["segA"] + new["segB"] + new["segC"]
    newplan = {
        "a": plan["a"], "b": plan["b"], "c": plan["c"],
        "s1": len(new["segA"]),
        "s2": len(new["segA"]) + len(new["segB"]),
        "order_a": new["oa"], "order_b": new["ob"], "order_c": new["oc"],
        "g_order": new_g, "big": [0, 0, 0],
    }
    Path(NEWPLAN).write_text(json.dumps(newplan))
    print(f"[ASM] wrote new plan -> {NEWPLAN} "
          f"s1={newplan['s1']} s2={newplan['s2']}", flush=True)

    # Build full perm & guarded-bank (reuse assembler walk)
    s1n, s2n = newplan["s1"], newplan["s2"]
    full = (new["oa"] + new_g[0:s1n] + new["ob"] + new_g[s1n:s2n]
            + new["oc"] + new_g[s2n:])
    assert len(full) == kt.n and len(set(full)) == kt.n, "bad perm"

    print("[BANK] walking assembled perm...", flush=True)
    t0 = time.time()
    times, tofs, dvs, ok, exc_n, last_leg = walk_perm_chrono(
        kt, full, tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)
    print(f"[BANK] walk {time.time()-t0:.0f}s ok={ok} exc={exc_n}/{kt.n_exc} "
          f"last_leg={last_leg}", flush=True)
    if not ok:
        print(f"[BANK] WALK FAILED at leg {last_leg} "
              f"({full[last_leg]}->{full[last_leg+1]}) — banking NOTHING.",
              flush=True)
        return
    x = list(times) + list(tofs) + [float(p) for p in full]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    tof_arr = np.array(tofs)
    print(f"[BANK] mk={mk:.4f}d feas={feas} viols={list(fit[1:])} "
          f"exc={exc_n}", flush=True)
    print(f"[BANK] tof: sum={tof_arr.sum():.1f} median={np.median(tof_arr):.3f}"
          f" max={tof_arr.max():.2f} >3d={int((tof_arr>3).sum())} "
          f">5d={int((tof_arr>5).sum())} sum>3d={tof_arr[tof_arr>3].sum():.1f}",
          flush=True)
    if not feas:
        print("[BANK] infeasible — not banking.", flush=True)
        return
    if mk >= 2225.1581:
        print(f"[BANK] mk {mk:.4f} not below 2225.1581 — not banking.",
              flush=True)
        return
    bak = OUT + ".bak.e561"
    if Path(OUT).exists() and not Path(bak).exists():
        Path(bak).write_bytes(Path(OUT).read_bytes())
        print(f"[BANK] backed up -> {bak}", flush=True)
    tmp = OUT + ".tmp"
    Path(tmp).write_text(json.dumps([{
        "decisionVector": x, "problem": "large", "challenge": CHALLENGE}]))
    os.replace(tmp, OUT)
    print(f">>> BANKED large mk={mk:.4f}d exc={exc_n} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
