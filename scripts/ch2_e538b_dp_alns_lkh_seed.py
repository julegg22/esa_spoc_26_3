"""E-538b — Fixed SA cooling: per-iter decay (not per-DP-feasible).

Bug discovery in E-538: `sa_temp *= SA_DECAY` was applied after the
`continue` statements that handled DP-infeasibility, meaning the SA
schedule was decoupled from wall-clock and depended on the (tiny) DP
feasibility rate. At ~1.1% feasibility, the chains spent ~3h in hot
exploration without effective cooling.

Fix: move sa_temp decay to BEFORE the continues. Each iteration
(feasible or not) advances the SA schedule.

Same dual-seed setup: bank vs LKH-3 perm.
SA_T0 = 8.0 (hotter initial), SA_DECAY = 0.99995 (per iter).
At 50k iters: T = 8 × 0.99995^50000 = 0.66. Well-cooled.
2 h budget (each chain typically reaches 25-30k iters in 2h on this
4-core machine under contention).
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
BAK = OUT + ".bak.20260607.e538b"
FINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
LKH_RESULT = '/tmp/ch2_e536_result.json'

SA_T0 = 8.0
SA_DECAY = 0.99995    # per-iter
CKPT_INTERVAL_S = 600
CKPT_TMPL = '/tmp/ch2_e538b_ckpt_chain{}.json'


def destroy_random_k(perm, k, rng):
    n = len(perm)
    indices = rng.sample(range(1, n-1), min(k, n-2))
    removed = [perm[i] for i in indices]
    kept = [perm[i] for i in range(n) if i not in set(indices)]
    return kept, removed


def destroy_segment_reverse(perm, rng):
    n = len(perm)
    if n < 6: return list(perm), []
    i = rng.randint(1, n-4); j = rng.randint(i+2, n-2)
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:], []


def destroy_double_bridge(perm, rng):
    n = len(perm)
    if n < 9: return list(perm), []
    cuts = sorted(rng.sample(range(1, n-1), 3))
    a, b, c = cuts
    return perm[:a] + perm[c:n-1] + perm[b:c] + perm[a:b] + perm[n-1:], []


def destroy_swap(perm, rng):
    n = len(perm)
    if n < 4: return list(perm), []
    i = rng.randint(1, n-2); j = rng.randint(1, n-2)
    while j == i: j = rng.randint(1, n-2)
    p = list(perm); p[i], p[j] = p[j], p[i]
    return p, []


def repair_random_insert(kept, removed, rng):
    current = list(kept)
    rng.shuffle(removed)
    for node in removed:
        n = len(current)
        pos = rng.randint(1, n)
        current = current[:pos] + [node] + current[pos:]
    return current


def alns_chain(args):
    chain_id, max_wall_s, init_perm, init_label = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 9907 + 31)
    log = lambda msg: print(f"[c{chain_id}/{init_label}] {msg}", flush=True)

    log("loading ultrafine table...")
    t_load = time.time()
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    log(f"table loaded in {time.time()-t_load:.1f}s")

    log(f"DP-evaluating init seed...")
    t0 = time.time()
    seed_res = evaluate_perm_dp_numba(kt, init_perm, cheap_tab, exc_tab, q, T)
    log(f"  DP wall: {time.time()-t0:.1f}s mk={seed_res['mk']:.4f}d")

    state = {'perm': init_perm, 'mk': seed_res['mk'],
             'times': seed_res['times'], 'tofs': seed_res['tofs']}
    best_local = dict(state)

    sa_temp = SA_T0
    iter_count = 0; n_dp_ok = 0; n_dp_fail = 0; n_accepted = 0
    t0 = time.time(); last_ckpt = time.time()
    hist_fh = open(f'/tmp/ch2_e538b_chain{chain_id}_hist.jsonl', 'a')
    ckpt = CKPT_TMPL.format(chain_id)

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        # *** FIX: SA decay every iter, BEFORE any continue ***
        sa_temp *= SA_DECAY

        op = rng.choices(
            ['random3', 'random5', 'segment_reverse', 'double_bridge', 'swap'],
            weights=[3, 2, 3, 2, 1])[0]
        if op == 'random3':
            kept, removed = destroy_random_k(state['perm'], 3, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'random5':
            kept, removed = destroy_random_k(state['perm'], 5, rng)
            new_perm = repair_random_insert(kept, removed, rng)
        elif op == 'segment_reverse':
            new_perm, _ = destroy_segment_reverse(state['perm'], rng)
        elif op == 'double_bridge':
            new_perm, _ = destroy_double_bridge(state['perm'], rng)
        else:
            new_perm, _ = destroy_swap(state['perm'], rng)
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
            state = {'perm': new_perm, 'mk': new_mk,
                     'times': result['times'], 'tofs': result['tofs']}
            if new_mk < best_local['mk']:
                best_local = dict(state)
                hist_fh.write(json.dumps({
                    'chain': chain_id, 'init': init_label,
                    'iter': iter_count, 'mk': new_mk, 'op': op,
                    'elapsed_s': time.time() - t0,
                }) + '\n')
                hist_fh.flush()
                try:
                    cur = json.load(open(OUT))
                    cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
                    if new_mk < cur_mk - 1e-4:
                        x_full = list(result['times']) + list(result['tofs']) + \
                                  [float(p) for p in new_perm]
                        if not Path(BAK).exists():
                            Path(BAK).write_bytes(Path(OUT).read_bytes())
                        tmp = OUT + '.tmp'
                        Path(tmp).write_text(json.dumps([{
                            'decisionVector': x_full, 'problem': 'small',
                            'challenge': CHALLENGE,
                        }]))
                        os.replace(tmp, OUT)
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
                           'init_label': init_label},
                          open(ckpt, 'w'))
            except Exception: pass
            last_ckpt = time.time()

    hist_fh.close()
    log(f"chain done. iters={iter_count} best={best_local['mk']:.4f}d "
        f"(seeded from {init_label})")
    return chain_id, init_label, best_local


def main(wall_h: float = 2.0):
    if not Path(FINE).exists():
        print(f"ERR ultrafine table missing"); return
    if not Path(LKH_RESULT).exists():
        print(f"ERR LKH-3 result missing"); return

    print(f"E-538b dual-seed DP-ALNS (fixed SA cooling). wall_h={wall_h}",
          flush=True)
    bank = json.load(open(OUT))
    n_kt = KTTSP(INST).n
    bank_perm = [int(x) for x in bank[0]['decisionVector'][2*(n_kt-1):]]
    lkh_res = json.load(open(LKH_RESULT))
    lkh_perm = lkh_res['lkh_sym_perm']
    print(f"  Bank seed: start={bank_perm[0]} end={bank_perm[-1]}",
          flush=True)
    print(f"  LKH-3 seed: start={lkh_perm[0]} end={lkh_perm[-1]}", flush=True)
    print(f"  SA_T0={SA_T0}, SA_DECAY={SA_DECAY} (per iter)", flush=True)

    args = [
        (0, wall_h * 3600, bank_perm, 'bank'),
        (1, wall_h * 3600, lkh_perm, 'lkh3'),
    ]
    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    with mp.Pool(2) as pool:
        results = pool.map(alns_chain, args)
    print(f"\nAll chains done.", flush=True)
    for ci, lab, best in results:
        print(f"  chain {ci} ({lab}): best={best['mk']:.4f}d", flush=True)


if __name__ == '__main__':
    wh = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    main(wall_h=wh)
