"""E-528 — Ch2 small: parallel ALNS with SLSQP polish (A — heavy compute).

8 parallel ALNS chains, each running independently with SA acceptance,
periodically syncing the global bank via the small.json file. Each chain:
  - Destroy: random-k (k ∈ [3,7]), worst-leg (top tof/min-tof ratio),
             segment-reverse, double-bridge
  - Repair:  sequential best-position insert (Lambert-feasibility filtered)
  - Evaluate: walk_perm_chrono → SLSQP polish (the C6-corrected evaluator)
  - Accept:   SA with chain-specific seed/temp schedule
  - Reseed:   every 6 h, swap perm with global bank if it's better

Targeted wall: 3-4 days. Checkpoints every 10 min per chain.
"""
from __future__ import annotations
import sys, os, json, time, random, math
from pathlib import Path
import numpy as np
import multiprocessing as mp
from scipy.optimize import minimize

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260605.e528"
HIST = '/tmp/ch2_e528_history.jsonl'
CKPT_TMPL = '/tmp/ch2_e528_ckpt_chain{}.json'

DV_CHEAP = 100.0; DV_EXC = 600.0
TOF_MIN = 0.001; TOF_MAX = 8.0; MAX_T = 200.0
PEN_CHRONO = 1e6; PEN_DV = 1e4

SA_T0 = 3.0           # initial temperature (in d)
SA_DECAY = 0.9998     # per-accept-attempt decay
RESEED_INTERVAL_S = 6 * 3600   # every 6h, check global bank
CKPT_INTERVAL_S = 600          # 10 min


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return 1e9


def make_obj(kt, perm, exc_set):
    n_legs = len(perm) - 1
    def f(x):
        times = x[:n_legs]; tofs = x[n_legs:]
        pc = 0.0
        for k in range(1, n_legs):
            s = times[k] - (times[k-1] + tofs[k-1])
            if s < 0: pc -= s
        pd = 0.0
        for k in range(n_legs):
            cap = DV_EXC if k in exc_set else DV_CHEAP
            dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
            if dv > cap: pd += dv - cap
        return times[-1] + tofs[-1] + PEN_CHRONO * pc + PEN_DV * pd
    return f


def slsqp_polish(kt, perm, t0, tof0, exc_set, maxiter=100):
    n_legs = len(perm) - 1
    x0 = np.array(list(t0) + list(tof0))
    bounds = [(0, MAX_T)] * n_legs + [(TOF_MIN, TOF_MAX)] * n_legs
    f = make_obj(kt, perm, exc_set)
    try:
        r = minimize(f, x0, method='SLSQP', bounds=bounds,
                     options={'maxiter': maxiter, 'ftol': 1e-7})
    except Exception:
        return None, 1e9, False
    x = r.x
    ts = list(x[:n_legs]); tfs = list(x[n_legs:])
    fit = kt.fitness(ts + tfs + [float(p) for p in perm])
    feas = bool(kt.is_feasible(fit))
    return (ts, tfs), (float(fit[0]) if len(fit) > 0 else 1e9), feas


def walk_and_polish(kt, perm):
    """walk_perm_chrono + SLSQP polish. Returns (ts, tfs, mk, feas) or None."""
    try:
        ts, tfs, dvs, ok, exc_n, _ = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception:
        return None
    if not ok or exc_n > kt.n_exc:
        return None
    mk_walk = ts[-1] + tfs[-1]
    if mk_walk > 200.0:
        return None
    exc_set = {k for k in range(len(perm)-1) if dvs[k] > DV_CHEAP + 1e-6}
    res, mk, feas = slsqp_polish(kt, perm, ts, tfs, exc_set)
    if not feas:
        return None
    return res[0], res[1], mk, exc_set


# ── Destroy operators ───────────────────────────────────────────────
def destroy_random_k(perm, k, rng):
    """Remove k random nodes (excluding start and end)."""
    n = len(perm)
    indices = rng.sample(range(1, n-1), min(k, n-2))
    removed = [perm[i] for i in indices]
    kept = [perm[i] for i in range(n) if i not in set(indices)]
    return kept, removed


