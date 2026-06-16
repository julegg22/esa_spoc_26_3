"""E-579: Late-Acceptance Hill Climbing (LAHC) for Ch1 matching.

WHY (deep review 2026-06-14): every prior matching engine — lns, mip_lns,
coop_mip_lns — is an IMPROVEMENT-ONLY hill-climber with RANDOM-ONLY destroy.
They accept a neighbour only if `m >= best` and otherwise reset to `best`, so
they can never take a lateral/worsening step across a ridge into a different
basin. CP-SAT-LNS solving 6000-var windows to PROVEN optimal with 0 gain is the
fingerprint of exactly this: every neighbourhood reachable WITHOUT a downhill
step is already optimal => the bank is a local, not global, optimum. The
leaderboard top team's incumbent LADDER (matching-ii 73714->73709->73697x3->...)
is the fingerprint of an acceptance metaheuristic ratcheting across basins, which
is what we lack.

Smallest highest-ROI change: keep the SAME ruin-and-recreate neighbour as `lns`
(random ruin -> ejection_improve repair) but swap the acceptance rule for LAHC.
LAHC accepts a candidate if it is no worse than the current solution OR no worse
than the cost the search held `L` steps ago. That single change lets the
incumbent drift downhill through a worse local optimum and re-climb in a new
basin, which improvement-only search structurally cannot do.

Stage-0 diagnosis is folded into the startup log: per-node-type slack (unused
Earth/Moon/dest nodes = raw headroom) and the gap to the known leaderboard r1
incumbent, so we measure how much basin-crossing could in principle buy.

Workers run independent LAHC (different seeds + ruin sizes) and share a global
best via a pool file; worker 0 seeds from the CURRENT BANK so we never regress.
GUARD-BANKED: overwrites solutions/upload/<problem>.json ONLY if strictly better
AND feasible, after a backup, with round-trip verify. Never submits.

Engine = EXACT repair (HiGHS max-weight 3-D matching on the freed window, as in
coop_mip_lns) UNDER LAHC acceptance + targeted (random/worst/blocking) destroy.
The existing exact-LNS engines have the same strong repair but accept only
`m >= best` (improvement-only) and so cannot cross a ridge; swapping in LAHC
acceptance is the untried basin-overarching capability (see
vault/methodology/M-general-basin-overarching-search.md).

Run:
  PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
    python -u scripts/ch1_e579_matching_lahc.py matching-ii 3600 4 6 20000 4
  args: <problem> <budget_s> <n_workers> <ruin_k> <lahc_len> <time_per_sub_s>
  ruin_k = small ABSOLUTE base count of transfers to destroy per move (NOT a
  fraction): the bank is already a single-swap local optimum, so improvement
  requires a few coordinated blocker drops, not a large ruin.
  time_per_sub = HiGHS time cap per exact-repair window solve.
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
    _solve_sub,
    _write_pool_best,
    ejection_improve,
    load_instance,
)

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}
CHALLENGE = "spoc-4-luna-tomato-logistics"
# known leaderboard r1 incumbent mass (fetch_leaderboards.py, 2026-06-14) — for
# the Stage-0 gap log only; never used as a target/threshold.
R1_MASS = {"matching-i": 33555.615, "matching-ii": 73714.033}


def _feasible(e, ll, d, x):
    return all(arr[x == 1].size == np.unique(arr[x == 1]).size for arr in (e, ll, d))


def _exact_repair(e, ll, d, w, x, ne, nl, nd, time_per_sub, threads):
    """Strong repair: exact max-weight 3-D matching (HiGHS) on the transfers
    whose e/l/d nodes are ALL currently free. This is bank-quality reconstruction
    — greedy repair lands strictly below a sharp incumbent every time (2026-06-14
    smoke), so an acceptance metaheuristic on greedy repair can never exceed the
    bank. The existing exact-LNS engines (mip_lns/coop_mip_lns) HAVE this repair
    but are improvement-only; the new capability is exact repair UNDER LAHC
    acceptance, so the search exact-repairs its way ACROSS basins, not within."""
    kept = np.flatnonzero(x)
    ue = np.zeros(ne, bool)
    ul = np.zeros(nl, bool)
    ud = np.zeros(nd, bool)
    ue[e[kept]] = True
    ul[ll[kept]] = True
    ud[d[kept]] = True
    idx = np.flatnonzero((x == 0) & ~ue[e] & ~ul[ll] & ~ud[d])
    if idx.size:
        sub = _solve_sub(e[idx], ll[idx], d[idx], w[idx], time_per_sub, threads)
        x[idx[sub == 1]] = 1
    return float(w[x == 1].sum())


DESTROY = ("random", "worst", "blocking")


def _destroy(op, x, e, ll, d, w, order, se, sl, sd, k, rng):
    """Return the array of SELECTED transfer indices to remove (ruin set).

    Smoke test (2026-06-14) showed random ruin + repair lands at a near-rigid
    mass: the acceptance rule alone (LAHC vs improvement-only) barely matters
    because random destroy never reaches a different basin. These targeted
    operators are the load-bearing change — `blocking` in particular frees
    exactly the nodes that heavy EXCLUDED transfers are waiting on (the 536
    unused-node headroom)."""
    sel = np.flatnonzero(x)
    if sel.size == 0:
        return sel
    if op == "random":
        return rng.choice(sel, size=min(k, sel.size), replace=False)
    if op == "worst":
        # drop the k lowest-weight selected transfers -> frees nodes for heavier
        return sel[np.argsort(w[sel], kind="stable")[:k]]
    # "blocking": for the heaviest excluded transfers, drop the selected
    # transfers currently occupying their nodes so the repair can insert them.
    excl = np.flatnonzero(x == 0)
    excl = excl[np.argsort(-w[excl], kind="stable")[: 4 * k]]
    blockers = []
    seen = set()
    for i in excl:
        for owner in (se[e[i]], sl[ll[i]], sd[d[i]]):
            if owner != -1 and owner not in seen:
                seen.add(int(owner))
                blockers.append(int(owner))
        if len(blockers) >= k:
            break
    if not blockers:
        return rng.choice(sel, size=min(k, sel.size), replace=False)
    return np.asarray(blockers[:k], dtype=np.int64)


def _diagnose(e, ll, d, w, x, problem):
    """Stage-0: raw headroom = unused nodes per type; gap to r1 incumbent."""
    sel = np.flatnonzero(x)
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    used_e, used_l, used_d = np.unique(e[sel]).size, np.unique(ll[sel]).size, np.unique(d[sel]).size
    mass = float(w[sel].sum())
    r1 = R1_MASS.get(problem)
    gap = f"{r1 - mass:+.3f} ({100 * (r1 - mass) / r1:.3f}%)" if r1 else "n/a"
    print(f"[diag {problem}] bank mass={mass:.3f}, sel={sel.size}; "
          f"unused nodes: Earth {ne - used_e}/{ne}, Moon {nl - used_l}/{nl}, "
          f"dest {nd - used_d}/{nd}; gap to r1={gap}", flush=True)


def lahc_worker(args):
    path, seed, budget, ruin_k, lahc_len, time_per_sub, pool, bank_x = args
    e, ll, d, w = load_instance(path)
    order = np.argsort(-w, kind="stable")
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    rng = np.random.default_rng(seed)

    # per-worker ruin size + history length for diversity. The ruin is a SMALL
    # ABSOLUTE count of transfers, not a fraction: the bank is already an
    # ejection_improve local optimum (no profitable single swap), so the only
    # improving move is a few COORDINATED blocker drops that let a heavy
    # excluded transfer enter where no single swap was profitable.
    kbase = max(2, ruin_k + 3 * (seed % 4))
    L = max(1, int(lahc_len * (1.0 + 0.25 * (seed % 3))))

    # start cur = bank (a true local optimum). EXACT repair reconstructs to
    # bank-quality, so the history can be pinned at bank_cost without freezing
    # (the greedy-repair freeze of the earlier smoke test does not apply here).
    cur = bank_x.copy()
    se, sl, sd = _owner_maps(e, ll, d, cur, ne, nl, nd)
    cur_cost = ejection_improve(e, ll, d, w, cur, order, se, sl, sd)
    best, best_cost = cur.copy(), cur_cost
    hist = np.full(L, cur_cost, dtype=np.float64)

    # adaptive destroy-operator weights (ALNS roulette); reward new global best
    op_w = np.ones(len(DESTROY))
    op_use = np.zeros(len(DESTROY), dtype=np.int64)
    op_win = np.zeros(len(DESTROY), dtype=np.int64)

    t0 = time.time()
    it = accepted = worsening = 0
    last_sync = 0.0
    while time.time() - t0 < budget:
        it += 1
        oi = rng.choice(len(DESTROY), p=op_w / op_w.sum())
        op_use[oi] += 1
        cand = cur.copy()
        cse, csl, csd = _owner_maps(e, ll, d, cand, ne, nl, nd)
        k = rng.integers(2, kbase + 1)  # vary ruin size within [2, kbase]
        ruin = _destroy(DESTROY[oi], cand, e, ll, d, w, order, cse, csl, csd, k, rng)
        cand[ruin] = 0
        cand_cost = _exact_repair(e, ll, d, w, cand, ne, nl, nd, time_per_sub, 1)

        v = it % L
        if cand_cost >= cur_cost or cand_cost >= hist[v]:
            if cand_cost < cur_cost - 1e-9:
                worsening += 1
            cur, cur_cost = cand, cand_cost
            accepted += 1
        if cur_cost > hist[v]:
            hist[v] = cur_cost
        if cur_cost > best_cost + 1e-9:
            best, best_cost = cur.copy(), cur_cost
            op_win[oi] += 1
            op_w[oi] += 2.0  # reward the operator that broke a new best
            _write_pool_best(pool, best_cost, best)

        # rare cooperation: adopt global best only to update `best` tracking,
        # NOT `cur` (preserve each worker's basin drift / diversity).
        now = time.time() - t0
        if now - last_sync > 30.0:
            last_sync = now
            op_w = 0.7 * op_w + 0.3  # decay toward uniform (keep exploring)
            gm, gx = _read_pool_best(pool)
            if gx is not None and gm > best_cost + 1e-9:
                best, best_cost = gx.copy(), float(gm)
            wins = {DESTROY[i]: f"{op_win[i]}/{op_use[i]}" for i in range(len(DESTROY))}
            print(f"[w{seed}] it={it} cur={cur_cost:.3f} best={best_cost:.3f} "
                  f"acc={accepted} (wors={worsening}) wins={wins} "
                  f"t={now:.0f}s", flush=True)
    return best_cost, best.astype(np.int8), int(seed), int(it), int(worsening)


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-ii"
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 3600.0
    nw = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    ruin_k = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    lahc_len = int(sys.argv[5]) if len(sys.argv) > 5 else 20000
    time_per_sub = float(sys.argv[6]) if len(sys.argv) > 6 else 4.0
    path = INST[problem]
    bankp = f"solutions/upload/{problem}.json"

    e, ll, d, w = load_instance(path)
    bank_x = np.asarray(json.load(open(bankp))[0]["decisionVector"], dtype=np.int8)
    assert bank_x.size == w.size, f"bank dim {bank_x.size} != instance {w.size}"
    assert _feasible(e, ll, d, bank_x), "current bank is INFEASIBLE — abort"
    bank_mass = float(w[bank_x == 1].sum())
    _diagnose(e, ll, d, w, bank_x, problem)
    print(f"{problem}: bank mass {bank_mass:.3f} ({int(bank_x.sum())} sel); "
          f"{nw} workers x {budget:.0f}s LAHC (exact repair), ruin_k={ruin_k}, "
          f"lahc_len={lahc_len}, time_per_sub={time_per_sub}s", flush=True)

    pool = f"/tmp/lahc_pool_{problem}.npy"
    _write_pool_best(pool, bank_mass, bank_x)

    args = [(path, s, budget, ruin_k, lahc_len, time_per_sub, pool, bank_x)
            for s in range(nw)]
    with mp.Pool(nw) as p:
        res = p.map(lahc_worker, args)
    bm, bx, seed, it, wors = max(res, key=lambda r: r[0])
    # final strict-local-optimum polish of the cross-worker best (LAHC drifts on
    # the plateau; the banked solution must be re-climbed, not left mid-drift)
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    se, sl, sd = _owner_maps(e, ll, d, bx, ne, nl, nd)
    bx = bx.copy()
    pm = ejection_improve(e, ll, d, w, bx, np.argsort(-w, kind="stable"), se, sl, sd)
    if pm > bm:
        print(f"final ejection polish: {bm:.3f} -> {pm:.3f}", flush=True)
        bm = pm
    bx = bx.astype(np.int8)
    print(f"best across workers: {bm:.3f} (seed {seed}, {it} iters, "
          f"{wors} worsening-accepts)", flush=True)
    print(f"per-worker best: {sorted(round(r[0], 3) for r in res)}", flush=True)
    tot_wors = sum(r[4] for r in res)
    print(f"total worsening-accepts across workers: {tot_wors} "
          f"(0 => LAHC degenerated to improvement-only; >0 => basin-crossing "
          f"actually exercised)", flush=True)

    if bm > bank_mass + 1e-6 and _feasible(e, ll, d, bx):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("/tmp/bank_bak", exist_ok=True)
        shutil.copy(bankp, f"/tmp/bank_bak/{problem}_{ts}.json")
        shutil.copy(bankp, f"{bankp}.bak.lahc")
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
              f"bank untouched ===", flush=True)


if __name__ == "__main__":
    main()
