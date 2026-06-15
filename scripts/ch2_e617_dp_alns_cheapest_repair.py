"""E-617 — Ch2 small: DP-ALNS with CHEAPEST-INSERTION repair (the missing operator).

Evidence motivating this (2026-06-15 fresh-perspective audit):
  E-529 DP-ALNS already has every ingredient competitive TD-TSP solvers use —
  SA uphill acceptance, destroy operators, and a DP that finds the PROVABLE
  optimum schedule (timing + exc-bridge selection) for any order. It floored at
  112.996 d. The ONE weak link is its repair: `repair_random_insert` drops the
  removed nodes at RANDOM positions ("Fast but may fail DP"). That is the exact
  operator the matching E-579 lever-2 replaced with exact repair, and the
  textbook ALNS workhorse we never wired into Ch2-small.

  We CANNOT do per-candidate DP repair: the ultrafine DP is ~200 s/perm, and an
  optimal-window repair would need ~230 DP evals per repair (~12 h). Instead we
  rank insertion positions with the precomputed min-over-epoch cheap-tof table
  (microsecond lookups) — cheapest-insertion — and DP-evaluate only the single
  assembled candidate, exactly as E-529 already does. So per-iteration cost is
  unchanged (~one DP) but the candidate is far stronger than random.

  Regret-2 variant added: insert the node whose 2nd-best gap is much worse than
  its best (most "regretful") first — standard ALNS, escapes greedy myopia.

This is the decisive test of the basin-overarching conjecture for small: if a
strong-repair destroy+SA still floors at 112.996, small's gap to R3 (101.65) is
a true model floor, not a search-architecture gap. If it crosses, the lever was
repair quality all along.

Guard-banked exactly as E-529 (backup once, atomic replace only if strictly
better + feasible round-trip via kt.fitness).

Usage: python ch2_e617_dp_alns_cheapest_repair.py [n_chains=4] [wall_h=48]
"""
from __future__ import annotations
import sys, os, json, time, random, math
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ch2_e529_dp_alns import (
    evaluate_perm_dp, destroy_random_k, destroy_segment_reverse,
    destroy_double_bridge, destroy_swap,
    INST, OUT, FINE,
)

sys.stdout.reconfigure(line_buffering=True)

BAK = OUT + ".bak.20260615.e617"
CKPT_TMPL = '/tmp/ch2_e617_ckpt_chain{}.json'
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 4 * 3600
EXC_PENALTY = 50.0   # added to exc-edge min-tof when ranking inserts (prefer cheap)

# ── ILS (basin-hopping) schedule ──
RRT_DEV = 0.01        # accept sideways within 1% of best (~1.1d band) for diversity
KICK_MIN = 3          # base perturbation size (nodes destroyed)
KICK_MAX = 12         # max perturbation when stagnating
ESCALATE_EVERY = 60   # stale iters before kick grows by 1
STALE_LIMIT = 250     # stale iters before hard-restart from best


# ── min-over-epoch tof tables for cheapest-insertion ranking ────────────
def build_mintof(cheap_tab, exc_tab):
    """Best-case (min over epoch) tof per directed pair. inf where no transfer.
    Returns (mintof, is_exc_only): mintof used to rank inserts; cheap preferred."""
    n = cheap_tab.shape[0]
    with np.errstate(invalid='ignore'):
        cmin = np.nanmin(np.where(np.isfinite(cheap_tab), cheap_tab, np.inf), axis=2)
        emin = np.nanmin(np.where(np.isfinite(exc_tab), exc_tab, np.inf), axis=2)
    # rank cost: cheap tof if it exists, else exc tof + penalty, else inf
    rank = np.where(np.isfinite(cmin), cmin, emin + EXC_PENALTY)
    np.fill_diagonal(rank, 0.0)
    return rank.astype(np.float64)


def cheapest_insertion_repair(kept, removed, rank, rng, regret=False):
    """Insert each removed node at the gap minimizing added rank-cost
    (mintof[a,x]+mintof[x,b]-mintof[a,b]). regret=True orders removed nodes by
    descending (2nd_best - best) gap cost and inserts the most-regretful first."""
    current = list(kept)
    pend = list(removed)
    rng.shuffle(pend)
    while pend:
        if regret and len(pend) > 1:
            # pick the node with the largest regret (best vs 2nd-best gap)
            best_node = None; best_regret = -1.0; best_pos_for = None
            for x in pend:
                costs = []
                for p in range(1, len(current) + 1):
                    a = current[p - 1]; b = current[p % len(current)] if p < len(current) else current[-1]
                    b = current[p] if p < len(current) else None
                    if b is None:
                        c = rank[a, x]
                    else:
                        c = rank[a, x] + rank[x, b] - rank[a, b]
                    costs.append((c, p))
                costs.sort()
                regret_val = (costs[1][0] - costs[0][0]) if len(costs) > 1 else 0.0
                if regret_val > best_regret:
                    best_regret = regret_val; best_node = x; best_pos_for = costs[0][1]
            x = best_node; pos = best_pos_for
            current = current[:pos] + [x] + current[pos:]
            pend.remove(x)
        else:
            x = pend.pop()
            best_c = math.inf; best_pos = 1
            for p in range(1, len(current) + 1):
                a = current[p - 1]
                if p < len(current):
                    b = current[p]
                    c = rank[a, x] + rank[x, b] - rank[a, b]
                else:
                    c = rank[a, x]
                if c < best_c:
                    best_c = c; best_pos = p
            current = current[:best_pos] + [x] + current[best_pos:]
    return current