def destroy_worst_leg(kt, perm, times, tofs, k, rng):
    """Remove the k nodes whose incoming legs have highest tof/min-tof ratio."""
    n = len(perm)
    if n < k + 2: return perm, []
    ratios = []
    for kk in range(1, n-1):
        i, j = perm[kk-1], perm[kk]
        cur_tof = tofs[kk-1] if kk-1 < len(tofs) else 1.0
        # rough estimate of "ideal" min tof via single Lambert call at the same t
        ratios.append((cur_tof, kk))
    ratios.sort(reverse=True)
    pick = [x[1] for x in ratios[:k]]
    pick_set = set(pick)
    removed = [perm[i] for i in pick]
    kept = [perm[i] for i in range(n) if i not in pick_set]
    return kept, removed


def destroy_segment_reverse(perm, rng):
    """2-opt: reverse a segment (no removal). Returns full new perm."""
    n = len(perm)
    if n < 6: return perm, []
    i = rng.randint(1, n-4); j = rng.randint(i+2, n-2)
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:], []


def destroy_double_bridge(perm, rng):
    n = len(perm)
    if n < 9: return perm, []
    cuts = sorted(rng.sample(range(1, n-1), 3))
    a, b, c = cuts
    return perm[:a] + perm[c:n-1] + perm[b:c] + perm[a:b] + perm[n-1:], []


# ── Repair: sequential best-position insert ─────────────────────────
def repair_best_position(kt, kept_perm, removed_nodes, rng):
    """Insert each removed node at the position that gives smallest walk_mk.
    Returns full perm (Lambert-feasibility filtered). May return None if hopeless.
    """
    current = list(kept_perm)
    # Random insertion order
    order = list(removed_nodes); rng.shuffle(order)
    for node in order:
        best_pos = None; best_mk = float('inf')
        n_cur = len(current)
        # Try every position between start and end (no insertion at 0 or end)
        for pos in range(1, n_cur):
            trial = current[:pos] + [node] + current[pos:]
            try:
                ts, tfs, _, ok, exc_n, _ = walk_perm_chrono(
                    kt, trial, tof_window=18.0, n_steps=180,
                    wait_steps=12, wait_dt=1.0)
            except Exception:
                continue
            if not ok or exc_n > kt.n_exc:
                continue
            mk = ts[-1] + tfs[-1]
            if mk < best_mk:
                best_mk = mk; best_pos = pos
        if best_pos is None:
            return None
        current = current[:best_pos] + [node] + current[best_pos:]
    return current


