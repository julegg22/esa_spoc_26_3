"""E-554 — Ch2 medium: E-549 DP-ALNS rerun on the EXPANDED v2 fine table.

E-549 stalled at DP_ok=4%: E-551 instrumentation showed missing_pair
dominates every operator (the curated 4686-pair table starved the
mutations). E-552 expands the table with all intra-comp directed pairs
(+observed inter-comp missing pairs) → M1/M2 become table-complete and
M5 nearly so. Identical architecture to E-549 otherwise (DP metric for
both SA baseline and candidates — consistent by construction).

Run AFTER /tmp/ch2_medium_fine_pair_set_v2.npz exists.
"""
from __future__ import annotations
import sys, os, json, time, random, math
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ch2_dp_numba import evaluate_perm_dp_numba
from ch2_e549_medium_structure_alns import (
    get_components, identify_bank_bridges,
    m5_bridge_swap, m2_intra_seg_rev, m1_intra_swap, m_random_swap)

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
BAK = OUT + ".bak.e554"
FINE = '/tmp/ch2_medium_fine_pair_set_v2.npz'
COARSE = '/tmp/ch2_medium_tcoupled.npz'
CKPT_TMPL = '/tmp/ch2_e554_ckpt_chain{}.json'

# T0 raised 3.0->10.0 (E-554 v1 froze: accepted=0 over 400 iters/chain). Recheck
# showed the bank's best feasible neighbor is +11.4d uphill (ok_min 240.35 vs bank
# 228.97); exp(-11.4/3)=2.4% was effectively frozen. T0=10 gives exp(-11.4/10)=32%
# accept on the min step; decay 0.9999 over ~12k iters/24h anneals T 10->~3 (explore
# early, exploit late). delta_min is measured, not guessed.
SA_T0 = 10.0
SA_DECAY = 0.9999
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 6 * 3600


