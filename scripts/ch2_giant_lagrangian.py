"""E-717 — Ch2-large rank-1: OUR OWN solver. Lagrangian relaxation of the time-expanded GTSP on the DAG.

All off-the-shelf solvers failed: Gurobi free (2000-var cap), elkai+Noon-Bean (intractable big-M),
CP-SAT AddCircuit (no feasible tour in 900s), GLKH (blocked). So we build a custom solver that exploits the
one structural gift no generic solver uses: the time-expanded graph is a DAG (edges go forward in epoch).

Formulation: pick a chronological path visiting EXACTLY ONE (city,epoch) node per city, minimizing sum of
edge tofs (= makespan). Relax the 601 "exactly one per city" constraints with multipliers lambda_c. The
relaxed problem adds lambda_{city(v)} to each node and becomes: min-cost path on the DAG with node+edge
costs -> a LINEAR-TIME DP in epoch (topological) order. Subgradient: lambda_c += step*(visits_c - 1) drives
each city to exactly-once. Track the best near-feasible path; greedily repair residual missing cities.
Output the tour -> faithful fine-tof retime. Target <424d (rank-1).
Usage: python ch2_giant_lagrangian.py [iters=400]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
g = np.load(f"{ROOT}/cache/ch2_giant_texp.npz")
NODES = g["nodes"]; SRC0 = g["src"]; DST0 = g["dst"]; COST0 = g["cost"]; nb = int(g["nb"]); giant = g["giant"].tolist()
d2 = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d2["epochs"]; KEYS = d2["keys"]; VALS = d2["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
nidx = {int(n): k for k, n in enumerate(NODES)}
N = len(NODES); NC = len(giant)
node_city = (NODES // nb).astype(np.int64)
node_epoch = (NODES % nb).astype(np.int64)
# remap edges to live-node indices, drop intra-cluster
su = np.array([nidx[int(s)] for s in SRC0]); dv = np.array([nidx[int(d)] for d in DST0])
keep = node_city[su] != node_city[dv]
su, dv, ec = su[keep], dv[keep], COST0[keep].astype(np.float64) / 1000.0   # cost in days
# CSR by source, in topological (epoch) order processing
topo = np.argsort(node_epoch, kind="stable")                 # process nodes earliest-epoch first
order_pos = np.empty(N, np.int64); order_pos[topo] = np.arange(N)
# group edges by source
o = np.argsort(su, kind="stable"); su, dv, ec = su[o], dv[o], ec[o]
estart = np.searchsorted(su, np.arange(N))
estart = np.append(estart, len(su))


def dp_path(nodecost):
    """min-cost path on the DAG with node+edge costs; returns (path nodes list, total cost)."""
    best = nodecost.copy(); back = np.full(N, -1, np.int64)
    for u in topo:                                           # topological order => preds finalized
        bu = best[u]; a, b = estart[u], estart[u + 1]
        if a == b:
            continue
        cand = bu + ec[a:b] + nodecost[dv[a:b]]
        better = cand < best[dv[a:b]]
        if better.any():
            idx = np.where(better)[0]
            for k in idx:
                w = dv[a + k]
                if cand[k] < best[w]:
                    best[w] = cand[k]; back[w] = u
    end = int(np.argmin(best))
    path = []; c = end
    while c != -1:
        path.append(c); c = back[c]
    return path[::-1], float(best[end])


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


def main(iters=400):
    print(f"[E-717] Lagrangian DAG solver: {N} nodes / {NC} cities / {len(su)} arcs", flush=True)
    lam = np.zeros(NC); best_cover = 0; best_path_cities = None; t0 = time.time()
    for it in range(iters):
        nodecost = lam[node_city]
        path, _ = dp_path(nodecost)
        cities = node_city[path]
        visits = np.bincount(cities, minlength=NC)
        cover = int((visits >= 1).sum()); dup = int((visits > 1).sum())
        # track best path by cities covered (with few dups)
        if cover - dup > best_cover:
            best_cover = cover - dup
            # dedup cities preserving first occurrence (chronological)
            seen = set(); od = []
            for c in cities:
                c = int(c)
                if c not in seen:
                    seen.add(c); od.append(c)
            best_path_cities = od
        step = 2.0 / (1.0 + 0.05 * it)                      # diminishing subgradient step
        lam += step * (visits - 1)
        lam = np.maximum(lam, -50.0)                         # bound rewards
        if it % 25 == 0 or it == iters - 1:
            print(f"  it{it}: path {len(path)} nodes, covers {cover}/{NC} cities ({dup} dup); "
                  f"best_cover={best_cover} [{time.time()-t0:.0f}s]", flush=True)
        if cover == NC and dup == 0:
            print(f"[E-717] FEASIBLE all-{NC} path at it{it}!", flush=True)
            best_path_cities = [int(c) for c in cities]
            break
    print(f"[E-717] best path covers {len(best_path_cities)}/{NC} cities; faithful retiming ...", flush=True)
    mk, strand = retime(best_path_cities)
    print(f"[E-717] Lagrangian tour: {len(best_path_cities)}/{NC} cities, realized makespan {mk:.1f}d, "
          f"strands {strand} (rank-1=424.62) [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": best_path_cities, "makespan": mk, "strands": strand},
              open(f"{ROOT}/cache/ch2_giant_lagrangian_tour.json", "w"))
    if len(best_path_cities) >= NC - 2 and strand == 0 and mk < 424:
        print(f"[E-717] *** RANK-1 ({mk:.0f}d) -> stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
    elif len(best_path_cities) > 560:
        print(f"[E-717] covers {len(best_path_cities)}/{NC} (> beam's 540) -> Lagrangian beats construction; "
              f"repair residual + retime; promising for rank-1.", flush=True)
    else:
        print(f"[E-717] covers {len(best_path_cities)}/{NC}; tune step/iters or the relaxation needs a "
              f"makespan (not sum-tof) objective / cover-cut strengthening.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 400)
