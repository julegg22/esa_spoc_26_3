"""E-530 — Ch2 small: cluster-aware DP-ALNS with diverse chain seeding.

Continuation of E-529 (which plateaued at 116.38 d). Two changes:
  (a) Cluster-aware destroy operators that target whole cheap-graph
      components or large contiguous segments of comp0 (length 8-15).
      E-529's operators (k≤5 nodes) saturated; the trapped state
      needs larger structural perturbation.
  (b) Diverse chain seeding: each chain seeded from a DIFFERENT
      checkpoint perm from E-529, instead of all from the same bank.
      Explores 6 basins simultaneously.

Uses the same numba-JIT'd DP evaluator from ch2_dp_numba.py and the
same ultrafine table (/tmp/ch2_small_tcoupled_ultrafine.npz).

Targets: ~48h budget. ALNS continues until R3 (111.76 d) or time-out.
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

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260606.e530"
FINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
CKPT_TMPL = '/tmp/ch2_e530_ckpt_chain{}.json'

# Seeds: chain 0 = current bank, chains 1-5 = E-529 chain checkpoints
SEED_PATHS = [
    None,  # chain 0 uses OUT
    '/tmp/ch2_e529_ckpt_chain1.json',
    '/tmp/ch2_e529_ckpt_chain2.json',
    '/tmp/ch2_e529_ckpt_chain3.json',
    '/tmp/ch2_e529_ckpt_chain4.json',
    '/tmp/ch2_e529_ckpt_chain5.json',
]

# Verified cheap-edge components
COMP_NODES = {
    0: None,  # big comp - computed at runtime
    1: [4, 11, 17],
    2: [16, 27, 32],
    3: [18, 23, 34],
}
SMALL_COMP_NODES = [4, 11, 17, 16, 27, 32, 18, 23, 34]

SA_T0 = 8.0          # higher than E-529's 5.0 — more exploration
SA_DECAY = 0.9995
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 6 * 3600


# ── Destroy operators (cluster-aware + larger radius) ───────────────
def destroy_segment_reverse(perm, rng, max_len=6):
    """E-529's segment_reverse with bounded length (small only)."""
    n = len(perm)
    if n < 6: return list(perm)
    i = rng.randint(1, n-4); j = min(rng.randint(i+2, n-2), i + max_len)
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]


def destroy_segment_reverse_large(perm, rng, min_len=8, max_len=15):
    """Reverse a large segment (8-15 nodes) of perm — typically inside
    comp0 since small comps are 3-node blocks."""
    n = len(perm)
    if n < min_len + 4: return list(perm)
    L = rng.randint(min_len, max_len)
    i = rng.randint(1, n - L - 2)
    j = i + L
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]


def destroy_segment_shuffle_large(perm, rng, min_len=8, max_len=15):
    """Shuffle (random reorder) a large segment of perm."""
    n = len(perm)
    if n < min_len + 4: return list(perm)
    L = rng.randint(min_len, max_len)
    i = rng.randint(1, n - L - 2)
    seg = list(perm[i:i+L])
    rng.shuffle(seg)
    return perm[:i] + seg + perm[i+L:]


def destroy_small_comp_shuffle(perm, rng):
    """Shuffle the order of one small comp's 3 nodes in-place
    (preserve their positions, randomize their values)."""
    n = len(perm)
    # Pick which small comp to shuffle
    cid = rng.choice([1, 2, 3])
    nodes = COMP_NODES[cid]
    # Find their positions in perm
    positions = sorted(i for i, v in enumerate(perm) if v in nodes)
    if len(positions) != 3: return list(perm)
    shuffled = list(nodes); rng.shuffle(shuffled)
    p = list(perm)
    for pi, sv in zip(positions, shuffled):
        p[pi] = sv
    return p


def destroy_swap(perm, rng):
    n = len(perm)
    if n < 4: return list(perm)
    i = rng.randint(1, n-2); j = rng.randint(1, n-2)
    while j == i: j = rng.randint(1, n-2)
    p = list(perm); p[i], p[j] = p[j], p[i]
    return p


def destroy_random_k_insert(perm, k, rng):
    """Remove k random nodes, reinsert at random positions."""
    n = len(perm)
    indices = rng.sample(range(1, n-1), min(k, n-2))
    removed = [perm[i] for i in indices]
    kept = [perm[i] for i in range(n) if i not in set(indices)]
    rng.shuffle(removed)
    for node in removed:
        pos = rng.randint(1, len(kept))
        kept = kept[:pos] + [node] + kept[pos:]
    return kept


def destroy_double_bridge(perm, rng):
    n = len(perm)
    if n < 9: return list(perm)
    cuts = sorted(rng.sample(range(1, n-1), 3))
    a, b, c = cuts
    return perm[:a] + perm[c:n-1] + perm[b:c] + perm[a:b] + perm[n-1:]


def mutate(perm, rng):
    """Choose a destroy operator with weighted random."""
    op = rng.choices(
        ['seg_rev_small', 'seg_rev_large', 'seg_shuf_large',
         'small_comp_shuf', 'swap', 'random_k', 'double_bridge'],
        weights=[2, 3, 3, 2, 1, 2, 2])[0]
    if op == 'seg_rev_small':
        return destroy_segment_reverse(perm, rng), op
    elif op == 'seg_rev_large':
        return destroy_segment_reverse_large(perm, rng), op
    elif op == 'seg_shuf_large':
        return destroy_segment_shuffle_large(perm, rng), op
    elif op == 'small_comp_shuf':
        return destroy_small_comp_shuffle(perm, rng), op
    elif op == 'swap':
        return destroy_swap(perm, rng), op
    elif op == 'random_k':
        k = rng.randint(5, 10)
        return destroy_random_k_insert(perm, k, rng), op
    else:
        return destroy_double_bridge(perm, rng), op


