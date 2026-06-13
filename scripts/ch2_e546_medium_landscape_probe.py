"""E-546 — Ch2 medium: solution-landscape diagnostic probe.

Purpose: understand what the medium fitness landscape looks like, so we
know where to invest compute. Specifically:

  1. Coarse-LKH diagnostic — generate an LKH-3 perm using the FULL coarse
     pair table (all 32580 pairs). Then evaluate via:
     a) walk_perm_chrono (real Lambert, no DP)
     b) Coarse-table DP (if works at all)
     c) Compare to bank
  2. Bank ↔ LKH pair-difference analysis — how many pairs do bank and
     LKH share?
  3. Random-shuffle exploration — generate 200 random perms (full shuffle
     + bank-anchored mutations), walk_perm_chrono each, get the mk
     histogram. Tells us:
     - What fraction of perms are walk-feasible?
     - What's the mk distribution of feasibles?
     - How far is bank from the median/best of randoms?
  4. Component structure probe — check what cheap-edge components medium
     has, identify if our pair set excludes structurally important pairs.

Single-threaded (won't interfere much with E-545's 4-core ALNS).
Outputs analysis to runs/ch2/e546_landscape.log + .json
"""
from __future__ import annotations
import sys, json, time, random
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

import elkai

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
COARSE = '/tmp/ch2_medium_tcoupled.npz'
FINE = '/tmp/ch2_medium_fine_pair_set.npz'
RESULT = '/tmp/ch2_e546_landscape.json'

DV_CHEAP = 100.0
DV_EXC = 600.0


def walk_evaluate(kt, perm):
    """walk_perm_chrono evaluation. Returns (mk, feas, exc_count) or None."""
    try:
        ts, tofs, dvs, ok, exc_n, last = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception:
        return None
    if not ok:
        return None
    mk = ts[-1] + tofs[-1]
    if exc_n > kt.n_exc:
        return None
    x = list(ts) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    return mk, feas, int(exc_n)


def lkh_perm_from_coarse(kt, cheap_min, exc_min):
    """Build cost matrix from coarse min-tof, solve via LKH-3."""
    n = kt.n
    BIG = 100000
    EXC_PEN = 10000
    cost = np.full((n, n), BIG, dtype=np.int64)
    for i in range(n):
        for j in range(n):
            if i == j:
                cost[i, j] = 0; continue
            c = cheap_min[i, j]
            if np.isfinite(c):
                cost[i, j] = int(round(c * 100))
            else:
                e = exc_min[i, j]
                if np.isfinite(e):
                    cost[i, j] = int(round(e * 100)) + EXC_PEN
    # Symmetric proxy
    sym = np.maximum(cost, cost.T)
    n2 = n + 1
    sym_d = np.zeros((n2, n2), dtype=np.int64)
    sym_d[:n, :n] = sym
    tour = elkai.solve_int_matrix(sym_d.tolist(), runs=5)
    # Drop dummy
    dummy_id = n
    i_d = tour.index(dummy_id)
    return tour[i_d+1:] + tour[:i_d]


