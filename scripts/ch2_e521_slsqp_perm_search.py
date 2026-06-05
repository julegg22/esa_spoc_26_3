"""E-521 — Ch2 small: perm search with SLSQP-polished evaluation.

Fixes the C6 bug at scale: replace walk_perm_chrono with walk +
SLSQP polish as the perm evaluator. Without this, every perm-search
comparison happens in distorted greedy units (the bug E-519b
exposed).

Architecture:
  Per candidate perm:
    1. walk_perm_chrono(perm) — cheap filter, gives initial (times, tofs)
       and exc-leg classification
    2. If walk result feasible and walk_mk < bank + 10d:
         SLSQP polish (1-2 starts) using walk's (times, tofs) as seed
       Else: skip
    3. If SLSQP-mk < bank: try to bank

Perm mutations: bank-anchored 2-opt + or-opt (single-segment moves
that keep most of bank's structure). Avoid global random shuffles
since those are guaranteed Lambert-infeasible per E-516.

Runs in 1-2 worker processes for parallelism (each SLSQP call is
single-threaded; pool of 4 workers fits desktop).
"""
from __future__ import annotations
import sys, os, json, time, random
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
BAK = OUT + ".bak.20260603.e521"
RESULT = '/tmp/ch2_e521_result.json'
HIST = '/tmp/ch2_e521_history.jsonl'
POOL = '/tmp/ch2_e521_pool.jsonl'    # save promising perms for future re-seeding

DV_CHEAP = 100.0
DV_EXC = 600.0
TOF_MIN = 0.001
TOF_MAX = 8.0
MAX_T = 200.0
PEN_CHRONO = 1e6
PEN_DV = 1e4

_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return 1e9


def make_obj(kt, perm, exc_set):
    n = kt.n
    n_legs = n - 1

    def f(x):
        times = x[:n_legs]; tofs = x[n_legs:]
        pen_c = 0.0
        for k in range(1, n_legs):
            s = times[k] - (times[k-1] + tofs[k-1])
            if s < 0:
                pen_c -= s
        pen_d = 0.0
        for k in range(n_legs):
            cap = DV_EXC if k in exc_set else DV_CHEAP
            dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
            if dv > cap:
                pen_d += dv - cap
        mk = times[-1] + tofs[-1]
        return mk + PEN_CHRONO * pen_c + PEN_DV * pen_d
    return f


def slsqp_polish(kt, perm, times0, tofs0, exc_set, maxiter=120):
    n_legs = len(perm) - 1
    x0 = np.array(list(times0) + list(tofs0))
    bounds = [(0, MAX_T)] * n_legs + [(TOF_MIN, TOF_MAX)] * n_legs
    f = make_obj(kt, perm, exc_set)
    try:
        r = minimize(f, x0, method='SLSQP', bounds=bounds,
                     options={'maxiter': maxiter, 'ftol': 1e-7})
    except Exception:
        return None, 1e9, False
    x = r.x
    ts = list(x[:n_legs]); tfs = list(x[n_legs:])
    x_udp = ts + tfs + [float(p) for p in perm]
    fit = kt.fitness(x_udp)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0]) if len(fit) > 0 else 1e9
    return (ts, tfs), mk, feas


def get_exc_set(kt, perm, times, tofs):
    s = set()
    for k in range(len(perm) - 1):
        dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
        if dv > DV_CHEAP + 1e-6:
            s.add(k)
    return s