def alns_chain(args):
    chain_id, max_wall_s, bank_path, node_comp, comp_nodes, bridge_positions = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 9907 + 71)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    log("loading v2 fine pair-set table...")
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    log(f"table loaded (n={cheap_tab.shape[0]}, T={T}, "
        f"pairs={len(d['pair_set'])})")

    bank = json.load(open(bank_path))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    state = {'perm': perm, 'mk': bank_mk,
             'times': list(dv[:n-1]), 'tofs': list(dv[n-1:2*(n-1)])}
    best_local = dict(state)
    log(f"init bank mk={bank_mk:.4f}d")

    ckpt = CKPT_TMPL.format(chain_id)
    if Path(ckpt).exists():
        try:
            ck = json.load(open(ckpt))
            if ck['perm'] and len(ck['perm']) == n:
                state = ck
                if ck['mk'] < best_local['mk']: best_local = dict(state)
                log(f"resumed ckpt mk={state['mk']:.4f}d")
        except Exception: pass

    sa_temp = SA_T0
    iter_count = 0; n_dp_ok = 0; n_dp_fail = 0; n_accepted = 0
    op_counts = {}; op_accepts = {}
    t0 = time.time(); last_ckpt = time.time(); last_reseed = time.time()
    hist_fh = open(f'/tmp/ch2_e554_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        sa_temp *= SA_DECAY

        op = rng.choices(
            ['M5_bridge', 'M2_seg_rev', 'M1_intra_swap', 'random'],
            weights=[60, 20, 15, 5])[0]
        op_counts[op] = op_counts.get(op, 0) + 1
        if op == 'M5_bridge':
            new_perm = m5_bridge_swap(state['perm'], node_comp,
                                       bridge_positions, rng)
        elif op == 'M2_seg_rev':
            new_perm = m2_intra_seg_rev(state['perm'], node_comp, rng)
        elif op == 'M1_intra_swap':
            new_perm = m1_intra_swap(state['perm'], node_comp,
                                       comp_nodes, rng)
        else:
            new_perm = m_random_swap(state['perm'], rng)
        if len(set(new_perm)) != n: continue

        result = evaluate_perm_dp_numba(kt, new_perm, cheap_tab, exc_tab, q, T)
        if result is None:
            n_dp_fail += 1
            continue
        n_dp_ok += 1
        new_mk = result['mk']

        delta = new_mk - state['mk']
        accept = delta < 0 or rng.random() < math.exp(-delta / max(sa_temp, 1e-6))
        if accept:
            n_accepted += 1
            op_accepts[op] = op_accepts.get(op, 0) + 1
            state = {'perm': new_perm, 'mk': new_mk,
                     'times': result['times'], 'tofs': result['tofs']}
            if new_mk < best_local['mk']:
                best_local = dict(state)
                hist_fh.write(json.dumps({
                    'chain': chain_id, 'iter': iter_count, 'mk': new_mk,
                    'op': op, 'elapsed_s': time.time() - t0,
                }) + '\n')
                hist_fh.flush()
                try:
                    cur = json.load(open(bank_path))
                    cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
                    if new_mk < cur_mk - 1e-4:
                        x_full = list(result['times']) + list(result['tofs']) + \
                                  [float(p) for p in new_perm]
                        if not Path(BAK).exists():
                            Path(BAK).write_bytes(Path(bank_path).read_bytes())
                        tmp = bank_path + '.tmp'
                        Path(tmp).write_text(json.dumps([{
                            'decisionVector': x_full, 'problem': 'medium',
                            'challenge': CHALLENGE,
                        }]))
                        os.replace(tmp, bank_path)
                        log(f"BANKED {new_mk:.4f}d (was {cur_mk:.4f}) "
                            f"op={op} iter={iter_count}")
                except Exception as e:
                    log(f"bank err: {str(e)[:60]}")

        if iter_count % 200 == 0:
            elapsed = time.time() - t0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"DP_ok={n_dp_ok} ({n_dp_ok/iter_count*100:.1f}%) "
                f"accepted={n_accepted} state={state['mk']:.4f} "
                f"best={best_local['mk']:.4f} T={sa_temp:.3f}")

        if time.time() - last_ckpt > CKPT_INTERVAL_S:
            try:
                json.dump({'perm': state['perm'], 'times': state['times'],
                           'tofs': state['tofs'], 'mk': state['mk'],
                           'best_mk': best_local['mk'], 'iter': iter_count,
                           'op_counts': op_counts, 'op_accepts': op_accepts},
                          open(ckpt, 'w'))
            except Exception: pass
            last_ckpt = time.time()

        if time.time() - last_reseed > RESEED_INTERVAL_S:
            try:
                cur = json.load(open(bank_path))
                cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
                if cur_mk < best_local['mk'] - 0.1:
                    dv2 = cur[0]['decisionVector']
                    state = {
                        'perm': [int(x) for x in dv2[2*(n-1):]],
                        'times': list(dv2[:n-1]),
                        'tofs': list(dv2[n-1:2*(n-1)]),
                        'mk': cur_mk,
                    }
                    best_local = dict(state)
                    sa_temp = SA_T0
                    log(f"reseeded from global mk={cur_mk:.4f}")
            except Exception: pass
            last_reseed = time.time()

    hist_fh.close()
    log(f"chain done. iters={iter_count} best={best_local['mk']:.4f}d")
    log(f"  op acceptance rates:")
    for op in op_counts:
        ac = op_accepts.get(op, 0); ct = op_counts[op]
        log(f"    {op}: {ac}/{ct} ({ac/max(ct,1)*100:.1f}%)")
    return chain_id, best_local


def main(n_chains: int = 4, wall_h: float = 24.0):
    if not Path(FINE).exists():
        print(f"ERR v2 fine pair-set missing ({FINE}) — run E-552 first")
        return
    if not Path(COARSE).exists():
        print(f"ERR coarse table missing"); return
    print(f"E-554 medium DP-ALNS on v2 table. n_chains={n_chains} "
          f"wall_h={wall_h}", flush=True)

    kt = KTTSP(INST); n = kt.n
    print(f"Loading structure (components + bridges)...", flush=True)
    node_comp = get_components(COARSE)
    comp_nodes = {c: [i for i in range(n) if node_comp[i] == c]
                  for c in set(node_comp.values())}
    sizes = sorted([len(v) for v in comp_nodes.values()], reverse=True)
    print(f"  components: {sizes}", flush=True)

    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    times = list(dv[:n-1]); tofs_b = list(dv[n-1:2*(n-1)])
    bridge_positions = identify_bank_bridges(kt, perm, times, tofs_b, node_comp)
    print(f"  bridge positions (bank's exc-inter legs): {bridge_positions}",
          flush=True)

    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    args = [(i, wall_h * 3600, OUT, node_comp, comp_nodes, bridge_positions)
            for i in range(n_chains)]
    with mp.Pool(n_chains) as pool:
        results = pool.map(alns_chain, args)
    print(f"\nAll chains done.", flush=True)
    for ci, best in results:
        print(f"  chain {ci}: best={best['mk']:.4f}d", flush=True)


if __name__ == '__main__':
    n_ch = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    main(n_chains=n_ch, wall_h=wh)
