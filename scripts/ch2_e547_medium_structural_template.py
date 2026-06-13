"""E-547 — Ch2 medium: bank structural template + safe-mutation classes.

E-546 revealed medium's feasibility is a knife-edge: even 5-20 random
swaps of bank give 100% walk-infeasibility. This script analyzes bank's
structural template to understand what makes it walk-feasible, and
identifies mutation classes that preserve the template.

Analysis:
  1. Component assignment per node from cheap-edge graph (4 comps:
     [121, 20, 20, 20]).
  2. Per-leg classification in bank perm:
     - is_exc (dv > 100)
     - intra/inter component
     - Position in perm
  3. Component-visit pattern: order of comps along bank's traversal.
     Bank visits some comps multiple times via exc bridges.
  4. Exception placement: which 5 legs are exc, where they bridge to.

Mutation tests (each generates 100 candidates):
  M1 — intra-comp swap: swap two nodes within the same component.
  M2 — intra-comp segment reverse: reverse a segment lying entirely
       within one component.
  M3 — intra-comp or-opt: move 1-3 consecutive nodes within same comp.
  M4 — exc-preserving 2-opt: 2-opt segment reverse that doesn't span
       any exc leg.
  M5 — bridge-node swap: swap an inter-comp bridge node with another
       node in the same destination comp.
  Control — random swap (any positions; same as E-546's Phase 3).

Compare walk-feasibility rates and mk distributions.
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
        "problems/medium.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
COARSE = '/tmp/ch2_medium_tcoupled.npz'
RESULT = '/tmp/ch2_e547_template.json'


def walk_eval(kt, perm):
    """walk_perm_chrono → (mk, ok, exc_n). None if exception."""
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


def get_components(coarse_path):
    """Identify cheap-edge components from coarse table."""
    d = np.load(coarse_path)
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
    print(f"E-547 medium structural template. n={n}", flush=True)

    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    times = list(dv[:n-1]); tofs_b = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    print(f"Bank: start={perm[0]} end={perm[-1]} mk={bank_mk:.4f}d (DP)",
          flush=True)

    # ── Component assignment ───────────────────────────────────────
    print("\n=== Components ===", flush=True)
    labels, n_comps = get_components(COARSE)
    sizes = [(int((labels == c).sum()), c) for c in range(n_comps)]
    sizes.sort(reverse=True)
    # Map comp_id → rank (so biggest is comp_rank 0)
    comp_rank = {sizes[r][1]: r for r in range(n_comps)}
    node_comp = {i: comp_rank[int(labels[i])] for i in range(n)}
    print(f"  {n_comps} comps, sizes: {[s for s, _ in sizes]}",
          flush=True)
    # Per-comp node lists
    comp_nodes = {r: [i for i in range(n) if node_comp[i] == r]
                  for r in range(n_comps)}
    print(f"  comp 0 (big, {len(comp_nodes[0])}): "
          f"first 5 = {comp_nodes[0][:5]}...", flush=True)
    for r in range(1, n_comps):
        print(f"  comp {r} ({len(comp_nodes[r])}): {comp_nodes[r]}",
              flush=True)

    # ── Bank perm analysis ─────────────────────────────────────────
    print("\n=== Bank perm structure ===", flush=True)
    bank_comp_seq = [node_comp[v] for v in perm]
    # Identify comp-switches
    switches = [k for k in range(1, n) if bank_comp_seq[k] != bank_comp_seq[k-1]]
    print(f"  comp visit sequence (compressed): ", end="", flush=True)
    compressed = []
    last = None
    for c in bank_comp_seq:
        if c != last:
            compressed.append(c); last = c
    print(f"{compressed}", flush=True)
    print(f"  # comp-switches: {len(switches)} (= K-1 for contiguous "
          f"= {n_comps-1})", flush=True)

    # Classify each leg
    exc_legs = []  # list of (leg_idx, from_node, to_node, dv, is_inter)
    cheap_legs = []
    for k in range(n - 1):
        i, j = perm[k], perm[k+1]
        dv_k = kt.compute_transfer(i, j, times[k], tofs_b[k])
        is_inter = node_comp[i] != node_comp[j]
        if dv_k > 100.001:
            exc_legs.append((k, i, j, dv_k, is_inter))
        elif dv_k <= 100.001:
            cheap_legs.append((k, i, j, dv_k, is_inter))
    print(f"  cheap legs: {len(cheap_legs)}, exc legs: {len(exc_legs)}",
          flush=True)
    n_inter_cheap = sum(1 for _, _, _, _, inter in cheap_legs if inter)
    n_intra_cheap = sum(1 for _, _, _, _, inter in cheap_legs if not inter)
    print(f"    cheap: {n_inter_cheap} inter-comp, {n_intra_cheap} intra-comp",
          flush=True)
    print(f"  Exception legs (5):", flush=True)
    for k, i, j, dv_k, inter in exc_legs:
        print(f"    leg {k:3d}: {i:3d}(c{node_comp[i]}) → {j:3d}(c{node_comp[j]})  "
              f"dv={dv_k:.1f}  {'INTER' if inter else 'intra'}",
              flush=True)

    # Identify exc leg positions (for exc-preserving 2-opt)
    exc_positions = set(k for k, _, _, _, _ in exc_legs)
    print(f"  Exception leg positions: {sorted(exc_positions)}", flush=True)

    # ── Mutation tests ─────────────────────────────────────────────
    print("\n=== Mutation classes — walk-feasibility test ===", flush=True)
    N_TRIALS = 100
    rng = random.Random(42)

    def test_mutation(name, mutator):
        """Run 100 mutations, report walk-feasibility + mk stats."""
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
        return {'n_feas': n_feas, 'mks': mks, 'wall': wall}

    results = {}

    # Control: random swap (anywhere)
    def m_control(rng_):
        p = list(perm)
        for _ in range(rng_.randint(5, 20)):
            i = rng_.randint(1, n-2); j = rng_.randint(1, n-2)
            if i != j: p[i], p[j] = p[j], p[i]
        return p

    # M1: intra-comp swap
    def m_intra_swap(rng_):
        p = list(perm)
        for _ in range(rng_.randint(5, 20)):
            c = rng_.choice(list(comp_nodes.keys()))
            same_comp = [k for k in range(n) if node_comp[p[k]] == c]
            if len(same_comp) < 2: continue
            i, j = rng_.sample(same_comp, 2)
            p[i], p[j] = p[j], p[i]
        return p

    # M2: intra-comp segment reverse
    def m_intra_seg_rev(rng_):
        p = list(perm)
        for _ in range(rng_.randint(3, 8)):
            # Find a segment lying entirely within one comp
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(2, 10)
                j = min(i + L, n - 2)
                if all(node_comp[p[k]] == node_comp[p[i]]
                       for k in range(i, j+1)):
                    p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                    break
        return p

    # M3: intra-comp or-opt (move 1-3 nodes within comp)
    def m_intra_or_opt(rng_):
        p = list(perm)
        for _ in range(rng_.randint(3, 10)):
            # Find a segment within one comp and a destination in same comp
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(1, 3)
                if i + L >= n - 1: continue
                if not all(node_comp[p[k]] == node_comp[p[i]]
                           for k in range(i, i+L)): continue
                seg = p[i:i+L]
                rest = p[:i] + p[i+L:]
                # Find positions in same comp in rest
                same_pos = [k for k in range(1, len(rest))
                            if k > 0 and k < len(rest)
                            and node_comp[rest[k]] == node_comp[seg[0]]]
                if not same_pos: continue
                pos = rng_.choice(same_pos)
                p = rest[:pos] + seg + rest[pos:]
                break
        return p

    # M4: exc-preserving 2-opt (don't cross any exc leg)
    def m_exc_preserve(rng_):
        p = list(perm)
        for _ in range(rng_.randint(3, 8)):
            for _ in range(20):
                i = rng_.randint(1, n-4)
                L = rng_.randint(2, 15)
                j = min(i + L, n - 2)
                # Ensure no exc leg lies within [i-1, j+1]
                if any(k in exc_positions for k in range(i-1, j+1)):
                    continue
                p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                break
        return p

    # M5: bridge-node swap (swap inter-comp bridge endpoints)
    def m_bridge_swap(rng_):
        p = list(perm)
        # Identify current bridge positions (exc-inter legs)
        inter_exc = [(k, i, j) for k, i, j, dv_k, inter in exc_legs if inter]
        if not inter_exc: return p
        for _ in range(rng_.randint(1, 3)):
            k, _, _ = rng_.choice(inter_exc)
            # Swap perm[k] with another node from the same comp
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

    # ── Summary + recommendation ───────────────────────────────────
    print("\n=== Summary ===", flush=True)
    best_rate = max(results[k]['n_feas'] for k in results)
    best_name = [k for k in results if results[k]['n_feas'] == best_rate][0]
    print(f"  Highest feasibility rate: {best_name} ({best_rate}/{N_TRIALS})",
          flush=True)
    n_under_bank = sum(1 for k, v in results.items()
                       for m in v['mks'] if m < bank_mk)
    print(f"  Total perms found BELOW bank's walk-eval ({bank_mk:.1f}d): "
          f"{n_under_bank}", flush=True)

    # Save details
    save_results = {}
    for k, v in results.items():
        save_results[k] = {'n_feas': v['n_feas'], 'mks': v['mks']}
    Path(RESULT).write_text(json.dumps({
        'bank_walk_mk': None,
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