def mutate(perm, rng):
    """Bank-preserving mutations: 2-opt, or-opt, double-bridge, swap, 3-opt."""
    n = len(perm); p = list(perm)
    op = rng.choices(['2opt', 'orpt_1', 'orpt_2', 'orpt_3', 'swap',
                       'double_bridge', '3opt'],
                     weights=[3, 2, 2, 1, 1, 2, 2])[0]
    if op == '2opt':
        i = rng.randint(1, n-3); j = rng.randint(i+1, n-2)
        return p[:i] + p[i:j+1][::-1] + p[j+1:]
    elif op.startswith('orpt'):
        L = int(op[-1])
        if L >= n-2: return p
        i = rng.randint(1, n-L-1)
        seg = p[i:i+L]; rest = p[:i] + p[i+L:]
        q = rng.randint(1, len(rest))
        return rest[:q] + seg + rest[q:]
    elif op == 'swap':
        i = rng.randint(1, n-2); j = rng.randint(1, n-2)
        if i == j: return p
        p[i], p[j] = p[j], p[i]; return p
    elif op == 'double_bridge':
        if n < 9: return p
        cuts = sorted(rng.sample(range(1, n-1), 3))
        a, b, c = cuts
        return p[:a] + p[c:n-1] + p[b:c] + p[a:b] + p[n-1:]  # preserve last
    elif op == '3opt':
        # 3 random cuts, randomly choose one of 7 reconnections (we use 2)
        if n < 8: return p
        cuts = sorted(rng.sample(range(1, n-2), 3))
        a, b, c = cuts
        # Variant: reverse middle segments
        return p[:a] + p[b:c][::-1] + p[a:b][::-1] + p[c:]
    return p


def eval_perm(args):
    """Evaluate one candidate perm: walk_perm_chrono then SLSQP-polish.
    Returns dict with results."""
    cand_id, perm = args
    kt = _GLOB['kt']
    rec = {'cand_id': cand_id, 'perm_first5': perm[:5]}
    try:
        ts0, tfs0, dvs, ok, exc_n, last_leg = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception as e:
        rec['walk_err'] = str(e)[:60]
        return rec
    if not ok:
        rec['walk_ok'] = False
        rec['walk_last_leg'] = int(last_leg)
        return rec
    walk_mk = ts0[-1] + tfs0[-1]
    rec['walk_ok'] = True
    rec['walk_mk'] = float(walk_mk)
    rec['walk_exc'] = int(exc_n)

    # Filter: only polish if walk is competitive
    if walk_mk > 150.0:
        return rec  # too far; skip SLSQP

    exc_set = get_exc_set(kt, perm, ts0, tfs0)
    res, slsqp_mk, feas = slsqp_polish(kt, perm, ts0, tfs0, exc_set)
    rec['slsqp_mk'] = float(slsqp_mk)
    rec['slsqp_feas'] = bool(feas)
    if feas:
        rec['perm'] = perm
        rec['ts'] = res[0] if res else None
        rec['tfs'] = res[1] if res else None
    return rec