def main():
    kt = KTTSP(INST); n = kt.n
    print(f"E-546 medium landscape probe. n={n}, n_exc={kt.n_exc}, "
          f"max_time={kt.max_time}d", flush=True)

    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk_recorded = float(kt.fitness(dv)[0])
    print(f"Bank perm: start={bank_perm[0]} end={bank_perm[-1]} "
          f"recorded mk={bank_mk_recorded:.4f}d", flush=True)

    # Walk-evaluate bank for reference
    print(f"\nValidating bank via walk_perm_chrono...", flush=True)
    bank_walk = walk_evaluate(kt, bank_perm)
    print(f"  walk: mk={bank_walk[0]:.4f}d feas={bank_walk[1]} "
          f"exc={bank_walk[2]}", flush=True)

    # ── Phase 1: coarse-LKH diagnostic ─────────────────────────────
    print(f"\n=== Phase 1: LKH-3 perm from coarse table ===", flush=True)
    d = np.load(COARSE)
    cheap_c = d['cheap']; exc_c = d['exc']
    cheap_min = np.nanmin(cheap_c, axis=2)
    exc_min = np.nanmin(exc_c, axis=2)
    np.fill_diagonal(cheap_min, np.inf)
    np.fill_diagonal(exc_min, np.inf)

    t0 = time.time()
    lkh_perm = lkh_perm_from_coarse(kt, cheap_min, exc_min)
    print(f"  LKH solved in {time.time()-t0:.1f}s. start={lkh_perm[0]} "
          f"end={lkh_perm[-1]} unique={len(set(lkh_perm))}",
          flush=True)
    lkh_walk = walk_evaluate(kt, lkh_perm)
    if lkh_walk is None:
        print(f"  LKH perm walk_perm_chrono REJECTED", flush=True)
        lkh_mk = None; lkh_exc = None; lkh_feas = False
    else:
        lkh_mk, lkh_feas, lkh_exc = lkh_walk
        print(f"  LKH perm walk: mk={lkh_mk:.4f}d feas={lkh_feas} "
              f"exc={lkh_exc}", flush=True)
        print(f"  vs bank {bank_walk[0]:.2f}d: "
              f"{'BETTER' if lkh_mk < bank_walk[0] else 'WORSE'} by "
              f"{abs(lkh_mk - bank_walk[0]):.2f}d", flush=True)

    # ── Phase 2: pair sharing analysis ─────────────────────────────
    print(f"\n=== Phase 2: pair-sharing analysis ===", flush=True)
    bank_pairs = set((bank_perm[k], bank_perm[k+1]) for k in range(n-1))
    lkh_pairs = set((lkh_perm[k], lkh_perm[k+1]) for k in range(n-1))
    shared = bank_pairs & lkh_pairs
    print(f"  bank pairs: {len(bank_pairs)}", flush=True)
    print(f"  lkh pairs:  {len(lkh_pairs)}", flush=True)
    print(f"  shared:     {len(shared)} "
          f"({len(shared)/len(bank_pairs)*100:.1f}%)", flush=True)
    print(f"  bank-only:  {len(bank_pairs - lkh_pairs)}", flush=True)
    print(f"  lkh-only:   {len(lkh_pairs - bank_pairs)}", flush=True)

    # How many LKH pairs are in our fine pair set?
    fine = np.load(FINE)
    fine_pair_set = set((int(i), int(j)) for i, j in fine['pair_set'])
    lkh_in_fine = sum(1 for p in lkh_pairs if p in fine_pair_set)
    bank_in_fine = sum(1 for p in bank_pairs if p in fine_pair_set)
    print(f"\n  bank pairs in fine table: {bank_in_fine}/{len(bank_pairs)} "
          f"({bank_in_fine/len(bank_pairs)*100:.1f}%)", flush=True)
    print(f"  lkh pairs in fine table:  {lkh_in_fine}/{len(lkh_pairs)} "
          f"({lkh_in_fine/len(lkh_pairs)*100:.1f}%)", flush=True)

    # ── Phase 3: random-shuffle exploration ────────────────────────
    print(f"\n=== Phase 3: random-shuffle landscape ===", flush=True)
    rng = random.Random(42)
    n_trials = 100
    n_feas = 0
    feas_mks = []
    # bank-anchored mutations (mostly 2-opt-like, k=20 random reinsert)
    bank_mut_mks = []
    n_bank_mut_feas = 0
    t0 = time.time()
    for trial in range(n_trials):
        # Random shuffle (preserve start/end of bank for fairness)
        p = list(bank_perm)
        middle = p[1:-1]
        rng.shuffle(middle)
        rp = [p[0]] + middle + [p[-1]]
        r = walk_evaluate(kt, rp)
        if r:
            n_feas += 1; feas_mks.append(r[0])
        # Bank-anchored: 5-20 random swaps
        bp = list(bank_perm)
        for _ in range(rng.randint(5, 20)):
            i = rng.randint(1, n-2); j = rng.randint(1, n-2)
            if i != j: bp[i], bp[j] = bp[j], bp[i]
        r = walk_evaluate(kt, bp)
        if r:
            n_bank_mut_feas += 1; bank_mut_mks.append(r[0])
    wall = time.time() - t0
    print(f"  {n_trials} random shuffles + {n_trials} bank-mutations "
          f"in {wall:.0f}s ({wall/(2*n_trials)*1000:.0f}ms/perm)",
          flush=True)
    print(f"\n  RANDOM SHUFFLES (start/end preserved):", flush=True)
    print(f"    walk-feasible: {n_feas}/{n_trials} = {n_feas/n_trials*100:.0f}%",
          flush=True)
    if feas_mks:
        print(f"    mk range: [{min(feas_mks):.1f}, {max(feas_mks):.1f}]d, "
              f"mean={np.mean(feas_mks):.1f}d, median={np.median(feas_mks):.1f}d",
              flush=True)
        n_below_bank = sum(1 for m in feas_mks if m < bank_walk[0])
        print(f"    below bank ({bank_walk[0]:.1f}): {n_below_bank}/{n_feas}",
              flush=True)

    print(f"\n  BANK-MUTATIONS (5-20 random swaps):", flush=True)
    print(f"    walk-feasible: {n_bank_mut_feas}/{n_trials} "
          f"= {n_bank_mut_feas/n_trials*100:.0f}%", flush=True)
    if bank_mut_mks:
        print(f"    mk range: [{min(bank_mut_mks):.1f}, "
              f"{max(bank_mut_mks):.1f}]d, mean={np.mean(bank_mut_mks):.1f}d, "
              f"median={np.median(bank_mut_mks):.1f}d", flush=True)
        n_below_bank = sum(1 for m in bank_mut_mks if m < bank_walk[0])
        print(f"    below bank ({bank_walk[0]:.1f}): {n_below_bank}/{n_bank_mut_feas}",
              flush=True)

    # ── Phase 4: component structure ───────────────────────────────
    print(f"\n=== Phase 4: cheap-edge component structure ===", flush=True)
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    adj_sym = np.isfinite(cheap_min) | np.isfinite(cheap_min).T
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym),
                                        directed=False)
    print(f"  Components: {nc}", flush=True)
    sizes = sorted([(int((lbl == c).sum()), c) for c in range(nc)],
                   reverse=True)
    print(f"  Top sizes: {[s for s, _ in sizes[:10]]}", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_walk_mk': bank_walk[0] if bank_walk else None,
        'lkh_walk_mk': lkh_mk, 'lkh_feas': lkh_feas, 'lkh_exc': lkh_exc,
        'lkh_perm': lkh_perm,
        'pair_sharing': {
            'bank_pairs': len(bank_pairs),
            'lkh_pairs': len(lkh_pairs),
            'shared': len(shared),
            'bank_in_fine': bank_in_fine,
            'lkh_in_fine': lkh_in_fine,
        },
        'random_shuffle_walk_feas_rate': n_feas / n_trials,
        'random_shuffle_mks': feas_mks,
        'bank_mut_walk_feas_rate': n_bank_mut_feas / n_trials,
        'bank_mut_mks': bank_mut_mks,
        'cheap_components': len(sizes),
        'comp_sizes_top10': [s for s, _ in sizes[:10]],
    }))
    print(f"\nResult saved to {RESULT}", flush=True)


if __name__ == '__main__':
    main()
