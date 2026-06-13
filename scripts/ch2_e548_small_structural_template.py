"""E-548 — Ch2 small: bank structural template + safe-mutation classes.

Sister analysis to E-547 (medium). Identifies small's bank structural
template and tests mutation classes that preserve walk-feasibility.

Same M1-M5 mutation classes (intra-comp swap, intra-comp segment reverse,
intra-comp or-opt, exc-preserving 2-opt, bridge-node swap) + Control.

Small known structure (per audit + experiments):
  Components: [40, 3, 3, 3]
  comp 0 = 40 nodes; comp 1 = {4,11,17}; comp 2 = {16,27,32}; comp 3 = {18,23,34}
  Bank starts at 34 (comp3), ends at 32 (comp2)
  5 exc legs: 4 inter + 1 intra-comp (per audit)
"""
from __future__ import annotations
import sys, json, time, random
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
ULTRAFINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
RESULT = '/tmp/ch2_e548_template.json'


def walk_eval(kt, perm):
    try:
        ts, tofs, dvs, ok, exc_n, _ = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception:
        return None, False, 0
    if not ok:
        return None, False, exc_n
    mk = ts[-1] + tofs[-1]
    return mk, True, exc_n


def get_components(fine_path):
    d = np.load(fine_path)
    cheap = d['cheap']
    cheap_min = np.nanmin(cheap, axis=2)
    n = cheap_min.shape[0]
    np.fill_diagonal(cheap_min, np.inf)
    adj_sym = np.isfinite(cheap_min) | np.isfinite(cheap_min.T)
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym),
                                        directed=False)
    return lbl, nc


