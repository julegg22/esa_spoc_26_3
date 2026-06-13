"""E-551 — Ch2 medium: instrument WHY DP rejects 96% of M5/M2/M1 mutations.

E-549 ran 11800 iters/chain with DP_ok=4% and 0 accepts. Methodology
trigger (CLAUDE.md 5a): solver rejects >30% of candidates → instrument
the silent reject paths before proposing new levers.

Hypothesis: mutated perms create adjacent pairs absent from the curated
4686-pair fine table (E-542 precomputed only bank-perm-derived pairs),
so the DP sees an all-INF leg and rejects regardless of schedule quality.

Classification per rejected candidate:
  missing_pair   — ≥1 leg whose (i,j) has NO finite entry in cheap or exc
  dp_unreachable — all legs have entries but no path through the table
  fitness_reject — DP found a path but kt.fitness/is_feasible rejects
  ok             — accepted, record mk

Output: per-operator reason counts, #missing-legs distribution, the
aggregate set of missing pairs (= targeted precompute shopping list).
"""
from __future__ import annotations
import sys, json, random
from collections import Counter
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP
from ch2_dp_numba import dp_evaluate_numba, reconstruct_actual_schedule

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
FINE = sys.argv[1] if len(sys.argv) > 1 else '/tmp/ch2_medium_fine_pair_set.npz'
COARSE = '/tmp/ch2_medium_tcoupled.npz'
RESULT = sys.argv[2] if len(sys.argv) > 2 else '/tmp/ch2_e551_reject_instrument.json'
N_TRIALS = 200


def get_components(coarse_path):
    d = np.load(coarse_path)
    cheap = d['cheap']
    cheap_min = np.nanmin(cheap, axis=2)
    n = cheap_min.shape[0]
    np.fill_diagonal(cheap_min, np.inf)
    adj_sym = np.isfinite(cheap_min) | np.isfinite(cheap_min.T)
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym), directed=False)
    sizes = sorted([(int((lbl == c).sum()), c) for c in range(nc)], reverse=True)
    comp_rank = {sizes[r][1]: r for r in range(nc)}
    return {i: comp_rank[int(lbl[i])] for i in range(n)}