# ── Main ALNS chain ─────────────────────────────────────────────────
def alns_chain(args):
    chain_id, max_wall_s, bank_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 7919 + int(time.time()) & 0xFFFF)
    sys.stdout.reconfigure(line_buffering=True)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    # Load initial bank
    bank = json.load(open(bank_path))
    dv = bank[0]['decisionVector']
    times0 = list(dv[:n-1]); tofs0 = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]
    state_mk = float(kt.fitness(dv)[0])
    state = {'perm': perm, 'ts': times0, 'tfs': tofs0, 'mk': state_mk}
    best_local = dict(state)
    log(f"init state mk={state_mk:.4f}d")

    # Try to load checkpoint (if resuming)
    ckpt_path = CKPT_TMPL.format(chain_id)
    if Path(ckpt_path).exists():
        try:
            ck = json.load(open(ckpt_path))
            if ck['perm'] and len(ck['perm']) == n:
                state = ck
                if ck['mk'] < best_local['mk']:
                    best_local = dict(state)
                log(f"resumed from ckpt mk={state['mk']:.4f}d")
        except Exception:
            pass

    sa_temp = SA_T0
    t0 = time.time()
    iter_count = 0; n_accepted = 0; n_polished = 0
    last_reseed = time.time()
    last_ckpt = time.time()
    hist_fh = open(f'/tmp/ch2_e528_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1

        # Choose destroy operator
        op = rng.choices(
            ['random_k', 'worst_leg', 'segment_reverse', 'double_bridge'],
            weights=[3, 2, 3, 2])[0]
        if op == 'random_k':
            k = rng.randint(3, 7)
            kept, removed = destroy_random_k(state['perm'], k, rng)
        elif op == 'worst_leg':
            k = rng.randint(3, 5)
            kept, removed = destroy_worst_leg(
                kt, state['perm'], state['ts'], state['tfs'], k, rng)
        elif op == 'segment_reverse':
            new_perm, _ = destroy_segment_reverse(state['perm'], rng)
            kept = new_perm; removed = []
        else:  # double_bridge
            new_perm, _ = destroy_double_bridge(state['perm'], rng)
            kept = new_perm; removed = []

        # Repair
        if removed:
            new_perm = repair_best_position(kt, kept, removed, rng)
            if new_perm is None: continue
        else:
            new_perm = kept

        # Evaluate
        result = walk_and_polish(kt, new_perm)
        if result is None: continue
        n_polished += 1
        new_ts, new_tfs, new_mk, new_exc = result

        # SA acceptance
        delta = new_mk - state['mk']
        accept = delta < 0 or rng.random() < math.exp(-delta / sa_temp)
        if accept:
            n_accepted += 1
            state = {'perm': new_perm, 'ts': new_ts, 'tfs': new_tfs,
                     'mk': new_mk}
            if new_mk < best_local['mk']:
                best_local = dict(state)
                hist_fh.write(json.dumps({
                    'chain': chain_id, 'iter': iter_count,
                    'mk': new_mk, 'op': op,
                    'elapsed_s': time.time() - t0,
                }) + '\n')
                hist_fh.flush()
                # Attempt global bank update (atomic)
                try:
                    cur_bank = json.load(open(bank_path))
                    cur_mk = float(kt.fitness(cur_bank[0]['decisionVector'])[0])
                    if new_mk < cur_mk - 1e-4:
                        x_full = list(new_ts) + list(new_tfs) + \
                                  [float(p) for p in new_perm]
                        # Backup once
                        bp = bank_path + ".bak.e528"
                        if not Path(bp).exists():
                            Path(bp).write_bytes(Path(bank_path).read_bytes())
                        tmp = bank_path + '.tmp'
                        Path(tmp).write_text(json.dumps([{
                            'decisionVector': x_full, 'problem': 'small',
                            'challenge': CHALLENGE,
                        }]))
                        os.replace(tmp, bank_path)
                        log(f"BANKED {new_mk:.4f}d "
                            f"(was {cur_mk:.4f}, iter={iter_count})")
                except Exception as e:
                    log(f"bank-update err: {str(e)[:60]}")

        sa_temp *= SA_DECAY

        # Periodic logging
        if iter_count % 50 == 0:
            elapsed = time.time() - t0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"polished={n_polished} accepted={n_accepted} "
                f"state={state['mk']:.4f} best={best_local['mk']:.4f} "
                f"T={sa_temp:.3f}")

        # Periodic checkpoint
        if time.time() - last_ckpt > CKPT_INTERVAL_S:
            try:
                json.dump({'perm': state['perm'], 'ts': state['ts'],
                           'tfs': state['tfs'], 'mk': state['mk'],
                           'best_mk': best_local['mk'],
                           'iter': iter_count}, open(ckpt_path, 'w'))
            except Exception as e:
                log(f"ckpt err: {str(e)[:60]}")
            last_ckpt = time.time()

        # Periodic reseed from global bank
        if time.time() - last_reseed > RESEED_INTERVAL_S:
            try:
                cur_bank = json.load(open(bank_path))
                cur_dv = cur_bank[0]['decisionVector']
                cur_mk = float(kt.fitness(cur_dv)[0])
                if cur_mk < state['mk'] - 0.1:
                    # global bank is meaningfully better — adopt
                    state = {
                        'perm': [int(x) for x in cur_dv[2*(n-1):]],
                        'ts': list(cur_dv[:n-1]),
                        'tfs': list(cur_dv[n-1:2*(n-1)]),
                        'mk': cur_mk,
                    }
                    sa_temp = SA_T0  # reset temp
                    log(f"reseeded from global bank mk={cur_mk:.4f}")
            except Exception:
                pass
            last_reseed = time.time()

    hist_fh.close()
    log(f"chain done. iters={iter_count} best={best_local['mk']:.4f}d")
    return chain_id, best_local


def main(n_chains=8, wall_h=72):
    print(f"E-528 parallel ALNS. n_chains={n_chains}, wall_h={wall_h}",
          flush=True)
    max_wall_s = wall_h * 3600
    args = [(i, max_wall_s, OUT) for i in range(n_chains)]
    # Backup current bank once at start
    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    with mp.Pool(n_chains) as pool:
        results = pool.map(alns_chain, args)
    print(f"\nAll chains done.", flush=True)
    for ci, best in results:
        print(f"  chain {ci}: best={best['mk']:.4f}d", flush=True)


if __name__ == '__main__':
    n_ch = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 72.0
    main(n_chains=n_ch, wall_h=wh)