def main():
    kt = KTTSP(INST); n = kt.n
    print(f"E-548 small structural template. n={n}", flush=True)

    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    times = list(dv[:n-1]); tofs_b = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    print(f"Bank: start={perm[0]} end={perm[-1]} mk={bank_mk:.4f}d (DP)",
          flush=True)

    print("\n=== Components ===", flush=True)
    labels, n_comps = get_components(ULTRAFINE)
    sizes = [(int((labels == c).sum()), c) for c in range(n_comps)]
    sizes.sort(reverse=True)
    comp_rank = {sizes[r][1]: r for r in range(n_comps)}
    node_comp = {i: comp_rank[int(labels[i])] for i in range(n)}
    print(f"  {n_comps} comps, sizes: {[s for s, _ in sizes]}",
          flush=True)
    comp_nodes = {r: [i for i in range(n) if node_comp[i] == r]
                  for r in range(n_comps)}
    print(f"  comp 0 (big, {len(comp_nodes[0])}): "
          f"{comp_nodes[0][:10]}...", flush=True)
    for r in range(1, n_comps):
        print(f"  comp {r} ({len(comp_nodes[r])}): {comp_nodes[r]}",
              flush=True)

    print("\n=== Bank perm structure ===", flush=True)
    bank_comp_seq = [node_comp[v] for v in perm]
    compressed = []
    last = None
    for c in bank_comp_seq:
        if c != last:
            compressed.append(c); last = c
    print(f"  comp visit sequence (compressed): {compressed}", flush=True)
    switches = [k for k in range(1, n) if bank_comp_seq[k] != bank_comp_seq[k-1]]
    print(f"  # comp-switches: {len(switches)} (K-1 = {n_comps-1})",
          flush=True)

    exc_legs = []
    cheap_legs = []
    for k in range(n - 1):
        i, j = perm[k], perm[k+1]
        dv_k = kt.compute_transfer(i, j, times[k], tofs_b[k])
        is_inter = node_comp[i] != node_comp[j]
        if dv_k > 100.001:
            exc_legs.append((k, i, j, dv_k, is_inter))
        else:
            cheap_legs.append((k, i, j, dv_k, is_inter))
    print(f"  cheap legs: {len(cheap_legs)}, exc legs: {len(exc_legs)}",
          flush=True)
    n_inter_cheap = sum(1 for _, _, _, _, inter in cheap_legs if inter)
    n_intra_cheap = sum(1 for _, _, _, _, inter in cheap_legs if not inter)
    print(f"    cheap: {n_inter_cheap} inter, {n_intra_cheap} intra",
          flush=True)
    print(f"  Exception legs:", flush=True)
    for k, i, j, dv_k, inter in exc_legs:
        print(f"    leg {k:2d}: {i:2d}(c{node_comp[i]}) → {j:2d}(c{node_comp[j]})  "
              f"dv={dv_k:.1f}  {'INTER' if inter else 'intra'}",
              flush=True)
    exc_positions = set(k for k, _, _, _, _ in exc_legs)

    print("\n=== Mutation classes — walk-feasibility test ===", flush=True)
    N_TRIALS = 100

    def test_mutation(name, mutator):
        n_feas = 0; mks = []
        rng_local = random.Random(42)
        t0 = time.time()
        for _ in range(N_TRIALS):
            p = mutator(rng_local)
            if p is None or len(set(p)) != n: continue
            mk, ok, _ = walk_eval(kt, p)
            if ok and mk is not None:
                n_feas += 1
                mks.append(mk)
        wall = time.time() - t0
        info = f"  {name:35s} {n_feas:3d}/{N_TRIALS} feasible "
        if mks:
            info += (f"mk_range=[{min(mks):.1f}, {max(mks):.1f}] "
                     f"median={np.median(mks):.1f} "
                     f"n_below_bank={sum(1 for m in mks if m < bank_mk)}")
        info += f"  ({wall:.0f}s)"
        print(info, flush=True)
        return {'n_feas': n_feas, 'mks': mks}

    results = {}

    def m_control(rng_):
        p = list(perm)
        for _ in range(rng_.randint(3, 10)):
            i = rng_.randint(1, n-2); j = rng_.randint(1, n-2)
            if i != j: p[i], p[j] = p[j], p[i]
        return p

    def m_intra_swap(rng_):
        p = list(perm)
        for _ in range(rng_.randint(3, 10)):
            c = rng_.choice(list(comp_nodes.keys()))
            same_comp_pos = [k for k in range(n) if node_comp[p[k]] == c]
            if len(same_comp_pos) < 2: continue
            i, j = rng_.sample(same_comp_pos, 2)
            p[i], p[j] = p[j], p[i]
        return p

    def m_intra_seg_rev(rng_):
        p = list(perm)
        for _ in range(rng_.randint(2, 5)):
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(2, 6)
                j = min(i + L, n - 2)
                if all(node_comp[p[k]] == node_comp[p[i]]
                       for k in range(i, j+1)):
                    p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                    break
        return p

    def m_intra_or_opt(rng_):
        p = list(perm)
        for _ in range(rng_.randint(2, 5)):
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(1, 3)
                if i + L >= n - 1: continue
                if not all(node_comp[p[k]] == node_comp[p[i]]
                           for k in range(i, i+L)): continue
                seg = p[i:i+L]
                rest = p[:i] + p[i+L:]
                same_pos = [k for k in range(1, len(rest))
                            if k > 0 and k < len(rest)
                            and node_comp[rest[k]] == node_comp[seg[0]]]
                if not same_pos: continue
                pos = rng_.choice(same_pos)
                p = rest[:pos] + seg + rest[pos:]
                break
        return p

    def m_exc_preserve(rng_):
        p = list(perm)
        for _ in range(rng_.randint(2, 5)):
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(2, 8)
                j = min(i + L, n - 2)
                if any(k in exc_positions for k in range(i-1, j+1)):
                    continue
                p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                break
        return p

    def m_bridge_swap(rng_):
        p = list(perm)
        inter_exc = [(k, i, j) for k, i, j, dv_k, inter in exc_legs if inter]
        if not inter_exc: return p
        for _ in range(rng_.randint(1, 2)):
            k, _, _ = rng_.choice(inter_exc)
            target_comp = node_comp[p[k]]
            candidates = [m for m in range(1, n-1)
                          if m != k and node_comp[p[m]] == target_comp]
            if not candidates: continue
            m = rng_.choice(candidates)
            p[k], p[m] = p[m], p[k]
        return p

    results['control'] = test_mutation("CONTROL (random swap)", m_control)
    results['M1_intra_swap'] = test_mutation("M1 intra-comp swap", m_intra_swap)
    results['M2_intra_seg_rev'] = test_mutation("M2 intra-comp seg-reverse", m_intra_seg_rev)
    results['M3_intra_or_opt'] = test_mutation("M3 intra-comp or-opt", m_intra_or_opt)
    results['M4_exc_preserve'] = test_mutation("M4 exc-preserving 2-opt", m_exc_preserve)
    results['M5_bridge_swap'] = test_mutation("M5 bridge-node swap", m_bridge_swap)

    print("\n=== Summary ===", flush=True)
    n_below_bank = sum(1 for k, v in results.items()
                       for m in v['mks'] if m < bank_mk)
    print(f"  Total perms found BELOW bank's DP-mk ({bank_mk:.1f}d): "
          f"{n_below_bank}", flush=True)
    print(f"  (Note: walk_perm_chrono mk is GREATER than DP mk; ",
          f"any walk-feasible perm rescored by DP will be smaller)",
          flush=True)

    save_results = {}
    for k, v in results.items():
        save_results[k] = {'n_feas': v['n_feas'], 'mks': v['mks']}
    Path(RESULT).write_text(json.dumps({
        'bank_dp_mk': bank_mk,
        'component_sizes': [s for s, _ in sizes],
        'comp_visit_compressed': compressed,
        'n_inter_cheap': n_inter_cheap,
        'n_intra_cheap': n_intra_cheap,
        'n_exc_legs': len(exc_legs),
        'exc_positions': sorted(exc_positions),
        'mutation_tests': save_results,
    }))
    print(f"\nResults saved to {RESULT}", flush=True)


if __name__ == '__main__':
    main()
