"""E-581 memetic / path-relinking for Ch1 matching (the one untried
basin-crosser on the monolithic conflict graph; E-580 probe ruled out
component-decomposition and kernel reduction).

Recombination (the basin-cross): given two feasible parent packings,
  core   = transfers selected in BOTH parents  (feasible: subset of each)
  cand   = transfers whose e/l/d nodes are ALL free of the core
  child  = core  U  exact-max-weight-matching(cand)        [_solve_sub]
The freed region is exactly the parents' DISAGREEMENT, so for two similar
strong parents it is small and _solve_sub solves it to TRUE optimality.
Offspring mass is provably >= max(parent masses) (each parent's region
selection is a feasible sub-matching on cand, so the exact solve dominates
it); the child lands in a basin combining both parents -> can exceed both.

Pool: K diverse strong packings (bank + perturbed-greedy seeds, each
ejection+mip_lns polished). Recombine random distinct pairs; insert a
child if it beats the pool-worst AND is Hamming-distinct (diversity).
4 workers, shared global best via the module pool file.

Guard-banked (backup + strict-improve + feasibility + round-trip); never
submits. Usage: python ch1_e581_matching_memetic.py <problem> <budget_s>
<n_workers> <pool_K> <time_per_sub_s>
"""
import json
import multiprocessing as mp
import os
import shutil
import sys
import time

import numpy as np

from esa_spoc_26.ch1_matching import (
    _owner_maps,
    _read_pool_best,
    _solve_sub,
    _write_pool_best,
    ejection_improve,
    load_instance,
    mip_lns,
)

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}
UPLOAD = {"matching-i": "solutions/upload/matching-i.json",
          "matching-ii": "solutions/upload/matching-ii.json"}
CHALLENGE = "spoc-4-luna-tomato-logistics"


def _feasible(e, ll, d, x):
    return all(arr[x == 1].size == np.unique(arr[x == 1]).size for arr in (e, ll, d))


def randomized_greedy(e, ll, d, w, rng, alpha, ne, nl, nd):
    n = w.shape[0]
    keys = w * np.exp(alpha * rng.standard_normal(n))
    order = np.argsort(-keys, kind="stable")
    ue = np.zeros(ne, bool)
    ul = np.zeros(nl, bool)
    ud = np.zeros(nd, bool)
    x = np.zeros(n, dtype=np.int8)
    for i in order:
        if ue[e[i]] or ul[ll[i]] or ud[d[i]]:
            continue
        x[i] = 1
        ue[e[i]] = ul[ll[i]] = ud[d[i]] = True
    return x


def recombine(e, ll, d, w, xa, xb, ne, nl, nd, time_per_sub, threads):
    core = (xa == 1) & (xb == 1)
    ue = np.zeros(ne, bool)
    ul = np.zeros(nl, bool)
    ud = np.zeros(nd, bool)
    ue[e[core]] = True
    ul[ll[core]] = True
    ud[d[core]] = True
    cand = np.flatnonzero((~core) & ~ue[e] & ~ul[ll] & ~ud[d])
    x = core.astype(np.int8)
    if cand.size:
        sub = _solve_sub(e[cand], ll[cand], d[cand], w[cand], time_per_sub, threads)
        x[cand[sub == 1]] = 1
    return x, float(w[x == 1].sum())


def _seed_pool(e, ll, d, w, order, ne, nl, nd, bank_x, K, rng, seed, budget_frac, t0, budget):
    """bank + (K-1) perturbed-greedy basins, each ejection+mip_lns polished."""
    pool = [(float(w[bank_x == 1].sum()), bank_x.copy())]
    slice_s = max(4.0, budget_frac * budget / max(1, K - 1))
    for j in range(K - 1):
        if time.time() - t0 > budget_frac * budget:
            break
        a = 0.10 * (1.0 + 0.6 * ((seed + j) % 4))
        x = randomized_greedy(e, ll, d, w, rng, a, ne, nl, nd)
        se, sl, sd = _owner_maps(e, ll, d, x, ne, nl, nd)
        ejection_improve(e, ll, d, w, x, order, se, sl, sd)
        rem = budget - (time.time() - t0)
        x, m, _ = mip_lns(e, ll, d, w, x, drop_frac=0.25, time_per_sub=6.0,
                          seed=seed * 100 + j, threads=1,
                          time_budget_s=min(slice_s, rem))
        pool.append((m, x.astype(np.int8)))
    return pool


def _distinct(x, pool, min_hamming=4):
    return all(int(np.count_nonzero(x != px)) >= min_hamming for _, px in pool)