# ── ALNS chain ──────────────────────────────────────────────────────
def alns_chain(args):
    chain_id, max_wall_s, bank_path, seed_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 9091 + 17)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    # Load ultrafine table
    log("loading ultrafine table...")
    t_load = time.time()
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    log(f"table loaded in {time.time()-t_load:.1f}s")

    # Load seed perm
    if seed_path is None:
        # Seed from current bank
        bank = json.load(open(bank_path))
        dv = bank[0]['decisionVector']
        seed_perm = [int(x) for x in dv[2*(n-1):]]
        seed_mk = float(kt.fitness(dv)[0])
        log(f"seeded from bank: mk={seed_mk:.4f}d")
    else:
        ck = json.load(open(seed_path))
        seed_perm = [int(x) for x in ck['perm']]
        seed_mk = float(ck['mk'])
        log(f"seeded from {Path(seed_path).name}: mk={seed_mk:.4f}d")

    # DP-evaluate the seed to get the actual schedule on ultrafine
    seed_res = evaluate_perm_dp_numba(kt, seed_perm, cheap_tab, exc_tab, q, T)
    if seed_res is None:
        log(f"WARN: seed perm DP-infeasible; falling back to bank")
        bank = json.load(open(bank_path))
        dv = bank[0]['decisionVector']
        seed_perm = [int(x) for x in dv[2*(n-1):]]
        seed_res = evaluate_perm_dp_numba(kt, seed_perm, cheap_tab, exc_tab, q, T)
    state = {'perm': seed_perm, 'mk': seed_res['mk'],
             'times': seed_res['times'], 'tofs': seed_res['tofs']}
    best_local = dict(state)
    log(f"state initialized mk={state['mk']:.4f}d")

    # Resume from E-530 ckpt if exists
    ckpt = CKPT_TMPL.format(chain_id)
    if Path(ckpt).exists():
        try:
            ck = json.load(open(ckpt))
            if ck['perm'] and len(ck['perm']) == n:
                state = ck
                if ck['mk'] < best_local['mk']: best_local = dict(state)
                log(f"resumed e530 ckpt mk={state['mk']:.4f}d")
        except Exception: pass

    sa_temp = SA_T0
    iter_count = 0; n_dp_ok = 0; n_dp_fail = 0; n_accepted = 0
    op_counts = {}; op_accepts = {}
    t0 = time.time(); last_ckpt = time.time(); last_reseed = time.time()
    hist_fh = open(f'/tmp/ch2_e530_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        new_perm, op = mutate(state['perm'], rng)
        op_counts[op] = op_counts.get(op, 0) + 1
        if len(set(new_perm)) != n: continue

        t_eval = time.time()
        result = evaluate_perm_dp_numba(kt, new_perm, cheap_tab, exc_tab, q, T)
        if result is None:
            n_dp_fail += 1
            continue
        n_dp_ok += 1
        new_mk = result['mk']

        delta = new_mk - state['mk']
        accept = delta < 0 or rng.random() < math.exp(-delta / sa_temp)
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
                # Bank globally if better
                try:
                    cur = json.load(open(bank_path))
                    cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
                    if new_mk < cur_mk - 1e-4:
                        x_full = list(result['times']) + list(result['tofs']) + \
                                  [float(p) for p in new_perm]
                        bp = bank_path + ".bak.e530"
                        if not Path(bp).exists():
                            Path(bp).write_bytes(Path(bank_path).read_bytes())
                        tmp = bank_path + '.tmp'
                        Path(tmp).write_text(json.dumps([{
                            'decisionVector': x_full, 'problem': 'small',
                            'challenge': CHALLENGE,
                        }]))
                        os.replace(tmp, bank_path)
                        log(f"BANKED {new_mk:.4f}d (was {cur_mk:.4f}) "
                            f"op={op} iter={iter_count}")
                except Exception as e:
                    log(f"bank err: {str(e)[:60]}")

        sa_temp *= SA_DECAY

        if iter_count % 50 == 0:
            elapsed = time.time() - t0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"DP_ok={n_dp_ok} DP_fail={n_dp_fail} accepted={n_accepted} "
                f"state={state['mk']:.4f} best={best_local['mk']:.4f} "
                f"T={sa_temp:.3f}")

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
                if cur_mk < state['mk'] - 0.1:
                    dv2 = cur[0]['decisionVector']
                    state = {
                        'perm': [int(x) for x in dv2[2*(n-1):]],
                        'times': list(dv2[:n-1]),
                        'tofs': list(dv2[n-1:2*(n-1)]),
                        'mk': cur_mk,
                    }
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


def main(wall_h=48):
    if not Path(FINE).exists():
        print(f"ERR ultrafine table missing"); return
    print(f"E-530 cluster-aware DP-ALNS. n_chains=6 wall_h={wall_h}",
          flush=True)
    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    args = [(i, wall_h * 3600, OUT, SEED_PATHS[i]) for i in range(6)]
    with mp.Pool(6) as pool:
        results = pool.map(alns_chain, args)
    print(f"\nAll chains done.", flush=True)
    for ci, best in results:
        print(f"  chain {ci}: best={best['mk']:.4f}d", flush=True)


if __name__ == '__main__':
    wh = float(sys.argv[1]) if len(sys.argv) > 1 else 48.0
    main(wall_h=wh)
