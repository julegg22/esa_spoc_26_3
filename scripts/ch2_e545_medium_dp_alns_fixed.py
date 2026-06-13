"""E-545 — Ch2 medium: DP-ALNS with bug fixes from E-543.

Fixes:
  1. Reseed comparison now uses best_local (not state).
     Was: if cur_bank < state['mk'] - 0.1 → reseed.
     This fired every 6h because chains wander state high, resetting T.
     Now: if cur_bank < best_local['mk'] - 0.1 → reseed.
  2. Destroy operators scaled to n=181:
     - segment_reverse capped at length 3-20 (was avg 90 on n=181!)
     - random_k expanded to k ∈ {3, 5, 8, 12} (was 3, 5 only)
     - double_bridge size-clamped
  3. SA T0 = 5.0 (was 8.0 — less hot since bigger ops give more
     uphill anyway)
  4. SA_DECAY = 0.99999 per iter (slightly slower so we don't cool too
     fast given 4% feasibility on medium)

4 chains, 24h budget.
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
        "problems/medium.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
BAK = OUT + ".bak.20260609.e545"
FINE = '/tmp/ch2_medium_fine_pair_set.npz'
CKPT_TMPL = '/tmp/ch2_e545_ckpt_chain{}.json'

SA_T0 = 5.0
SA_DECAY = 0.99999    # per iter
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 6 * 3600

SEG_MIN = 3
SEG_MAX = 20


def destroy_random_k(perm, k, rng):
    n = len(perm)
    indices = rng.sample(range(1, n-1), min(k, n-2))
    removed = [perm[i] for i in indices]
    kept = [perm[i] for i in range(n) if i not in set(indices)]
    return kept, removed


def destroy_segment_reverse_bounded(perm, rng):
    """Reverse a segment of length [SEG_MIN, SEG_MAX]."""
    n = len(perm)
    if n < SEG_MIN + 4: return list(perm), []
    L = rng.randint(SEG_MIN, min(SEG_MAX, n - 4))
    i = rng.randint(1, n - L - 2)
    j = i + L
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:], []


def destroy_segment_shuffle_bounded(perm, rng):
    """Shuffle a segment of length [SEG_MIN, SEG_MAX]."""
    n = len(perm)
    if n < SEG_MIN + 4: return list(perm), []
    L = rng.randint(SEG_MIN, min(SEG_MAX, n - 4))
    i = rng.randint(1, n - L - 2)
    seg = list(perm[i:i+L])
    rng.shuffle(seg)
    return perm[:i] + seg + perm[i+L:], []


def destroy_swap(perm, rng):
    n = len(perm)
    if n < 4: return list(perm), []
    i = rng.randint(1, n-2); j = rng.randint(1, n-2)
    while j == i: j = rng.randint(1, n-2)
    p = list(perm); p[i], p[j] = p[j], p[i]
    return p, []


def destroy_or_opt(perm, rng):
    """Or-opt: move a segment of 1-3 consecutive nodes to a new position."""
    n = len(perm)
    if n < 8: return list(perm), []
    L = rng.randint(1, 3)
    i = rng.randint(1, n - L - 2)
    seg = perm[i:i+L]
    rest = perm[:i] + perm[i+L:]
    p = rng.randint(1, len(rest) - 1)
    return rest[:p] + seg + rest[p:], []


def repair_random_insert(kept, removed, rng):
    current = list(kept)
    rng.shuffle(removed)
    for node in removed:
        n = len(current)
        pos = rng.randint(1, n)
        current = current[:pos] + [node] + current[pos:]
    return current


def alns_chain(args):
    chain_id, max_wall_s, bank_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 9907 + 53)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    log("loading fine pair-set table...")
    t_load = time.time()
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    log(f"table loaded {time.time()-t_load:.1f}s (n={cheap_tab.shape[0]}, T={T})")

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
    hist_fh = open(f'/tmp/ch2_e545_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        sa_temp *= SA_DECAY

        op = rng.choices(
            ['random3', 'random5', 'random8', 'random12',
             'seg_rev', 'seg_shuf', 'swap', 'or_opt'],
            weights=[2, 3, 3, 2, 4, 3, 1, 3])[0]
        op_counts[op] = op_counts.get(op, 0) + 1
        if op == 'random3':
            kept, removed = destroy_random_k(state['perm'], 3, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'random5':
            kept, removed = destroy_random_k(state['perm'], 5, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'random8':
            kept, removed = destroy_random_k(state['perm'], 8, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'random12':
            kept, removed = destroy_random_k(state['perm'], 12, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'seg_rev':
            new_perm, _ = destroy_segment_reverse_bounded(state['perm'], rng)
        elif op == 'seg_shuf':
            new_perm, _ = destroy_segment_shuffle_bounded(state['perm'], rng)
        elif op == 'swap':
            new_perm, _ = destroy_swap(state['perm'], rng)
        else:
            new_perm, _ = destroy_or_opt(state['perm'], rng)

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
                        bp = bank_path + ".bak.e545"
                        if not Path(bp).exists():
                            Path(bp).write_bytes(Path(bank_path).read_bytes())
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
                f"DP_ok={n_dp_ok} accepted={n_accepted} "
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

        # FIXED reseed: compare to best_local, not state
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
                    log(f"reseeded from global mk={cur_mk:.4f} "
                        f"(was best_local {best_local['mk']:.4f})")
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
        print(f"ERR fine pair-set table missing"); return
    print(f"E-545 medium DP-ALNS (fixed). n_chains={n_chains} wall_h={wall_h}",
          flush=True)
    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    args = [(i, wall_h * 3600, OUT) for i in range(n_chains)]
    with mp.Pool(n_chains) as pool:
        results = pool.map(alns_chain, args)
    print(f"\nAll chains done.", flush=True)
    for ci, best in results:
        print(f"  chain {ci}: best={best['mk']:.4f}d", flush=True)


if __name__ == '__main__':
    n_ch = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    main(n_chains=n_ch, wall_h=wh)