def memetic_worker(args):
    path, seed, budget, K, time_per_sub, poolfile, bank_x = args
    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    order = np.argsort(-w, kind="stable")
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    rng = np.random.default_rng(seed)
    t0 = time.time()

    pool = _seed_pool(e, ll, d, w, order, ne, nl, nd, bank_x, K, rng, seed,
                      0.20, t0, budget)
    pool.sort(key=lambda t: -t[0])
    best_m, best_x = pool[0][0], pool[0][1].copy()
    _write_pool_best(poolfile, best_m, best_x)
    print(f"[w{seed}] seeded pool K={len(pool)} masses="
          f"{[round(m, 2) for m, _ in pool]} t={time.time() - t0:.0f}s", flush=True)

    it = 0
    children = 0
    last_log = t0
    while time.time() - t0 < budget:
        it += 1
        # pull a sibling's better basin into the pool occasionally
        gm, gx = _read_pool_best(poolfile)
        if gx is not None and gm > pool[-1][0] + 1e-6 and _distinct(gx, pool):
            pool[-1] = (float(gm), gx.astype(np.int8))
            pool.sort(key=lambda t: -t[0])
        # pick two distinct parents (bias: elite x random for diversity)
        i = rng.integers(0, len(pool))
        j = rng.integers(0, len(pool))
        if i == j:
            continue
        xa, xb = pool[i][1], pool[j][1]
        rem = budget - (time.time() - t0)
        if rem <= 1:
            break
        child, cm = recombine(e, ll, d, w, xa, xb, ne, nl, nd,
                              min(time_per_sub, rem), 1)
        # polish the child a touch on its own basin
        se, sl, sd = _owner_maps(e, ll, d, child, ne, nl, nd)
        cm = ejection_improve(e, ll, d, w, child, order, se, sl, sd)
        children += 1
        worst = pool[-1][0]
        if cm > worst + 1e-6 and _distinct(child, pool):
            pool[-1] = (cm, child.astype(np.int8))
            pool.sort(key=lambda t: -t[0])
        if cm > best_m + 1e-6:
            best_m, best_x = cm, child.astype(np.int8).copy()
            _write_pool_best(poolfile, best_m, best_x)
        if time.time() - last_log > 30:
            last_log = time.time()
            print(f"[w{seed}] it={it} children={children} best={best_m:.3f} "
                  f"poolbest={pool[0][0]:.3f} poolworst={pool[-1][0]:.3f} "
                  f"t={time.time() - t0:.0f}s", flush=True)
    print(f"[w{seed}] DONE it={it} children={children} best={best_m:.3f} "
          f"t={time.time() - t0:.0f}s", flush=True)
    return best_m, best_x.astype(np.int8), int(seed)


def _guard_bank(problem, e, ll, d, w, x, bank_mass):
    up = UPLOAD[problem]
    m = float(w[x == 1].sum())
    if not (m > bank_mass + 1e-6 and _feasible(e, ll, d, x)):
        print(f"=== NO IMPROVEMENT (best {m:.3f} <= bank {bank_mass:.3f}); "
              f"bank untouched ===", flush=True)
        return
    os.makedirs("/tmp/bank_bak", exist_ok=True)
    if os.path.exists(up):
        shutil.copy2(up, f"/tmp/bank_bak/{os.path.basename(up)}.e581.bak")
        shutil.copy2(up, up + ".bak")
    with open(up, "w") as f:
        json.dump([{"decisionVector": x.astype(np.int8).tolist(),
                    "problem": problem, "challenge": CHALLENGE}], f)
    # round-trip verify
    with open(up) as f:
        rt = json.load(f)
    rx = np.asarray(rt[0]["decisionVector"], dtype=np.int8)
    rtm = float(w[rx == 1].sum())
    if not (_feasible(e, ll, d, rx) and abs(rtm - m) < 1e-6):
        if os.path.exists(up + ".bak"):
            shutil.copy2(up + ".bak", up)
        print(f"=== ROUND-TRIP FAILED (rt={rtm:.3f} vs {m:.3f}); RESTORED bank ===",
              flush=True)
        return
    print(f"=== BANKED {problem} {bank_mass:.3f} -> {rtm:.3f} "
          f"(+{rtm - bank_mass:.3f}); UNSUBMITTED ===", flush=True)


def _load_bank_x(problem, n):
    up = UPLOAD[problem]
    if os.path.exists(up):
        with open(up) as f:
            dv = json.load(f)[0]["decisionVector"]
        x = np.asarray(dv, dtype=np.int8)
        return x if x.shape[0] == n else None
    return None


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-ii"
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 3600.0
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    time_per_sub = float(sys.argv[5]) if len(sys.argv) > 5 else 10.0

    path = INST[problem]
    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    bank_x = _load_bank_x(problem, n)
    if bank_x is None:
        from esa_spoc_26.ch1_matching import greedy
        bank_x = greedy(e, ll, d, w)
    assert _feasible(e, ll, d, bank_x), "bank infeasible"
    bank_mass = float(w[bank_x == 1].sum())
    print(f"{problem}: bank mass {bank_mass:.3f} ({int(bank_x.sum())} sel); "
          f"{nw} workers x {budget:.0f}s memetic, pool_K={K}, "
          f"time_per_sub={time_per_sub}s", flush=True)

    poolfile = f"/tmp/e581_pool_{problem}.npy"
    if os.path.exists(poolfile):
        os.remove(poolfile)
    _write_pool_best(poolfile, bank_mass, bank_x)

    args = [(path, s, budget, K, time_per_sub, poolfile, bank_x) for s in range(nw)]
    with mp.Pool(nw) as p:
        res = p.map(memetic_worker, args)

    bm, bx, bs = max(res, key=lambda r: r[0])
    print(f"best across workers: {bm:.3f} (seed {bs})", flush=True)
    print(f"per-worker best: {sorted(round(r[0], 3) for r in res)}", flush=True)
    _guard_bank(problem, e, ll, d, w, bx, bank_mass)


if __name__ == "__main__":
    main()
