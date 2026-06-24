"""E-715 stage 2 — Ch2-large rank-1: Noon-Bean GTSP->ATSP transform + LKH solve + faithful verify.

Input: cache/ch2_giant_texp.npz (time-expanded graph, 5703 nodes / 601 city-clusters / 370k edges).
Noon-Bean: zero-cost intra-cluster cycle + inter-cluster arcs offset by M and shifted to the cluster
predecessor -> the ATSP optimum visits each cluster's nodes consecutively, selecting one representative
epoch-copy per city. elkai (LKH) solves the ATSP. Decode -> city order + chosen epochs -> FAITHFUL retime
(fine-tof) -> realized makespan. Target <405d (rank-1). Validates Noon-Bean via the retime (garbage decode
-> nonsense makespan).
Usage: python ch2_giant_gtsp_solve.py"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
import elkai
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
g = np.load(f"{ROOT}/cache/ch2_giant_texp.npz")
NODES = g["nodes"]; SRC = g["src"]; DST = g["dst"]; COST = g["cost"]; nb = int(g["nb"]); giant = g["giant"].tolist()
d2 = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d2["epochs"]; KEYS = d2["keys"]; VALS = d2["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}

# remap live nodes 0..N-1; node -> (city, bucket)
nidx = {int(n): k for k, n in enumerate(NODES)}
N = len(NODES)
node_city = np.array([int(n) // nb for n in NODES])               # giant-index
node_buck = np.array([int(n) % nb for n in NODES])
clusters = defaultdict(list)
for k in range(N):
    clusters[node_city[k]].append(k)


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
    t = 0.0; exc = 0; strand = 0
    for k in range(len(order) - 1):
        a, b = giant[order[k]], giant[order[k + 1]]
        r = fine_tof(a, b, t)
        if r is None and exc < kt.n_exc:
            r = fine_tof(a, b, t)
            if r is None:
                pass
        if r is None:
            strand += 1; t += 9.0
        else:
            t = r
    return t, strand


def main():
    print(f"[E-715-2] Noon-Bean on {N} nodes / {len(clusters)} clusters / {len(SRC)} edges", flush=True)
    maxc = int(COST.max())
    M = maxc * (len(clusters) + 5)                                # Noon-Bean offset (> any tour's real cost)
    BIG = M * 50
    D = np.full((N, N), BIG, np.int64)
    # zero-cost intra-cluster directed cycle; record predecessor in cycle
    pred = {}
    for c, nodes in clusters.items():
        m = len(nodes)
        for a in range(m):
            u, v = nodes[a], nodes[(a + 1) % m]
            D[u, v] = 0; pred[v] = u
    # inter-cluster arcs: (pred(src), dst) = cost + M
    t0 = time.time()
    for s, dd, c in zip(SRC, DST, COST):
        su, dv = nidx.get(int(s)), nidx.get(int(dd))
        if su is None or dv is None or node_city[su] == node_city[dv]:
            continue
        a = pred[su]
        val = int(c) + M
        if val < D[a, dv]:
            D[a, dv] = val
    np.fill_diagonal(D, 0)
    print(f"[E-715-2] matrix built [{time.time()-t0:.0f}s]; solving ATSP with LKH ...", flush=True)
    tour = elkai.solve_int_matrix(D.tolist())
    # decode: walk tour, take one representative per cluster (entry node), in order of appearance
    seen = set(); order = []
    for n in tour:
        c = node_city[n]
        if c not in seen:
            seen.add(c); order.append(int(c))
    print(f"[E-715-2] decoded {len(order)}/{len(clusters)} cities; faithful retiming ...", flush=True)
    mk, strand = retime(order)
    print(f"[E-715-2] GTSP tour realized makespan {mk:.1f}d, strands {strand}/{len(order)} (rank-1=424.62) [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order, "makespan": mk, "strands": strand}, open(f"{ROOT}/cache/ch2_giant_gtsp_tour.json", "w"))
    if strand == 0 and mk < 424:
        print(f"[E-715-2] *** RANK-1 ({mk:.0f}d) -> stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
    elif strand <= 3 and mk < 600:
        print(f"[E-715-2] close: {strand} strands @ {mk:.0f}d -> repair strands + retime; promising.", flush=True)
    else:
        print(f"[E-715-2] {strand} strands @ {mk:.0f}d -> Noon-Bean/bucketing imperfect; refine (finer buckets / KEEP / verify transform).", flush=True)


if __name__ == "__main__":
    main()
