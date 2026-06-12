"""E-562b — Ch2 LARGE epoch-aware re-ordering, continued.

Continues E-562 (banked 1536.3953d over 3 batch epoch-aware iterations,
2182->1957->1732->1536). Adds the predecessor's named next levers:

  Lever 1: MORE epoch-aware iterations (cheap, proven). Run up to N_ITERS
           rounds, keeping the best feasible walk. Stop when an iteration
           improves <STOP_DELTA d.

  Lever 2 (key): SEQUENTIAL per-piece re-solve. Instead of scoring all 6
           pieces from one stale walk's epochs, re-walk after each piece
           is re-solved so DOWNSTREAM pieces see FRESH (earlier) epochs.
           Improving the head shifts all downstream epochs earlier, which
           invalidates tail costs under the batch approach; sequential
           re-solve fixes that lag.

Topology / 5-bridge "comp0-last" / split points (267/508) / fixed bridge
endpoints / big_jumps=0 / exc=5 are PRESERVED exactly as in E-562.

GUARDED BANK: overwrite large.json only if feasible AND mk<1536.3953 AND
1051 nodes AND viols all 0. Backup -> large.json.bak.e562b (created only
if absent). Independent re-validate after writing.
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
PLAN = "/tmp/ch2_e562_assembly_plan.json"          # the 1536.3953 plan
NEWPLAN = "/tmp/ch2_e562b_assembly_plan.json"

BIG = 10_000_000          # truly non-cheap (forbidden) edge
PENALTY = 60_000          # cheap-reachable but proxy missed at this epoch
SCALE = 1000.0            # tof(days) -> int cost
TOF_WINDOW = 40.0
N_STEPS = 200
CURRENT_BANK = 1536.3953  # do not bank unless strictly below this

N_ITERS = 6
STOP_DELTA = 10.0         # stop iterating when improvement < this (days)

# Walk params identical to the banked walk (so epochs reproduce exactly).
WALK = dict(tof_window=40.0, n_steps=300, wait_steps=8, wait_dt=1.0)

# The 6 pieces in CHRONOLOGICAL assembly order:
#   order_a, segA, order_b, segB, order_c, segC
PIECE_ORDER = ["oa", "segA", "ob", "segB", "oc", "segC"]
KEY_OF = {"oa": "order_a", "ob": "order_b", "oc": "order_c",
          "segA": "segA", "segB": "segB", "segC": "segC"}


def build_cost_epoch(kt, nodes, cheap, epoch):
    """Epoch-aware cost over `nodes`. epoch[i] = true departure epoch of
    node i (global id)."""
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
                continue
            tof, dv = find_earliest_transfer(
                kt, i, j, t_i, kt.dv_thr, TOF_WINDOW, N_STEPS)
            if tof is not None:
                C[a][b] = int(round(tof * SCALE))
            else:
                C[a][b] = PENALTY
                n_pen += 1
    n_forbid = int((C == BIG).sum())
    print(f"  cost {m}x{m}: forbidden={n_forbid} "
          f"({n_forbid/(m*m)*100:.1f}%) pen_edges={n_pen} "
          f"wall={time.time()-t0:.0f}s", flush=True)
    return C


def solve_open_path(C, start_idx, end_idx, time_limit_s, tag, seed_order=None):
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
          f"path~{cost_sum/SCALE:.1f}d big_jumps={big_jumps} "
          f"pen_used={pen_edges} len={len(order)} "
          f"start={order[0]} end={order[-1]}", flush=True)
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
    """global node id -> departure epoch from the walk."""
    ep = {}
    for k in range(len(times)):
        ep[full[k]] = times[k]
    ep[full[-1]] = times[-1]
    return ep


def plan_pieces(plan):
    """Return dict tag -> node list, in current plan."""
    g = plan["g_order"]
    s1, s2 = plan["s1"], plan["s2"]
    return {
        "oa": list(plan["order_a"]),
        "segA": list(g[0:s1]),
        "ob": list(plan["order_b"]),
        "segB": list(g[s1:s2]),
        "oc": list(plan["order_c"]),
        "segC": list(g[s2:]),
    }


def endpoints_of(plan):
    """Fixed (start,end) bridge endpoints per piece. PRESERVED exactly.
    oa start is free (it is the global origin); everything else pinned."""
    g = plan["g_order"]
    s1, s2 = plan["s1"], plan["s2"]
    return {
        "oa":   (None,                  plan["order_a"][-1]),
        "segA": (g[0],                  g[s1-1]),
        "ob":   (plan["order_b"][0],    plan["order_b"][-1]),
        "segB": (g[s1],                 g[s2-1]),
        "oc":   (plan["order_c"][0],    plan["order_c"][-1]),
        "segC": (g[s2],                 g[-1]),
    }


def assemble_from_pieces(plan, pieces):
    """Rebuild a plan dict from re-ordered pieces (keeps endpoints/splits)."""
    new_g = pieces["segA"] + pieces["segB"] + pieces["segC"]
    return {
        "a": plan["a"], "b": plan["b"], "c": plan["c"],
        "s1": len(pieces["segA"]),
        "s2": len(pieces["segA"]) + len(pieces["segB"]),
        "order_a": pieces["oa"], "order_b": pieces["ob"],
        "order_c": pieces["oc"], "g_order": new_g, "big": [0, 0, 0],
    }


def resolve_piece(kt, cheap, tag, nodes, start_node, end_node, epoch):
    """Build epoch-aware cost & re-solve one piece. Returns reordered node
    list (preserving start/end), or None on irrecoverable failure."""
    if start_node is None:
        start_node = nodes[0]
    C = build_cost_epoch(kt, nodes, cheap, epoch)
    si = nodes.index(start_node)
    ei = nodes.index(end_node)
    tl = 480 if len(nodes) > 400 else 240
    # seed with identity when start/end are already first/last (valid Ham)
    seed = list(range(len(nodes))) if (
        si == 0 and ei == len(nodes) - 1) else None
    order_idx, big = solve_open_path(C, si, ei, tl, tag, seed_order=seed)
    if order_idx is None or big > 0:
        print(f"  [{tag}] big_jumps={big} — keep identity (valid order).",
              flush=True)
        if si == 0 and ei == len(nodes) - 1:
            order_idx = list(range(len(nodes)))
        else:
            return None
    return [int(nodes[k]) for k in order_idx]


def main():
    kt = KTTSP(INST)
    d = np.load(ADJ)
    cheap = d["cheap"]
    plan = json.load(open(PLAN))

    full0 = assemble_full(plan)
    w0 = walk_stats(kt, full0)
    tof0 = np.array(w0["tofs"])
    print(f"[BASE] mk={w0['mk']:.4f} feas={w0['feas']} exc={w0['exc']} "
          f"viols={list(w0['fit'][1:])}", flush=True)
    print(f"[BASE] tof sum={tof0.sum():.1f} max={tof0.max():.2f} "
          f">3d={int((tof0>3).sum())} sum>3d={tof0[tof0>3].sum():.1f}",
          flush=True)

    best_mk = w0["mk"]
    best_x = w0["x"]
    best_plan = plan
    cur_plan = plan

    prev_iter_mk = w0["mk"]

    for it in range(N_ITERS):
        print(f"\n========== SEQUENTIAL EPOCH-AWARE ITER {it} ==========",
              flush=True)
        # Endpoints are fixed from current plan (preserved each iter).
        endpoints = endpoints_of(cur_plan)
        # Working pieces (mutated as we re-solve, head-to-tail).
        pieces = plan_pieces(cur_plan)

        # Fresh epochs from a walk of the CURRENT assembly.
        full = assemble_full(assemble_from_pieces(cur_plan, pieces))
        w_cur = walk_stats(kt, full)
        epoch = epoch_from_walk(full, w_cur["times"])

        seq_failed = False
        for tag in PIECE_ORDER:
            nodes = pieces[tag]
            sn, en = endpoints[tag]
            print(f"[{tag}] n={len(nodes)} start={sn} end={en}", flush=True)
            new_nodes = resolve_piece(kt, cheap, tag, nodes, sn, en, epoch)
            if new_nodes is None:
                print(f"[{tag}] irrecoverable — abort iter (keep prev).",
                      flush=True)
                seq_failed = True
                break
            pieces[tag] = new_nodes
            # SEQUENTIAL: re-walk so downstream pieces see fresh epochs.
            full = assemble_full(assemble_from_pieces(cur_plan, pieces))
            w_seq = walk_stats(kt, full)
            if w_seq is None:
                print(f"[{tag}] re-walk failed — abort iter.", flush=True)
                seq_failed = True
                break
            epoch = epoch_from_walk(full, w_seq["times"])
            print(f"  [{tag}] after re-solve mk={w_seq['mk']:.4f} "
                  f"feas={w_seq['feas']}", flush=True)

        if seq_failed:
            break

        newplan = assemble_from_pieces(cur_plan, pieces)
        full = assemble_full(newplan)
        assert len(full) == kt.n and len(set(full)) == kt.n, "bad perm"

        w = walk_stats(kt, full)
        if w is None:
            print(f"[iter {it}] WALK FAILED — stop.", flush=True)
            break
        tof = np.array(w["tofs"])
        print(f"[iter {it}] mk={w['mk']:.4f} feas={w['feas']} exc={w['exc']} "
              f"viols={list(w['fit'][1:])}", flush=True)
        print(f"[iter {it}] tof sum={tof.sum():.1f} max={tof.max():.2f} "
              f">3d={int((tof>3).sum())} >5d={int((tof>5).sum())} "
              f"sum>3d={tof[tof>3].sum():.1f}", flush=True)

        if w["feas"] and w["mk"] < best_mk:
            best_mk = w["mk"]
            best_x = w["x"]
            best_plan = newplan
            print(f"[iter {it}] NEW BEST mk={best_mk:.4f}", flush=True)

        improve = prev_iter_mk - w["mk"]
        print(f"[iter {it}] improvement vs prev iter = {improve:.2f}d",
              flush=True)
        cur_plan = newplan
        prev_iter_mk = w["mk"]

        if w["feas"] and improve < STOP_DELTA and improve >= 0:
            print(f"[iter {it}] improvement < {STOP_DELTA}d — stop "
                  f"iterating (diminishing returns).", flush=True)
            break
        if w["mk"] > CURRENT_BANK * 1.15:
            print(f"[iter {it}] mk diverging ({w['mk']:.1f}) — stop.",
                  flush=True)
            break

    print(f"\n[FINAL] best_mk={best_mk:.4f} (current bank {CURRENT_BANK})",
          flush=True)

    if best_mk >= CURRENT_BANK:
        print("[BANK] did NOT beat current bank — banking NOTHING.",
              flush=True)
        return

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
    bak = OUT + ".bak.e562b"
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
