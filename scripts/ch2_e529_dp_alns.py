"""E-529 — Ch2 small: parallel ALNS with DP-on-ultrafine-table evaluator.

E-527 revealed walk+SLSQP misses up to 16 d on a single perm because the
Lambert dv landscape is discontinuous; gradient-based optimizers can't
reliably escape local basins. DP on the 0.05 d ultrafine table finds
the provable global optimum schedule for any perm.

This script runs ALNS with DP as the evaluator. Each iteration:
  1. Destroy current perm (random-k, segment reverse, double bridge, etc.)
  2. Repair (sequential best-position insert via walk_perm_chrono filter)
  3. DP-evaluate the candidate perm (returns provable optimum schedule)
  4. SA accept/reject
  5. Bank globally if improvement

Cost: DP ~200 s per perm on 1 core; infeasible perms much faster
(no-sink terminates DP early). On 6 parallel chains, ~30 evals/h per chain.
In 3 days: ~13k evals total — small but each is DP-quality.
"""
from __future__ import annotations
import sys, os, json, time, random, math
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from ch2_dp_numba import evaluate_perm_dp_numba as _eval_dp_numba

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260605.e529"
FINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
CKPT_TMPL = '/tmp/ch2_e529_ckpt_chain{}.json'
HIST = '/tmp/ch2_e529_history.jsonl'

DV_CHEAP = 100.0
INF = 10**9

SA_T0 = 5.0
SA_DECAY = 0.999
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 4 * 3600


# ── DP evaluator ────────────────────────────────────────────────────
def precompute_edges_for_perm(perm, cheap_tab, exc_tab, q, T):
    """For each leg, build (arr_bucket, actual_tof) lookup."""
    n_legs = len(perm) - 1
    c_arr = np.full((n_legs, T), INF, dtype=np.int32)
    c_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, T), INF, dtype=np.int32)
    e_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    for k in range(n_legs):
        i, j = perm[k], perm[k+1]
        c_row = cheap_tab[i, j]; e_row = exc_tab[i, j]
        for tp in range(T):
            ct = c_row[tp]
            if np.isfinite(ct):
                c_tof[k, tp] = ct
                arr = tp + int(np.ceil(float(ct) / q))
                if arr < T: c_arr[k, tp] = arr
            et = e_row[tp]
            if np.isfinite(et):
                e_tof[k, tp] = et
                arr = tp + int(np.ceil(float(et) / q))
                if arr < T: e_arr[k, tp] = arr
    return c_arr, c_tof, e_arr, e_tof


def dp_evaluate(perm, cheap_tab, exc_tab, q, T, n_exc_max):
    """Forward DP on perm. Returns (sink_bucket, exc_used, legs) or None.
    legs: list of (dep_bucket, arr_bucket, isexc)."""
    n_legs = len(perm) - 1
    c_arr, c_tof, e_arr, e_tof = precompute_edges_for_perm(
        perm, cheap_tab, exc_tab, q, T)
    # Early-exit: hopeless legs
    for k in range(n_legs):
        if (c_arr[k] >= INF).all() and (e_arr[k] >= INF).all():
            return None, c_tof, e_tof

    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=bool)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_isexc = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True

    for k in range(n_legs):
        ts_e = np.argwhere(reach[k])
        if ts_e.shape[0] == 0:
            return None, c_tof, e_tof
        for t, e in ts_e:
            t = int(t); e = int(e)
            for tp in range(t, T):
                arr = c_arr[k, tp]
                if arr < INF and arr < T:
                    if not reach[k+1, arr, e]:
                        reach[k+1, arr, e] = True
                        pred_t[k+1, arr, e] = t
                        pred_e[k+1, arr, e] = e
                        pred_dep[k+1, arr, e] = tp
                        pred_isexc[k+1, arr, e] = 0
            if e < n_exc_max:
                for tp in range(t, T):
                    arr = e_arr[k, tp]
                    if arr < INF and arr < T:
                        if not reach[k+1, arr, e+1]:
                            reach[k+1, arr, e+1] = True
                            pred_t[k+1, arr, e+1] = t
                            pred_e[k+1, arr, e+1] = e
                            pred_dep[k+1, arr, e+1] = tp
                            pred_isexc[k+1, arr, e+1] = 1

    sink = reach[n_legs]
    finite_ts = np.where(sink.any(axis=1))[0]
    if len(finite_ts) == 0:
        return None, c_tof, e_tof
    min_t = int(finite_ts.min())
    e_used = int(np.where(sink[min_t])[0].min())

    legs = []
    k = n_legs; t = min_t; e = e_used
    while k > 0:
        prev_t = int(pred_t[k, t, e])
        prev_e = int(pred_e[k, t, e])
        dep = int(pred_dep[k, t, e])
        isexc = int(pred_isexc[k, t, e])
        legs.append((dep, t, isexc))
        k -= 1; t = prev_t; e = prev_e
    legs.reverse()
    return (min_t, e_used, legs), c_tof, e_tof


