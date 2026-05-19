"""Ch2 KTTSP — cluster-decomposition solver (E-016 reframe).

The ≤100 m/s graph of `small` splits into 4 connected components
([40,3,3,3]). A feasible tour = a Hamiltonian path WITHIN each
cluster on its cheap edges, stitched by ≤5 inter-cluster bridge
("exception") legs. Per-cluster Ham-path is small & sparse →
CP-SAT solves it exactly (where E-015's full-graph CP-SAT could
not). Then order the clusters, pick bridges, full-horizon re-time,
validate on the official-mirror scorer, bank. Generalises to
medium/large (same structure, O-006).
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from ortools.sat.python import cp_model
from scipy.sparse.csgraph import connected_components

import esa_spoc_26.ch2_lns as L
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def cluster_path(DV, nodes, thr, max_s=20.0):
    """Exact CP-SAT Hamiltonian path over `nodes` using only edges with
    DV ≤ thr. Returns an ordered list of global node ids, or None."""
    if len(nodes) == 1:
        return list(nodes)
    idx = {g: k for k, g in enumerate(nodes)}
    m = cp_model.CpModel()
    depot = len(nodes)
    arcs, lits = [], {}
    for k in range(len(nodes)):
        arcs.append((depot, k, m.NewBoolVar(f"s{k}")))
        arcs.append((k, depot, m.NewBoolVar(f"e{k}")))
    for a in nodes:
        for b in nodes:
            if a != b and DV[a, b] <= thr:
                v = m.NewBoolVar(f"x{a}_{b}")
                arcs.append((idx[a], idx[b], v))
                lits[(idx[a], idx[b])] = v
    m.AddCircuit(arcs)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = float(max_s)
    s.parameters.num_workers = 8
    if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    nxt = {i: j for (i, j), v in lits.items() if s.Value(v)}
    start = next(h for t, h, c in arcs if t == depot and s.Value(c))
    seq = [start]
    while len(seq) < len(nodes) and seq[-1] in nxt:
        seq.append(nxt[seq[-1]])
    if len(seq) != len(nodes):
        return None
    return [nodes[k] for k in seq]


def solve_cluster(inst, problem="small",
                  npz="/home/julian/Projects/esa_spoc_26_3/edges_small.npz",
                  out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    L._KT = kt = KTTSP(inst)
    DV = np.load(npz)["dv"]
    n = kt.n

    A = ((DV <= 100) | (DV.T <= 100)).astype(int)
    np.fill_diagonal(A, 0)
    ncomp, lab = connected_components(sp.csr_matrix(A), directed=False)
    clusters = [np.where(lab == c)[0].tolist() for c in range(ncomp)]

    # intra-cluster Hamiltonian path: ≤100 first, relax to ≤600 if needed
    paths = []
    for cl in clusters:
        p = cluster_path(DV, cl, 100.0) or cluster_path(DV, cl, 600.0)
        if p is None:
            return {"problem": problem, "feasible": False,
                    "note": f"no intra-cluster path (cluster size {len(cl)})"}
        paths.append(p)

    # order clusters + per-path direction; bridges must be ≤600;
    # total exception legs (intra + bridges, 100<Δv≤600) ≤ n_exc
    best = None
    for perm in itertools.permutations(range(ncomp)):
        for dirs in itertools.product([0, 1], repeat=ncomp):
            seq = []
            for ci, d in zip(perm, dirs, strict=True):
                pth = paths[ci][::-1] if d else paths[ci]
                seq.extend(pth)
            ok, exc, cost = True, 0, 0.0
            for k in range(len(seq) - 1):
                dv = DV[seq[k], seq[k + 1]]
                if dv > 600.0 + 1e-6:
                    ok = False
                    break
                if dv > 100.0:
                    exc += 1
                cost += dv
            if ok and exc <= kt.n_exc and (best is None or cost < best[0]):
                best = (cost, seq, exc)
    if best is None:
        return {"problem": problem, "feasible": False,
                "note": "no ≤600 cluster stitching within exception budget"}

    order = best[1]
    x, feas, mk, n_exc, n_bad = L.decode(order)
    res = {"problem": problem, "n": n, "clusters": [len(c) for c in clusters],
           "static_exc": best[2], "makespan_d": round(mk, 3),
           "n_exc": n_exc, "n_bad": n_bad, "feasible": feas,
           "rank3_small_d": 111.76}
    if feas:
        f = kt.fitness(x)
        if kt.is_feasible(f):
            p = Path(out) / f"{problem}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps([{"decisionVector": x,
                                      "problem": problem,
                                      "challenge": CHALLENGE}]))
            res["artifact"] = str(p)
            res["official_makespan_d"] = round(f[0], 3)
        else:
            res["feasible"] = False
            res["note"] = f"decode-feasible but official rejects: {f}"
    return res


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    print(json.dumps(solve_cluster(inst), indent=2))
