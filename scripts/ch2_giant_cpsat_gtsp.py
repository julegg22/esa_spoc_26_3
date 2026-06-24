"""E-716 — Ch2-large rank-1: time-expanded GTSP via OR-Tools CP-SAT AddCircuit (in-repo; no GLKH download).

The time-expanded graph is a DAG (edges forward in epoch) so no subtours are possible -> the hard part of a
GTSP is free. CP-SAT models it directly: node (city,epoch) with a SKIP self-loop; exactly one node un-skipped
per city-cluster; a dummy depot D makes the open path a circuit; AddCircuit enforces a single covering path;
minimize sum of arc tofs (= makespan for a chronological tour). CP-SAT is multi-core, no license cap (unlike
restricted Gurobi), and AddCircuit's propagator handles connectivity natively (where Noon-Bean+elkai choked).
Decode -> city order -> FAITHFUL fine-tof retime. Target <424d (rank-1).
Usage: python ch2_giant_cpsat_gtsp.py [time_limit_s=900]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
from ortools.sat.python import cp_model
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
g = np.load(f"{ROOT}/cache/ch2_giant_texp.npz")
NODES = g["nodes"]; SRC = g["src"]; DST = g["dst"]; COST = g["cost"]; nb = int(g["nb"]); giant = g["giant"].tolist()
d2 = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d2["epochs"]; KEYS = d2["keys"]; VALS = d2["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
nidx = {int(n): k for k, n in enumerate(NODES)}
N = len(NODES)
node_city = np.array([int(n) // nb for n in NODES])
clusters = defaultdict(list)
for k in range(N):
    clusters[int(node_city[k])].append(k)


def fine_tof(i, j, t):
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def retime(order):
    t = 0.0; strand = 0
    for k in range(len(order) - 1):
        r = fine_tof(giant[order[k]], giant[order[k + 1]], t)
        if r is None:
            strand += 1; t += 9.0
        else:
            t = r
    return t, strand


def main(tl=900):
    m = cp_model.CpModel()
    D = N                                                          # dummy depot index
    skip = {v: m.NewBoolVar(f"s{v}") for v in range(N)}           # SKIP self-loop literal per node
    arcs = [(v, v, skip[v]) for v in range(N)]
    edge_arcs = []                                                # (literal, cost) for real inter-cluster arcs
    for s, dd, c in zip(SRC, DST, COST):
        su, dv = nidx.get(int(s)), nidx.get(int(dd))
        if su is None or dv is None or node_city[su] == node_city[dv]:
            continue
        lit = m.NewBoolVar("")
        arcs.append((su, dv, lit)); edge_arcs.append((lit, int(c)))
    for v in range(N):                                            # dummy depot in/out (open path), cost 0
        arcs.append((D, v, m.NewBoolVar("")))
        arcs.append((v, D, m.NewBoolVar("")))
    m.AddCircuit(arcs)
    for c, nodes in clusters.items():                            # exactly one node visited per city
        m.Add(sum(skip[v] for v in nodes) == len(nodes) - 1)
    m.Minimize(sum(lit * c for lit, c in edge_arcs))
    print(f"[E-716] CP-SAT GTSP: {N} nodes / {len(clusters)} clusters / {len(edge_arcs)} arcs; solving (tl={tl}s, multi-core)", flush=True)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = tl
    solver.parameters.num_search_workers = 4
    solver.parameters.log_search_progress = False
    t0 = time.time()
    st = solver.Solve(m)
    print(f"[E-716] status={solver.StatusName(st)} obj={solver.ObjectiveValue() if st in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 'n/a'} "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("[E-716] no feasible GTSP tour found in budget.", flush=True)
        return
    # decode: follow the circuit from D
    nxt = {}
    for (u, v, lit) in arcs:
        if u != v and solver.Value(lit):
            nxt[u] = v
    order = []; cur = nxt.get(D)
    seen = set()
    while cur is not None and cur != D and cur not in seen:
        seen.add(cur)
        if cur < N:
            order.append(int(node_city[cur]))
        cur = nxt.get(cur)
    # dedup cities preserving order
    od = []; sc = set()
    for c in order:
        if c not in sc:
            sc.add(c); od.append(c)
    print(f"[E-716] decoded {len(od)}/{len(clusters)} cities; faithful retiming ...", flush=True)
    mk, strand = retime(od)
    print(f"[E-716] CP-SAT GTSP tour: realized makespan {mk:.1f}d, strands {strand}/{len(od)} (rank-1=424.62) [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": od, "makespan": mk, "strands": strand}, open(f"{ROOT}/cache/ch2_giant_cpsat_tour.json", "w"))
    if strand == 0 and mk < 424:
        print(f"[E-716] *** RANK-1 ({mk:.0f}d) -> stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
    elif len(od) >= len(clusters) - 2:
        print(f"[E-716] complete tour @ {mk:.0f}d ({strand} strands) -> {'refine' if mk>=424 else 'rank-1!'}; "
              f"if strands>0 repair + retime.", flush=True)
    else:
        print(f"[E-716] partial decode ({len(od)}); inspect circuit/cluster constraints.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 900)