def reconstruct_actual_schedule(legs, c_tof, e_tof, q):
    times = [leg[0] * q for leg in legs]
    tofs = []
    for k, (dep, arr, isexc) in enumerate(legs):
        tof = float(e_tof[k, dep] if isexc else c_tof[k, dep])
        tofs.append(tof)
    return times, tofs


def evaluate_perm_dp(kt, perm, cheap_tab, exc_tab, q, T):
    """Numba-JIT'd version. Returns dict with mk/times/tofs or None."""
    return _eval_dp_numba(kt, perm, cheap_tab, exc_tab, q, T)


# ── Destroy operators ───────────────────────────────────────────────
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


# ── Repair: cheap walk-feasibility filter for inserts ───────────────
def repair_random_insert(kept, removed, rng):
    """Just insert removed nodes at random positions. Fast but may fail DP."""
    current = list(kept)
    rng.shuffle(removed)
    for node in removed:
        n = len(current)
        pos = rng.randint(1, n)
        current = current[:pos] + [node] + current[pos:]
    return current


# ── ALNS chain ──────────────────────────────────────────────────────
def alns_chain(args):
    chain_id, max_wall_s, bank_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 7919 + 11)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    # Load ultrafine table once per chain
    log("loading ultrafine table...")
    t_load = time.time()
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    log(f"table loaded in {time.time()-t_load:.1f}s q={q}d T={T}")

    # Load bank
    bank = json.load(open(bank_path))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    state = {'perm': perm, 'mk': bank_mk,
             'times': list(dv[:n-1]), 'tofs': list(dv[n-1:2*(n-1)])}
    best_local = dict(state)
    log(f"init bank mk={bank_mk:.4f}d")

    # Resume from ckpt
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
    t0 = time.time(); last_ckpt = time.time(); last_reseed = time.time()
    hist_fh = open(f'/tmp/ch2_e529_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        # Destroy + repair
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

        # DP evaluate
        t_eval = time.time()
        result = evaluate_perm_dp(kt, new_perm, cheap_tab, exc_tab, q, T)
        eval_wall = time.time() - t_eval
        if result is None:
            n_dp_fail += 1
            continue
        n_dp_ok += 1
        new_mk = result['mk']

        # SA accept
        delta = new_mk - state['mk']
        accept = delta < 0 or rng.random() < math.exp(-delta / sa_temp)
        if accept:
            n_accepted += 1
            state = {'perm': new_perm, 'mk': new_mk,
                     'times': result['times'], 'tofs': result['tofs']}
            if new_mk < best_local['mk']:
                best_local = dict(state)
                hist_fh.write(json.dumps({
                    'chain': chain_id, 'iter': iter_count, 'mk': new_mk,
                    'op': op, 'eval_wall_s': eval_wall,
                    'elapsed_s': time.time() - t0,
                }) + '\n')
                hist_fh.flush()
                # Atomic bank update if globally better
                try:
                    cur = json.load(open(bank_path))
                    cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
                    if new_mk < cur_mk - 1e-4:
                        x_full = list(result['times']) + list(result['tofs']) + \
                                  [float(p) for p in new_perm]
                        bp = bank_path + ".bak.e529"
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

        if iter_count % 5 == 0:
            elapsed = time.time() - t0
            rate = (n_dp_ok + n_dp_fail) / elapsed if elapsed > 0 else 0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"DP_ok={n_dp_ok} DP_fail={n_dp_fail} accepted={n_accepted} "
                f"rate={rate*60:.1f}/min state={state['mk']:.4f} "
                f"best={best_local['mk']:.4f} T={sa_temp:.3f}")

        if time.time() - last_ckpt > CKPT_INTERVAL_S:
            try:
                json.dump({'perm': state['perm'], 'times': state['times'],
                           'tofs': state['tofs'], 'mk': state['mk'],
                           'best_mk': best_local['mk'], 'iter': iter_count},
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
    return chain_id, best_local


def main(n_chains=6, wall_h=72):
    if not Path(FINE).exists():
        print(f"ERR ultrafine table missing: {FINE}"); return
    print(f"E-529 DP-based parallel ALNS. n_chains={n_chains} wall_h={wall_h}",
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
    n_ch = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 72.0
    main(n_chains=n_ch, wall_h=wh)
