"""E-657 lever #2 (cluster-first): solve Ch2-small's 40-city GIANT cheap-component as a TSP,
stitch the 3×3 satellites via exception bridges, walk faithfully. Construction (greedy+beam)
strands; local search stuck; the loss is epoch-phasing inside the giant. Cluster-first solves
the giant's internal order then bridges — the structure the bank/competitors use.

Giant TSP: try elkai-LKH on the 40-node epoch-min-tof matrix (small ⇒ precision may work);
fallback nearest-neighbor + 2-opt. Assembly: giant path -exc-> S1 -exc-> S2 -exc-> S3 (3 bridges
≤5 exc), each component a cheap sub-path, bridges = cheapest exc edges between endpoints.
Faithful eval walk_perm_chrono/kt.fitness vs bank 112.996. Usage: python ch2_giant_tsp_small.py [ntry=300]
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
STRICT = dict(tof_window=12.0, n_steps=200, wait_steps=8, wait_dt=0.5)


def two_opt_path(nodes, D, rng, iters=4000):
    """2-opt on an OPEN path over `nodes` minimizing sum of D along it."""
    p = nodes[:]; rng.shuffle(p)
    def plen(p): return sum(D[p[i], p[i + 1]] for i in range(len(p) - 1))
    best = plen(p)
    for _ in range(iters):
        i, j = sorted(rng.sample(range(len(p)), 2))
        if j - i < 1: continue
        q = p[:i] + p[i:j + 1][::-1] + p[j + 1:]
        l = plen(q)
        if l < best - 1e-12: p, best = q, l
    return p, best


def giant_tour(gnodes, D, rng):
    """Try elkai-LKH (cycle) on the giant submatrix; else 2-opt open path. Return ordered path."""
    g = list(gnodes); idx = {c: k for k, c in enumerate(g)}
    sub = np.array([[D[a, b] for b in g] for a in g])
    fin = np.isfinite(sub); BIG = (sub[fin].max() if fin.any() else 1.0) * 100
    S = np.where(fin, sub, BIG)
    try:
        import elkai
        M = np.round(S * 1000).astype(np.int64)
        np.fill_diagonal(M, 0)
        cyc = elkai.DistanceMatrix(M.tolist()).solve_tsp()
        cyc = cyc[:-1] if cyc[0] == cyc[-1] else cyc
        order = [g[k] for k in cyc]
        # break cycle at longest edge -> open path
        w = max(range(len(order)), key=lambda k: D[order[k], order[(k + 1) % len(order)]]
                if np.isfinite(D[order[k], order[(k + 1) % len(order)]]) else 1e9)
        return order[w + 1:] + order[:w + 1], "elkai-LKH"
    except Exception as e:
        path, _ = two_opt_path(g, D, rng)
        return path, f"2opt(elkai failed: {str(e)[:40]})"


def main(ntry=300):
    kt = KTTSP(INST); n = kt.n
    d = np.load('/tmp/ch2_small_tcoupled_ultrafine.npz')
    Dcheap = np.min(d['cheap'], axis=2)          # min cheap tof over epochs (inf if never cheap)
    Dexc = np.min(d['exc'], axis=2)              # min exc tof (for bridges)
    adj = np.load('/tmp/ch2_small_cheap_adj.npy')
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    comps = [list(np.where(lab == c)[0]) for c in range(nc)]
    comps.sort(key=len, reverse=True)
    giant, sats = comps[0], comps[1:]
    bank = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
    print(f"[E-657] n={n} bank={bank:.3f} | {nc} comps: giant={len(giant)} sats={[len(s) for s in sats]}", flush=True)

    rng = random.Random(0)
    gpath, how = giant_tour(giant, Dcheap, rng)
    print(f"[giant] solved via {how}; giant path len={len(gpath)} "
          f"static cheap-cost={sum(Dcheap[gpath[i],gpath[i+1]] for i in range(len(gpath)-1)):.2f}d", flush=True)

    def sat_path(s):
        if len(s) <= 2: return s
        p, _ = two_opt_path(s, Dcheap, rng); return p

    best_mk = 1e9; best_x = None; nfeas = 0; t0 = time.time()
    for t in range(ntry):
        # randomize giant orientation + satellite order/orientation, stitch with cheapest exc bridges
        gp = gpath[:] if rng.random() < 0.5 else gpath[::-1]
        order = list(gp)
        rem = [sat_path(s) for s in sats]; rng.shuffle(rem)
        for sp in rem:
            sp = sp if rng.random() < 0.5 else sp[::-1]
            order += sp                          # bridge = exc edge between order[-1 before] and sp[0] (walk handles timing)
        if len(set(order)) != n: continue
        times, tofs, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
        if not ok: continue
        nfeas += 1
        x = list(times) + list(tofs) + [float(p) for p in order]
        f = kt.fitness(x)
        if kt.is_feasible(f) and f[0] < best_mk:
            best_mk = float(f[0]); best_x = x
            tag = " *** <BANK" if best_mk < bank else ""
            print(f"  [t{t}] feasible mk={best_mk:.3f} ({best_mk-bank:+.3f}){tag}", flush=True)
        if t % 100 == 0 and t:
            print(f"  [t{t}] feasible={nfeas} best={best_mk:.3f} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[DONE] giant via {how} | {nfeas}/{ntry} feasible assemblies | best mk={best_mk:.3f} "
          f"vs bank {bank:.3f} | rank4=111.76 rank3=110.88", flush=True)
    if best_x is not None and best_mk < bank - 1e-4:
        json.dump({"makespan": best_mk, "decisionVector": best_x}, open('/tmp/ch2_small_giant_best.json', 'w'))
        v = "BEATS rank4!" if best_mk < 111.76 else "beats bank"
        print(f"  -> {v}; dumped /tmp/ch2_small_giant_best.json", flush=True)
    else:
        print(f"  -> giant-TSP+stitch did NOT beat bank (best feasible {best_mk:.3f}). "
              f"If 0 feasible: bridge structure needs explicit exc-edge endpoint selection (next).", flush=True)


if __name__ == "__main__":
    nt = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    main(nt)
