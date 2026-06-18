"""E-658 lever #2 final: ITERATED EPOCH-AWARE LKH on Ch2-small's 40-giant.

Fixes both blockers: (1) the e576 time-dependent reordering trap (static-LKH order inflates
when walked), and (2) the slow Lambert walk (use the precomputed table for the inner realized-
epoch walk; only ONE faithful walk at the end). Loop: LKH(cost) -> table-walk to get REALIZED
per-leg tofs at the walked epochs -> update cost to those realized tofs -> re-LKH -> repeat to
fixpoint. This converges the order toward the time-dependent optimum. Then assemble satellites
via explicit exc bridges + faithful walk vs bank 112.996.
Usage: python ch2_giant_iterlkh_small.py [iters=10]
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


def lkh_path(nodes, D):
    """elkai-LKH cycle on submatrix over `nodes`, broken into an open path at longest edge."""
    import elkai
    g = list(nodes); sub = np.array([[D[a, b] for b in g] for a in g])
    fin = np.isfinite(sub); BIG = (sub[fin].max() if fin.any() else 1.0) * 100
    S = np.where(fin, sub, BIG)
    M = np.round(S * 1000).astype(np.int64); np.fill_diagonal(M, 0)
    cyc = elkai.DistanceMatrix(M.tolist()).solve_tsp()
    cyc = cyc[:-1] if cyc[0] == cyc[-1] else cyc
    order = [g[k] for k in cyc]
    w = max(range(len(order)), key=lambda k: S[cyc[k], cyc[(k + 1) % len(order)]])
    return order[w + 1:] + order[:w + 1]


def table_walk(order, cheap, q, T, t0=0.0):
    """FAST realized-epoch walk on the table (no Lambert): returns makespan + realized tof per leg."""
    ep = t0; tofs = []
    for i in range(len(order) - 1):
        b = int(round(ep / q)); b = b if b < T else T - 1
        tof = cheap[order[i], order[i + 1], b]
        if not np.isfinite(tof):
            return None, None            # infeasible leg at this epoch
        tofs.append(tof); ep += tof
    return ep - t0, tofs


def main(iters=10):
    kt = KTTSP(INST); n = kt.n
    d = np.load('/tmp/ch2_small_tcoupled_ultrafine.npz')
    cheap = d['cheap']; q = float(d['t_starts'][1] - d['t_starts'][0]); T = len(d['t_starts'])
    Dmin = np.min(cheap, axis=2)
    adj = np.load('/tmp/ch2_small_cheap_adj.npy')
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    comps = sorted([list(np.where(lab == c)[0]) for c in range(nc)], key=len, reverse=True)
    giant, sats = comps[0], comps[1:]
    bank = float(kt.fitness(json.load(open(BANK))[0]['decisionVector'])[0])
    print(f"[E-658] n={n} bank={bank:.3f} | giant={len(giant)} sats={[len(s) for s in sats]}", flush=True)

    # ITERATE epoch-aware LKH on the giant
    cost = Dmin.copy()
    best_gorder = None; best_gmk = 1e9
    for it in range(iters):
        gorder = lkh_path(giant, cost)
        mk, tofs = table_walk(gorder, cheap, q, T)
        if mk is None:
            print(f"  [it{it}] LKH order infeasible at walked epochs (table-walk stranded)", flush=True)
            # perturb cost to escape
            cost = cost * (1 + 0.05 * np.random.default_rng(it).standard_normal(cost.shape))
            cost = np.where(np.isfinite(Dmin), np.abs(cost), np.inf); continue
        print(f"  [it{it}] giant table-walk makespan={mk:.3f}d (static LKH was 69.06 cheap-cost)", flush=True)
        if mk < best_gmk:
            best_gmk = mk; best_gorder = gorder
        # update cost to REALIZED tofs along this order (epoch-aware), keep Dmin elsewhere
        newcost = Dmin.copy()
        for i in range(len(gorder) - 1):
            newcost[gorder[i], gorder[i + 1]] = tofs[i]
        cost = newcost
    print(f"[giant] best epoch-aware giant table-walk makespan={best_gmk:.3f}d", flush=True)

    # ASSEMBLE: giant path -> satellites via explicit cheapest-exc bridges; faithful walk
    Dexc = np.min(d['exc'], axis=2); rng = random.Random(1)
    def sat_order(s):
        return s  # 3-city: any order; walk will time it
    best_mk = 1e9; best_x = None; nfeas = 0
    for trial in range(400):
        order = best_gorder[:] if rng.random() < 0.5 else best_gorder[::-1]
        rem = [s[:] for s in sats]; rng.shuffle(rem)
        for s in rem:
            rng.shuffle(s); order += s
        if len(set(order)) != n: continue
        times, tofs2, dvs, ok, exc, leg = walk_perm_chrono(kt, order, **STRICT)
        if not ok: continue
        nfeas += 1
        x = list(times) + list(tofs2) + [float(p) for p in order]
        f = kt.fitness(x)
        if kt.is_feasible(f) and f[0] < best_mk:
            best_mk = float(f[0]); best_x = x
            tag = " *** <BANK" if best_mk < bank else ""
            print(f"  [assemble t{trial}] official mk={best_mk:.3f} ({best_mk-bank:+.3f}){tag}", flush=True)
    print(f"\n[DONE] best epoch-aware giant table-walk={best_gmk:.3f} | assembled {nfeas}/400 feasible | "
          f"best official mk={best_mk:.3f} vs bank {bank:.3f} (rank4 111.76/rank3 110.88)", flush=True)
    if best_x is not None and best_mk < bank - 1e-4:
        json.dump({"makespan": best_mk, "decisionVector": best_x}, open('/tmp/ch2_small_iterlkh_best.json', 'w'))
        print(f"  -> {'BEATS rank4!' if best_mk<111.76 else 'beats bank'}; dumped /tmp/ch2_small_iterlkh_best.json", flush=True)
    else:
        print(f"  -> did not beat bank. INFO: best giant table-walk {best_gmk:.3f}; if « bank but assembly »bank, "
              f"the SATELLITE/bridge stitch is the residual loss (needs explicit exc-endpoint optimization).", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