# ── ALNS chain ──────────────────────────────────────────────────────────
def alns_chain(args):
    chain_id, max_wall_s, bank_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 7919 + 101)
    log = lambda msg: print(f"[c{chain_id}] {msg}", flush=True)

    log("loading ultrafine table...")
    t_load = time.time()
    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    rank = build_mintof(cheap_tab, exc_tab)
    log(f"table+rank ready in {time.time()-t_load:.1f}s q={q}d T={T}")

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

    # ── ILS (basin-hopping) state: always perturb the incumbent, accept within
    # an RRT band of best; escalate kick on stagnation; hard-restart from best.
    kick = KICK_MIN; stale = 0
    iter_count = 0; n_dp_ok = 0; n_dp_fail = 0; n_accepted = 0
    t0 = time.time(); last_ckpt = time.time(); last_reseed = time.time()
    hist_fh = open(f'/tmp/ch2_e617_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        # ── Perturb the INCUMBENT with strength `kick` (ILS) ──
        base = state['perm']
        r = rng.random()
        if r < 0.6:
            kept, removed = destroy_random_k(base, kick, rng)
            new_perm = cheapest_insertion_repair(kept, removed, rank, rng,
                                                 regret=(rng.random() < 0.4))
        elif r < 0.8:
            new_perm, _ = destroy_double_bridge(base, rng)
        elif r < 0.9:
            new_perm, _ = destroy_segment_reverse(base, rng)
        else:
            new_perm, _ = destroy_swap(base, rng)
        op = f'k{kick}'
        if len(set(new_perm)) != n: continue

        t_eval = time.time()
        result = evaluate_perm_dp(kt, new_perm, cheap_tab, exc_tab, q, T)
        eval_wall = time.time() - t_eval
        if result is None:
            n_dp_fail += 1
            continue
        n_dp_ok += 1
        new_mk = result['mk']
        cand = {'perm': new_perm, 'mk': new_mk,
                'times': result['times'], 'tofs': result['tofs']}

        # ── ILS accept: improve-incumbent OR sideways within RRT band of best ──
        if new_mk < state['mk'] - 1e-9 or \
           new_mk <= best_local['mk'] * (1.0 + RRT_DEV):
            state = cand
            n_accepted += 1

        if new_mk < best_local['mk'] - 1e-9:
            best_local = dict(cand)
            stale = 0; kick = KICK_MIN
            hist_fh.write(json.dumps({
                'chain': chain_id, 'iter': iter_count, 'mk': new_mk,
                'op': op, 'eval_wall_s': eval_wall,
                'elapsed_s': time.time() - t0,
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
                        'decisionVector': x_full, 'problem': 'small',
                        'challenge': CHALLENGE,
                    }]))
                    chk = json.loads(Path(tmp).read_text())
                    chk_mk = float(kt.fitness(chk[0]['decisionVector'])[0])
                    if chk_mk < cur_mk - 1e-4:
                        os.replace(tmp, bank_path)
                        log(f"BANKED {chk_mk:.4f}d (was {cur_mk:.4f}) "
                            f"op={op} iter={iter_count}")
                    else:
                        os.remove(tmp)
                        log(f"reject bank: round-trip {chk_mk:.4f} !< {cur_mk:.4f}")
            except Exception as e:
                log(f"bank err: {str(e)[:60]}")
        else:
            stale += 1
            if stale % ESCALATE_EVERY == 0:
                kick = min(kick + 1, KICK_MAX)
            if stale >= STALE_LIMIT:
                state = dict(best_local)   # hard restart from best
                stale = 0; kick = KICK_MIN

        if iter_count % 5 == 0:
            elapsed = time.time() - t0
            rate = (n_dp_ok + n_dp_fail) / elapsed if elapsed > 0 else 0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"DP_ok={n_dp_ok} DP_fail={n_dp_fail} accepted={n_accepted} "
                f"rate={rate*60:.1f}/min state={state['mk']:.4f} "
                f"best={best_local['mk']:.4f} kick={kick} stale={stale}")

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
                if cur_mk < best_local['mk'] - 1e-4:
                    dv2 = cur[0]['decisionVector']
                    best_local = {
                        'perm': [int(x) for x in dv2[2*(n-1):]],
                        'times': list(dv2[:n-1]),
                        'tofs': list(dv2[n-1:2*(n-1)]),
                        'mk': cur_mk,
                    }
                    state = dict(best_local)
                    stale = 0; kick = KICK_MIN
                    log(f"adopted better global bank mk={cur_mk:.4f}")
            except Exception: pass
            last_reseed = time.time()

    hist_fh.close()
    log(f"chain done. iters={iter_count} best={best_local['mk']:.4f}d")
    return chain_id, best_local


def main(n_chains=4, wall_h=48):
    if not Path(FINE).exists():
        print(f"ERR ultrafine table missing: {FINE}"); return
    print(f"E-617 cheapest-insertion DP-ALNS. n_chains={n_chains} wall_h={wall_h}",
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
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 48.0
    main(n_chains=n_ch, wall_h=wh)
