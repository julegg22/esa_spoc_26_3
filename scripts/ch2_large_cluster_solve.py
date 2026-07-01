"""E-763 step B — per-cluster sub-solver (proof-of-concept for decompose->solve->couple).

Reuses the faithful full per-edge windows (cache/ch2_giant_faithful_full.npz: {(i,j): (dep_days, tof_days)})
restricted to ONE comp0 sub-cluster (cache/ch2_large_clusters.json) — no fresh prewarm. Intra-cluster is
cheap-dense, so no exceptions are needed inside a cluster: the exact retimer is earliest-cheap-arrival
greedy (optimal when waiting is allowed), wrapped in or-opt LNS over the cluster's node order. Minimizes
the intra-cluster makespan from t=0, then VALIDATES every leg with the official kt.compute_transfer.
Proves the sub-solver is tractable at cluster scale (n<=168) — the whole point vs the intractable 601-giant.
Usage: python ch2_large_cluster_solve.py <cluster_id e.g. c3> [iters=300000] [seed=1]
"""
import sys, json, time
import numpy as np
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
import _prov
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
THR = 100.0


def suffix_min(dep, arr):
    n = len(dep)
    if n == 0:
        return None
    order = np.argsort(dep, kind="stable"); dep = dep[order]; arr = arr[order]
    sidx = np.empty(n, np.int64); sidx[-1] = n - 1
    for q in range(n - 2, -1, -1):
        sidx[q] = q if arr[q] <= arr[sidx[q + 1]] else sidx[q + 1]
    return (dep, arr[sidx], dep[sidx], arr[sidx] - dep[sidx])   # dep, smin_arr, sdep, stof


def main():
    cid = sys.argv[1] if len(sys.argv) > 1 else "c3"
    iters = int(sys.argv[2]) if len(sys.argv) > 2 else 300000
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    _prov.stamp(__file__, cluster=cid, iters=iters)
    kt = KTTSP(INST)
    nodes = json.load(open("cache/ch2_large_clusters.json"))["clusters"][cid]
    S = set(nodes); nc = len(nodes)
    W = np.load("cache/ch2_giant_faithful_full.npz", allow_pickle=True)["windows"].item()
    # build intra-cluster cheap edge windows (suffix-min); count coverage
    EDGE = {}; cov = 0
    for i in nodes:
        for j in nodes:
            if i == j:
                continue
            v = W.get((i, j))
            if v is None or len(v[0]) == 0:
                continue
            dep = np.asarray(v[0], float); tof = np.asarray(v[1], float)
            sm = suffix_min(dep, dep + tof)
            if sm is not None:
                EDGE[(i, j)] = sm; cov += 1
    poss = nc * (nc - 1)
    print(f"[E-763][{cid}] n={nc} intra-edges with windows: {cov}/{poss} "
          f"({100*cov/poss:.0f}% dense) out-deg med="
          f"{int(np.median([sum((i,j) in EDGE for j in nodes) for i in nodes]))}", flush=True)

    def retime(order):
        t = 0.0; times = [0.0] * (nc - 1); tofs = [0.0] * (nc - 1)
        for k in range(nc - 1):
            e = EDGE.get((order[k], order[k + 1]))
            if e is None:
                return float("inf"), None, None
            cd, smin, sdep, stof = e
            q = np.searchsorted(cd, t)
            if q >= len(smin):
                return float("inf"), None, None
            times[k] = float(sdep[q]); tofs[k] = float(stof[q]); t = float(smin[q])
        return t, times, tofs                       # makespan = final arrival from t=0

    rng = np.random.default_rng(seed)
    # multi-start: seed from a few random orders, keep the best that retimes finite
    cur = None
    for _ in range(200):
        o = [nodes[0]] + list(rng.permutation(nodes[1:]))
        mk, ti, tf = retime(o)
        if mk < float("inf") and (cur is None or mk < cur[0]):
            cur = (mk, o)
    if cur is None:
        print(f"[E-763][{cid}] no finite-makespan order from 200 random starts -> cluster not cheap-Hamiltonian in this window set", flush=True)
        return
    cur_mk, cur_o = cur; best = cur_mk
    print(f"[E-763][{cid}] init makespan {cur_mk:.3f}d [{0}s]", flush=True)
    t0 = time.time(); r = seed
    for it in range(iters):
        r = (r * 1103515245 + 12345) & 0x7fffffff
        L = 1 + (r % 3); a = 1 + (r % (nc - L - 1)); seg = cur_o[a:a + L]
        rest = cur_o[:a] + cur_o[a + L:]; b = 1 + ((r >> 8) % (len(rest) - 1))
        cand = rest[:b] + seg + rest[b:]
        mk, ti, tf = retime(cand)
        if mk < cur_mk or (r % 20 == 0 and mk < cur_mk + 0.5):
            cur_o, cur_mk = cand, mk
        if mk < best - 1e-9:
            best = mk; best_o, best_ti, best_tf = cand, ti, tf
        if it % 50000 == 0:
            print(f"[E-763][{cid}] it{it} cur {cur_mk:.3f} best {best:.3f} [{time.time()-t0:.0f}s]", flush=True)
    # VALIDATE the best tour's legs with the official evaluator
    bad = 0; mxdv = 0.0
    for k in range(nc - 1):
        dv = kt.compute_transfer(best_o[k], best_o[k + 1], best_ti[k], best_tf[k])
        mxdv = max(mxdv, dv)
        if dv > THR + 1e-6:
            bad += 1
    json.dump({"cluster": cid, "order": best_o, "times": best_ti, "tofs": best_tf, "makespan": best},
              open(f"cache/ch2_large_clustour_{cid}.json", "w"))
    print(f"[E-763][{cid}] BEST intra-cluster makespan {best:.3f}d over {nc} nodes; "
          f"official validate: {nc-1-bad}/{nc-1} legs cheap (max dv {mxdv:.1f}), bad={bad}. "
          f"{'VALID cheap tour' if bad==0 else 'some legs exceed 100 (window drift)'} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