def main():
    kt = KTTSP(INST); n = kt.n
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    # pair (i,j) is "in table" iff any finite entry in either row
    pair_has = (np.isfinite(cheap_tab).any(axis=2) |
                np.isfinite(exc_tab).any(axis=2))
    print(f"E-551 reject instrumentation. n={n} T={T} q={q}", flush=True)
    print(f"  pairs in fine table: {int(pair_has.sum())}/{n*(n-1)}", flush=True)

    node_comp = get_components(COARSE)
    comp_nodes = {c: [i for i in range(n) if node_comp[i] == c]
                  for c in set(node_comp.values())}

    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    times = list(dv[:n-1]); tofs_b = list(dv[n-1:2*(n-1)])
    bank_mk = float(kt.fitness(dv)[0])
    print(f"  bank mk={bank_mk:.4f}d", flush=True)

    bridge_positions = []
    for k in range(n - 1):
        i, j = perm[k], perm[k+1]
        dv_k = float(kt.compute_transfer(i, j, times[k], tofs_b[k]))
        if dv_k > 100.001 and node_comp[i] != node_comp[j]:
            bridge_positions.append(k)
    print(f"  bridge positions: {bridge_positions}", flush=True)

    # ── operators (identical to E-549) ─────────────────────────────
    def m5(p0, rng):
        p = list(p0)
        for _ in range(rng.randint(1, 3)):
            if not bridge_positions: break
            k = rng.choice(bridge_positions)
            tc = node_comp[p[k]]
            cand = [m for m in range(1, n-1)
                    if m != k and node_comp[p[m]] == tc]
            if not cand: continue
            m = rng.choice(cand)
            p[k], p[m] = p[m], p[k]
        return p

    def m2(p0, rng):
        p = list(p0)
        for _ in range(rng.randint(2, 5)):
            for _ in range(20):
                i = rng.randint(1, n-4)
                L = rng.randint(3, 12)
                j = min(i + L, n - 2)
                if all(node_comp[p[k]] == node_comp[p[i]]
                       for k in range(i, j+1)):
                    p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                    break
        return p

    def m1(p0, rng):
        p = list(p0)
        for _ in range(rng.randint(3, 8)):
            c = rng.choice(list(comp_nodes.keys()))
            same = [k for k in range(1, n-1) if node_comp[p[k]] == c]
            if len(same) < 2: continue
            i, j = rng.sample(same, 2)
            p[i], p[j] = p[j], p[i]
        return p

    def m_rand(p0, rng):
        p = list(p0)
        for _ in range(rng.randint(2, 5)):
            i = rng.randint(1, n-2); j = rng.randint(1, n-2)
            if i != j: p[i], p[j] = p[j], p[i]
        return p

    def classify(p):
        missing = [(p[k], p[k+1]) for k in range(n-1)
                   if not pair_has[p[k], p[k+1]]]
        if missing:
            return 'missing_pair', missing, None
        res = dp_evaluate_numba(p, cheap_tab, exc_tab, q, T, kt.n_exc)
        if res[0] is None:
            return 'dp_unreachable', [], None
        min_t, e_used, legs = res[0]
        _, c_tof, e_tof = res
        ts, tfs = reconstruct_actual_schedule(legs, c_tof, e_tof, q)
        fit = kt.fitness(list(ts) + list(tfs) + [float(x) for x in p])
        if not kt.is_feasible(fit):
            return 'fitness_reject', [], None
        return 'ok', [], float(fit[0])

    all_missing = Counter()
    summary = {}
    for name, op in [('M5', m5), ('M2', m2), ('M1', m1), ('random', m_rand)]:
        rng = random.Random(42)
        reasons = Counter(); n_missing_legs = []; mks = []
        for _ in range(N_TRIALS):
            p = op(perm, rng)
            if len(set(p)) != n:
                reasons['degenerate'] += 1; continue
            reason, missing, mk = classify(p)
            reasons[reason] += 1
            if missing:
                n_missing_legs.append(len(missing))
                for pr in missing: all_missing[pr] += 1
            if mk is not None: mks.append(mk)
        summary[name] = {
            'reasons': dict(reasons),
            'missing_legs_per_cand': {
                'mean': float(np.mean(n_missing_legs)) if n_missing_legs else 0,
                'max': int(max(n_missing_legs)) if n_missing_legs else 0},
            'ok_mks': {'n': len(mks),
                       'min': min(mks) if mks else None,
                       'n_below_bank': sum(1 for m in mks if m < bank_mk)},
        }
        print(f"  {name:7s} {dict(reasons)}  "
              f"missing_legs mean={summary[name]['missing_legs_per_cand']['mean']:.1f} "
              f"ok_min={min(mks) if mks else None}", flush=True)

    uniq = len(all_missing)
    intra = sum(1 for (i, j) in all_missing if node_comp[i] == node_comp[j])
    print(f"\nUnique missing pairs across all rejects: {uniq} "
          f"({intra} intra-comp, {uniq-intra} inter-comp)", flush=True)
    print(f"Top 20 most-hit missing pairs: "
          f"{all_missing.most_common(20)}", flush=True)
    # Size of the "expand to all intra-comp pairs" option
    n_intra_all = sum(len(v) * (len(v) - 1) for v in comp_nodes.values())
    n_intra_have = int(sum(pair_has[i, j]
                           for c, v in comp_nodes.items()
                           for i in v for j in v if i != j))
    print(f"All-intra-comp directed pairs: {n_intra_all}, "
          f"already in table: {n_intra_have}, "
          f"to add: {n_intra_all - n_intra_have}", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_mk': bank_mk,
        'pairs_in_table': int(pair_has.sum()),
        'per_op': summary,
        'unique_missing_pairs': uniq,
        'missing_intra': intra,
        'intra_all': n_intra_all,
        'intra_have': n_intra_have,
        'top_missing': [[list(p), c] for p, c in all_missing.most_common(200)],
    }))
    print(f"\nSaved {RESULT}", flush=True)


if __name__ == '__main__':
    main()