def main(n_cands=2000, n_workers=4, seed_pool_path=None):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_times = list(dv[:n-1]); bank_tofs = list(dv[n-1:2*(n-1)])
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(bank_times + bank_tofs +
                                 [float(p) for p in bank_perm])[0])
    print(f"E-521 SLSQP-polished perm search. bank_mk={bank_mk:.4f}d. "
          f"n_cands={n_cands}, workers={n_workers}", flush=True)

    # Load seed pool if provided
    seed_perms = [bank_perm]
    if seed_pool_path and Path(seed_pool_path).exists():
        for line in open(seed_pool_path):
            try:
                d = json.loads(line)
                if 'perm' in d and len(d['perm']) == n:
                    seed_perms.append(list(map(int, d['perm'])))
            except Exception:
                pass
        print(f"Loaded {len(seed_perms)-1} pool perms (+ bank = "
              f"{len(seed_perms)} seeds)", flush=True)

    rng = random.Random(0)
    # Generate candidate perms: seed-anchored mutations (round-robin across seeds)
    candidates = []
    for cid in range(n_cands):
        seed = seed_perms[cid % len(seed_perms)]
        p = list(seed)
        # 1-5 mutations
        for _ in range(rng.randint(1, 5)):
            p = mutate(p, rng)
        candidates.append((cid, p))
    print(f"Generated {len(candidates)} candidate perms.", flush=True)

    best_slsqp = (bank_mk, None, None, None)
    n_walk_ok = 0; n_slsqp_polished = 0; n_polished_feas = 0
    n_under_bank = 0
    n_pool = 0
    hist = open(HIST, 'w')
    pool_fh = open(POOL, 'w')
    pool_threshold = bank_mk + 0.5    # save anything within 0.5 d of bank

    t0 = time.time()
    with mp.Pool(n_workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(eval_perm, candidates):
            # log slim version (no full perm/ts/tfs for noise)
            slim = {k: v for k, v in rec.items()
                    if k not in ('perm', 'ts', 'tfs')}
            hist.write(json.dumps(slim) + '\n')
            if rec.get('walk_ok'):
                n_walk_ok += 1
            if 'slsqp_mk' in rec:
                n_slsqp_polished += 1
                if rec.get('slsqp_feas'):
                    n_polished_feas += 1
                    # Save to pool if it's within threshold (re-seed material)
                    if rec['slsqp_mk'] < pool_threshold and rec.get('perm'):
                        pool_fh.write(json.dumps({
                            'slsqp_mk': rec['slsqp_mk'],
                            'walk_mk': rec.get('walk_mk'),
                            'perm': rec['perm'],
                            'ts': rec['ts'], 'tfs': rec['tfs'],
                        }) + '\n')
                        pool_fh.flush()
                        n_pool += 1
                    if rec['slsqp_mk'] < bank_mk - 1e-4:
                        n_under_bank += 1
                        if rec['slsqp_mk'] < best_slsqp[0]:
                            best_slsqp = (rec['slsqp_mk'], rec['perm'],
                                           rec['ts'], rec['tfs'])
                            print(f"  >>> new best slsqp_mk={rec['slsqp_mk']:.4f}d "
                                  f"(cand={rec['cand_id']}, walk_mk={rec['walk_mk']:.4f})",
                                  flush=True)
            if (rec['cand_id'] % 100) == 0:
                elapsed = time.time() - t0
                eta = elapsed / max(rec['cand_id'], 1) * (n_cands - rec['cand_id'])
                print(f"  cand={rec['cand_id']}/{n_cands} elapsed={elapsed:.0f}s "
                      f"eta={eta:.0f}s  walk_ok={n_walk_ok} "
                      f"slsqp_polished={n_slsqp_polished} "
                      f"feas={n_polished_feas} under_bank={n_under_bank}",
                      flush=True)
    hist.close(); pool_fh.close()
    wall = time.time() - t0
    print(f"\n=== E-521 done in {wall/60:.1f}min ===", flush=True)
    print(f"  walk_ok: {n_walk_ok}/{n_cands}", flush=True)
    print(f"  SLSQP-polished: {n_slsqp_polished}", flush=True)
    print(f"  SLSQP-polished feasible: {n_polished_feas}", flush=True)
    print(f"  under bank ({bank_mk:.4f}): {n_under_bank}", flush=True)
    print(f"  best slsqp_mk: {best_slsqp[0]:.4f}d", flush=True)
    print(f"  pool size (mk < {pool_threshold:.4f}): {n_pool}", flush=True)

    banked = False
    if best_slsqp[1] is not None and best_slsqp[0] < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_final = list(best_slsqp[2]) + list(best_slsqp[3]) + \
                  [float(p) for p in best_slsqp[1]]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {best_slsqp[0]:.4f}d "
              f"({bank_mk - best_slsqp[0]:.4f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_entry': float(bank_mk), 'best_slsqp': float(best_slsqp[0]),
        'n_candidates': n_cands, 'n_walk_ok': n_walk_ok,
        'n_slsqp_polished': n_slsqp_polished,
        'n_polished_feasible': n_polished_feas,
        'n_under_bank': n_under_bank,
        'banked': banked, 'wall_min': wall / 60,
    }))


if __name__ == '__main__':
    n_cands = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    n_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    seed_pool = sys.argv[3] if len(sys.argv) > 3 else None
    main(n_cands=n_cands, n_workers=n_workers, seed_pool_path=seed_pool)
