"""E-577: GRASP diverse multi-start for Ch1 matching (escape-the-basin probe).

Premise (deep review 2026-06-14): every prior matching run — coop_mip_lns,
mip_lns, CP-SAT-LNS up to ~6000-var regions solved to proven OPTIMAL — polishes
the SAME greedy/bank incumbent and finds ZERO improving moves (E-048 + the
cpsat_lns_ii logs). That proves the bank is optimal within every reachable
NEIGHBOURHOOD of one basin. The single untested variant of "compute-expensive
global search to escape basins" is therefore NOT a hotter local search (strictly
weaker than exact region re-opt) but DIVERSE CONSTRUCTION: build many different
high-quality starts and exact-polish each, sampling different basins.

Construction = perturbed-weight randomized greedy (multiplicative log-normal
noise on the weights reorders near-ties, so each seed lands in a different basin)
-> ejection_improve to a true local optimum -> mip_lns exact polish slice.
Workers cooperate via a shared pool-best file; worker 0 seeds from the CURRENT
BANK so we never lose ground. GUARD-BANKED: overwrites
solutions/upload/matching-ii.json ONLY if strictly better AND feasible, after a
backup, with round-trip verify. Never submits.

Run (after cores free):
  PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
    python -u scripts/ch1_e577_matching_grasp_multistart.py matching-ii 3600 4 0.12 90
  args: <problem> <total_budget_s> <n_workers> <alpha> <polish_slice_s>
"""
from __future__ import annotations

import datetime
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
    _write_pool_best,
    ejection_improve,
    greedy,
    load_instance,
    mip_lns,
)

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}
CHALLENGE = "spoc-4-luna-tomato-logistics"


def _feasible(e, ll, d, x):
    return all(arr[x == 1].size == np.unique(arr[x == 1]).size for arr in (e, ll, d))


def randomized_greedy(e, ll, d, w, rng, alpha):
    """Perturbed-weight greedy: order by w * exp(alpha * N(0,1)) so near-ties
    reshuffle (different basin per seed), but FEASIBILITY and the returned
    solution are scored on the TRUE weights. alpha=0 == deterministic greedy."""
    n = w.shape[0]
    keys = w * np.exp(alpha * rng.standard_normal(n))
    order = np.argsort(-keys, kind="stable")
    use_e = np.zeros(int(e.max()) + 1, dtype=bool)
    use_l = np.zeros(int(ll.max()) + 1, dtype=bool)
    use_d = np.zeros(int(d.max()) + 1, dtype=bool)
    x = np.zeros(n, dtype=np.int8)
    for i in order:
        ei, li, di = e[i], ll[i], d[i]
        if use_e[ei] or use_l[li] or use_d[di]:
            continue
        x[i] = 1
        use_e[ei] = use_l[li] = use_d[di] = True
    return x


def _worker(args):
    path, seed, budget, alpha, polish_slice, pool, bank_x = args
    e, ll, d, w = load_instance(path)
    n = w.shape[0]
    order = np.argsort(-w, kind="stable")
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    rng = np.random.default_rng(seed)

    best_x = bank_x.copy()
    best_m = float(w[best_x == 1].sum())
    t0 = time.time()
    restarts = 0
    while time.time() - t0 < budget:
        restarts += 1
        # construction: worker 0 first restart uses the BANK (never regress);
        # everyone else (and all later restarts) uses a perturbed-greedy basin.
        if seed == 0 and restarts == 1:
            x = bank_x.copy()
        else:
            a = alpha * (1.0 + 0.5 * (seed % 4))  # vary diversity across workers
            x = randomized_greedy(e, ll, d, w, rng, a)
        se, sl, sd = _owner_maps(e, ll, d, x, ne, nl, nd)
        ejection_improve(e, ll, d, w, x, order, se, sl, sd)
        # exact polish slice on this basin
        rem = budget - (time.time() - t0)
        if rem <= 1:
            break
        x, m, _ = mip_lns(
            e, ll, d, w, x, drop_frac=0.25, time_per_sub=8.0, seed=seed + restarts,
            threads=1, time_budget_s=min(polish_slice, rem),
        )
        if m > best_m + 1e-6:
            best_x, best_m = x.copy(), m
            _write_pool_best(pool, best_m, best_x)
        # cooperate: adopt the global best if a sibling found a better basin
        gm, gx = _read_pool_best(pool)
        if gx is not None and gm > best_m + 1e-6:
            best_x, best_m = gx.copy(), float(gm)
        print(f"[w{seed} r{restarts}] best={best_m:.3f} "
              f"t={time.time() - t0:.0f}s", flush=True)
    return best_m, best_x.astype(np.int8), int(seed), int(restarts)


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-ii"
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 3600.0
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    alpha = float(sys.argv[4]) if len(sys.argv) > 4 else 0.12
    polish_slice = float(sys.argv[5]) if len(sys.argv) > 5 else 90.0
    path = INST[problem]
    bankp = f"solutions/upload/{problem}.json"

    e, ll, d, w = load_instance(path)
    bank_x = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
    assert bank_x.size == w.size, f"bank dim {bank_x.size} != instance {w.size}"
    assert _feasible(e, ll, d, bank_x), "current bank is INFEASIBLE — abort"
    bank_mass = float(w[bank_x == 1].sum())
    print(f"{problem}: bank mass {bank_mass:.3f} ({int(bank_x.sum())} sel); "
          f"{nw} workers x {budget:.0f}s, alpha={alpha}, "
          f"polish_slice={polish_slice}s", flush=True)

    pool = f"/tmp/grasp_pool_{problem}.npy"
    _write_pool_best(pool, bank_mass, bank_x)

    args = [(path, s, budget, alpha, polish_slice, pool, bank_x) for s in range(nw)]
    with mp.Pool(nw) as p:
        res = p.map(_worker, args)
    bm, bx, seed, restarts = max(res, key=lambda r: r[0])
    print(f"best across workers: {bm:.3f} (seed {seed}, {restarts} restarts)",
          flush=True)
    print(f"per-worker: {sorted(round(r[0], 3) for r in res)}", flush=True)

    if bm > bank_mass + 1e-6 and _feasible(e, ll, d, bx):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("/tmp/bank_bak", exist_ok=True)
        shutil.copy(bankp, f"/tmp/bank_bak/{problem}_{ts}.json")
        shutil.copy(bankp, f"{bankp}.bak.grasp")
        json.dump([{"decisionVector": bx.tolist(), "problem": problem,
                    "challenge": CHALLENGE}], open(bankp, "w"))
        rt = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
        rtm = float(w[rt == 1].sum())
        ok = _feasible(e, ll, d, rt) and abs(rtm - bm) < 1e-6
        print(f"=== BANKED {problem} {bank_mass:.3f} -> {rtm:.3f} "
              f"(+{rtm - bank_mass:.3f}); round-trip {'OK' if ok else 'MISMATCH'}; "
              f"backup saved ===", flush=True)
    else:
        print(f"=== NO IMPROVEMENT (best {bm:.3f} <= bank {bank_mass:.3f}); "
              f"bank untouched — confirms single-basin ceiling ===", flush=True)


if __name__ == "__main__":
    main()
