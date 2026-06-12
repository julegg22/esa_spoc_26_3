"""Warm-started cooperative MIP-LNS on a matching instance, GUARD-BANKED.

Re-test of the matching ceiling under now-free cores: load the CURRENT
bank as the warm start (NOT a cold greedy), run N cooperative coop_mip_lns
workers sharing a pool-best file, and overwrite solutions/upload/<problem>.json
ONLY if the result is strictly better AND feasible (each e/l/d used once),
after a backup. Never submits.

Run: PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
       python -u scripts/ch1_matching_lns_warmbank.py matching-i 600 4
"""
from __future__ import annotations

import datetime
import json
import multiprocessing as mp
import os
import shutil
import sys

import numpy as np

from esa_spoc_26.ch1_matching import coop_mip_lns, load_instance

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}
CHALLENGE = "spoc-4-luna-tomato-logistics"


def _feasible(e, ll, d, x):
    return all(arr[x == 1].size == np.unique(arr[x == 1]).size for arr in (e, ll, d))


def _worker(args):
    path, seed, budget, time_per_sub, pool = args
    e, ll, d, w = load_instance(path)
    x0m, x0 = _read_pool(pool)  # all workers start from the shared bank seed
    best, bm, rounds = coop_mip_lns(
        e, ll, d, w, x0, seed=seed, threads=1, time_budget_s=budget,
        time_per_sub=time_per_sub, pool_best_path=pool, sync_every=15,
    )
    return float(bm), best.astype(np.int8), int(seed), int(rounds)


def _read_pool(path):
    v = np.load(path, allow_pickle=False)
    return float(v[0]), v[1:].astype(np.int8)


def main():
    problem = sys.argv[1]
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    path = INST[problem]
    bankp = f"solutions/upload/{problem}.json"

    e, ll, d, w = load_instance(path)
    x0 = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
    assert x0.size == w.size, f"bank dim {x0.size} != instance {w.size}"
    assert _feasible(e, ll, d, x0), "current bank is INFEASIBLE — abort"
    bank_mass = float(w[x0 == 1].sum())
    print(f"{problem}: bank mass {bank_mass:.3f} ({int(x0.sum())} sel), "
          f"{nw} workers x {budget:.0f}s warm-started", flush=True)

    # seed the shared pool with the current bank so every worker starts there
    pool = f"/tmp/matchlns_pool_{problem}.npy"
    np.save(pool, np.concatenate([[bank_mass], x0.astype(np.int8)]))

    args = [(path, s, budget, 8.0, pool) for s in range(nw)]
    with mp.Pool(nw) as p:
        res = p.map(_worker, args)
    bm, bx, seed, rounds = max(res, key=lambda r: r[0])
    print(f"best across workers: {bm:.3f} (seed {seed}, {rounds} rounds)",
          flush=True)

    if bm > bank_mass + 1e-6 and _feasible(e, ll, d, bx):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("/tmp/bank_bak", exist_ok=True)
        shutil.copy(bankp, f"/tmp/bank_bak/{problem}_{ts}.json")
        shutil.copy(bankp, f"{bankp}.bak.lnswarm")
        json.dump([{"decisionVector": bx.tolist(), "problem": problem,
                    "challenge": CHALLENGE}], open(bankp, "w"))
        # round-trip verify
        rt = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
        rtm = float(w[rt == 1].sum())
        print(f"=== BANKED {problem} {bank_mass:.3f} -> {rtm:.3f} "
              f"(+{rtm - bank_mass:.3f}); feasible; backup saved ===", flush=True)
    else:
        print(f"=== NO IMPROVEMENT (best {bm:.3f} <= bank {bank_mass:.3f}); "
              f"bank untouched ===", flush=True)


if __name__ == "__main__":
    main()
