"""E-562 — Ch2 LARGE epoch-aware re-ordering.

E-561 banked 2182.0087d but its cost matrix scored each edge (i,j) by
find_earliest_transfer at 4 FIXED ref times — an optimistic, time-
INDEPENDENT proxy. The chronological walk (walk_perm_chrono) reaches
node i at a TRUE epoch t_i that ranges 0..2180d, so the realized cheap
tof at t_i is far longer than the best-of-4-ref-times proxy. OR-Tools
minimised the proxy, not the walk -> heavy tail unchanged.

This script makes the cost matrix EPOCH-AWARE:
  1. Walk the CURRENT banked order -> per-node departure epoch t_i.
  2. Rebuild cost[i][j] = find_earliest_transfer(kt, i, j, t_start=t_i)
     at i's true epoch (BIG if not cheap-reachable; PENALTY if cheap
     but proxy missed at this epoch).
  3. Re-solve the 6 endpoint-pinned open paths (same segB seeding),
     re-assemble, re-walk.
  4. ITERATE: re-extract epochs from the new walk, re-score, re-solve.
     Keep the best feasible walk; guarded-bank only if < 2182.0087.

Topology, split points (267/508), bridge endpoints, big_jumps=0 are
PRESERVED exactly as in E-561.
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
PLAN = "/tmp/ch2_e561_assembly_plan.json"          # the 2182.0087 plan
NEWPLAN = "/tmp/ch2_e562_assembly_plan.json"

BIG = 10_000_000          # truly non-cheap (forbidden) edge
PENALTY = 60_000          # cheap-reachable but proxy missed at this epoch
SCALE = 1000.0            # tof(days) -> int cost
TOF_WINDOW = 40.0         # match the walk's window so epoch-tof aligns
N_STEPS = 200             # finer than walk's 300? keep moderate for speed
CURRENT_BANK = 2182.0087  # do not bank unless strictly below this

# Walk params identical to the banked walk (so epochs reproduce exactly).
WALK = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)


def build_cost_epoch(kt, nodes, cheap, epoch):
    """Epoch-aware cost over `nodes`. epoch[i] = true departure epoch of
    node i (global id). cost[a][b] scores edge (nodes[a]->nodes[b]) at the
    epoch the walk DEPARTS nodes[a]. BIG if not cheap-reachable; PENALTY
    if cheap-reachable but no cheap tof found at this epoch."""
    m = len(nodes)
    C = np.full((m, m), BIG, dtype=np.int64)
    t0 = time.time()
    n_pen = 0
    for a in range(m):
        i = nodes[a]
        t_i = float(epoch[i])
        cand_set = set(int(c) for c in np.where(cheap[i])[0])
        for b in range(m):
            if a == b:
                C[a][b] = 0
                continue
            j = nodes[b]
            if j not in cand_set:
                continue  # leave BIG (truly non-cheap)
            tof, dv = find_earliest_transfer(
                kt, i, j, t_i, kt.dv_thr, TOF_WINDOW, N_STEPS)
            if tof is not None:
                C[a][b] = int(round(tof * SCALE))
            else:
                C[a][b] = PENALTY
                n_pen += 1
        if (a + 1) % 100 == 0:
            print(f"    cost row {a+1}/{m} ({time.time()-t0:.0f}s)", flush=True)
    n_forbid = int((C == BIG).sum())
    print(f"  cost {m}x{m}: forbidden(BIG)={n_forbid} "
          f"({n_forbid/(m*m)*100:.1f}%) penalty_edges={n_pen} "
          f"wall={time.time()-t0:.0f}s", flush=True)
    return C


def solve_open_path(C, start_idx, end_idx, time_limit_s, tag, seed_order=None):
    """Open Hamiltonian path start->end over all nodes minimising summed
    cost. Dummy depot links end->depot->start at 0."""
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

    t0 = time.time()
    if seed_order is not None:
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
    order, idx_ = [], routing.Start(0)
    while not routing.IsEnd(idx_):
        node = mgr.IndexToNode(idx_)
        if node != depot:
            order.append(node)
        idx_ = sol.Value(routing.NextVar(idx_))
    big_jumps = pen_edges = 0
    cost_sum = 0
    for k in range(1, len(order)):
        c = C[order[k-1]][order[k]]
        if c >= BIG:
            big_jumps += 1
        elif c >= PENALTY:
            pen_edges += 1
        else:
            cost_sum += c
    print(f"  [{tag}] solved {time.time()-t0:.0f}s obj={sol.ObjectiveValue()} "
          f"path_cost~{cost_sum/SCALE:.1f}d big_jumps={big_jumps} "
          f"penalty_edges_used={pen_edges} "
          f"len={len(order)} start={order[0]} end={order[-1]}", flush=True)
    return order, big_jumps


def assemble_full(plan):
    s1, s2 = plan["s1"], plan["s2"]
    g = plan["g_order"]
    return (plan["order_a"] + g[0:s1] + plan["order_b"] + g[s1:s2]
            + plan["order_c"] + g[s2:])


def walk_stats(kt, full):
    times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, full, **WALK)
    if not ok:
        return None
    x = list(times) + list(tofs) + [float(p) for p in full]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    return dict(times=times, tofs=tofs, x=x, fit=fit, feas=feas, mk=mk,
                exc=exc, ok=ok)


def epoch_from_walk(full, times):
    """Map global node id -> departure epoch from the walk. times[k] is the
    departure epoch of node full[k]. The terminus has no departure; give it
    the last arrival epoch (it has no outgoing edge that matters)."""
    ep = {}
    for k in range(len(times)):
        ep[full[k]] = times[k]
    # terminus
    ep[full[-1]] = times[-1] + 0.0
    return ep


def main():
    kt = KTTSP(INST)
    d = np.load(ADJ)
    cheap = d["cheap"]
    plan = json.load(open(PLAN))

    subdefs = [
        ("oa",   "order_a", None),
        ("segA", "segA",    None),
        ("ob",   "order_b", None),
        ("segB", "segB",    None),
        ("oc",   "order_c", None),
        ("segC", "segC",    None),
    ]

    def seg_nodes(pl):
        g = pl["g_order"]
        return {"segA": g[0:pl["s1"]], "segB": g[pl["s1"]:pl["s2"]],
                "segC": g[pl["s2"]:], "order_a": pl["order_a"],
                "order_b": pl["order_b"], "order_c": pl["order_c"]}

    # Baseline walk of current plan to confirm reproduction.
    full0 = assemble_full(plan)
    w0 = walk_stats(kt, full0)
    print(f"[BASE] mk={w0['mk']:.4f} feas={w0['feas']} exc={w0['exc']} "
          f"viols={list(w0['fit'][1:])}", flush=True)

    best_mk = w0["mk"]
    best_x = w0["x"]
    best_plan = plan
    best_full = full0

    cur_plan = plan
    cur_walk = w0

    N_ITERS = 3
    for it in range(N_ITERS):
        print(f"\n========== EPOCH-AWARE ITERATION {it} ==========",
              flush=True)
        full = assemble_full(cur_plan)
        epoch = epoch_from_walk(full, cur_walk["times"])
        sn = seg_nodes(cur_plan)
        # fixed bridge endpoints from CURRENT plan
        g = cur_plan["g_order"]
        s1, s2 = cur_plan["s1"], cur_plan["s2"]
        endpoints = {
            "oa":   (None,    cur_plan["order_a"][-1]),
            "segA": (g[0],    g[s1-1]),
            "ob":   (cur_plan["order_b"][0], cur_plan["order_b"][-1]),
            "segB": (g[s1],   g[s2-1]),
            "oc":   (cur_plan["order_c"][0], cur_plan["order_c"][-1]),
            "segC": (g[s2],   g[-1]),
        }

        new = {}
        ok_iter = True
        for tag, key, _ in subdefs:
            nodes = list(sn[key])
            start_node, end_node = endpoints[tag]
            if start_node is None:
                start_node = nodes[0]
            print(f"[{tag}] n={len(nodes)} start={start_node} "
                  f"end={end_node}", flush=True)
            C = build_cost_epoch(kt, nodes, cheap, epoch)
            si = nodes.index(start_node)
            ei = nodes.index(end_node)
            tl = 480 if len(nodes) > 400 else 240
            seed = list(range(len(nodes))) if (
                si == 0 and ei == len(nodes) - 1) else None
            order_idx, big = solve_open_path(C, si, ei, tl, tag,
                                             seed_order=seed)
            if order_idx is None or big > 0:
                print(f"[{tag}] FAIL big_jumps={big} — reseeding with "
                      f"identity order (valid cheap-Ham).", flush=True)
                # fall back to current valid ordering for this seg
                if si == 0 and ei == len(nodes) - 1:
                    order_idx = list(range(len(nodes)))
                    big = 0
                else:
                    ok_iter = False
                    break
            new[tag] = [int(nodes[k]) for k in order_idx]

        if not ok_iter:
            print(f"[iter {it}] aborted (a non-seeded segment got "
                  f"big_jumps>0).", flush=True)
            break

        new_g = new["segA"] + new["segB"] + new["segC"]
        newplan = {
            "a": cur_plan["a"], "b": cur_plan["b"], "c": cur_plan["c"],
            "s1": len(new["segA"]),
            "s2": len(new["segA"]) + len(new["segB"]),
            "order_a": new["oa"], "order_b": new["ob"], "order_c": new["oc"],
            "g_order": new_g, "big": [0, 0, 0],
        }
        full = assemble_full(newplan)
        assert len(full) == kt.n and len(set(full)) == kt.n, "bad perm"

        w = walk_stats(kt, full)
        if w is None:
            print(f"[iter {it}] WALK FAILED — keeping previous best, stop.",
                  flush=True)
            break
        tof_arr = np.array(w["tofs"])
        print(f"[iter {it}] mk={w['mk']:.4f} feas={w['feas']} exc={w['exc']} "
              f"viols={list(w['fit'][1:])}", flush=True)
        print(f"[iter {it}] tof: sum={tof_arr.sum():.1f} "
              f"max={tof_arr.max():.2f} >3d={int((tof_arr>3).sum())} "
              f">5d={int((tof_arr>5).sum())} "
              f"sum>3d={tof_arr[tof_arr>3].sum():.1f}", flush=True)

        if w["feas"] and w["mk"] < best_mk:
            best_mk = w["mk"]
            best_x = w["x"]
            best_plan = newplan
            best_full = full
            print(f"[iter {it}] NEW BEST mk={best_mk:.4f}", flush=True)

        # iterate from this new walk (even if not better, epochs shifted)
        cur_plan = newplan
        cur_walk = w
        # divergence guard: if mk grew a lot above current bank, stop
        if w["mk"] > CURRENT_BANK * 1.10:
            print(f"[iter {it}] mk diverging ({w['mk']:.1f}) — stop.",
                  flush=True)
            break

    print(f"\n[FINAL] best_mk={best_mk:.4f} (current bank {CURRENT_BANK})",
          flush=True)

    # Guarded bank
    if best_mk >= CURRENT_BANK:
        print("[BANK] did NOT beat current bank — banking NOTHING, "
              "large.json untouched.", flush=True)
        return

    # independent re-validate
    fit = kt.fitness(best_x)
    feas = bool(kt.is_feasible(fit))
    perm = [int(round(v)) for v in best_x[2100:3151]]
    covered = len(set(perm)) == kt.n and len(perm) == kt.n
    mk = float(fit[0])
    viols = list(fit[1:])
    print(f"[REVAL] mk={mk:.4f} feas={feas} viols={viols} "
          f"covered={covered}", flush=True)
    if not (feas and mk < CURRENT_BANK and covered and all(v == 0
            for v in viols)):
        print("[BANK] re-validation failed — banking NOTHING.", flush=True)
        return

    Path(NEWPLAN).write_text(json.dumps(best_plan))
    bak = OUT + ".bak.e562"
    if Path(OUT).exists() and not Path(bak).exists():
        Path(bak).write_bytes(Path(OUT).read_bytes())
        print(f"[BANK] backed up -> {bak}", flush=True)
    tmp = OUT + ".tmp"
    Path(tmp).write_text(json.dumps([{
        "decisionVector": best_x, "problem": "large", "challenge": CHALLENGE}]))
    os.replace(tmp, OUT)
    print(f">>> BANKED large mk={mk:.4f}d -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
