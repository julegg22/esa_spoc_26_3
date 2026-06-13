"""E-550 — Ch2 medium: walk+SLSQP-polished ALNS with M5 operator (no DP table).

The medium DP-on-fine-table approach stalled at 228.97 d (E-543, E-545,
E-549 all gave 0 bankings). Hypothesis: M5's 58 % walk-feasibility doesn't
translate to DP-competitive schedules because the curated 4686-pair table
restricts ALNS. Walk+SLSQP eval uses continuous t (no table restriction)
and may find improvements DP misses.

Architecture (mirrors small E-521):
  - M5 bridge-swap primary (60 %), M2 intra-seg-rev (20 %), M1 intra-swap (15 %), random (5 %)
  - walk_perm_chrono → if walk_mk < bank+30: SLSQP polish 96-dim (times, tofs)
  - Penalty-based objective (dv constraints, chronology)
  - 4 chains × 24 h budget
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
        "problems/medium.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
BAK = OUT + ".bak.20260610.e550"
COARSE = '/tmp/ch2_medium_tcoupled.npz'
CKPT_TMPL = '/tmp/ch2_e550_ckpt_chain{}.json'

DV_CHEAP = 100.0; DV_EXC = 600.0
TOF_MIN = 0.001; TOF_MAX = 12.0
MAX_T = 500.0
PEN_CHRONO = 1e6; PEN_DV = 1e4

SA_T0 = 5.0
SA_DECAY = 0.99995
WALK_THRESHOLD = 330.0   # skip SLSQP if walk_mk above this
CKPT_INTERVAL_S = 600
RESEED_INTERVAL_S = 6 * 3600


def get_components(coarse_path):
    d = np.load(coarse_path)
    cheap = d['cheap']
    cheap_min = np.nanmin(cheap, axis=2)
    n = cheap_min.shape[0]
    np.fill_diagonal(cheap_min, np.inf)
    adj_sym = np.isfinite(cheap_min) | np.isfinite(cheap_min.T)
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym), directed=False)
    sizes = sorted([(int((lbl==c).sum()), c) for c in range(nc)], reverse=True)
    comp_rank = {sizes[r][1]: r for r in range(nc)}
    return {i: comp_rank[int(lbl[i])] for i in range(n)}


def identify_bridges(kt, perm, times, tofs_b, node_comp):
    bridges = []
    for k in range(len(perm) - 1):
        i, j = perm[k], perm[k+1]
        dv_k = float(kt.compute_transfer(i, j, times[k], tofs_b[k]))
        if dv_k > 100.001 and node_comp[i] != node_comp[j]:
            bridges.append(k)
    return bridges


# ── Operators ───────────────────────────────────────────────────────
def m5(perm, node_comp, bridge_positions, rng):
    n = len(perm)
    if not bridge_positions: return list(perm)
    p = list(perm)
    for _ in range(rng.randint(1, 3)):
        k = rng.choice(bridge_positions)
        target_comp = node_comp[p[k]]
        cand = [m for m in range(1, n-1)
                if m != k and node_comp[p[m]] == target_comp]
        if not cand: continue
        m = rng.choice(cand)
        p[k], p[m] = p[m], p[k]
    return p


def m2(perm, node_comp, rng):
    n = len(perm); p = list(perm)
    for _ in range(rng.randint(2, 5)):
        for _ in range(20):
            i = rng.randint(1, n-4)
            L = rng.randint(3, 12)
            j = min(i + L, n - 2)
            if all(node_comp[p[k]] == node_comp[p[i]] for k in range(i, j+1)):
                p = p[:i] + p[i:j+1][::-1] + p[j+1:]
                break
    return p


def m1(perm, node_comp, comp_nodes, rng):
    n = len(perm); p = list(perm)
    for _ in range(rng.randint(3, 8)):
        c = rng.choice(list(comp_nodes.keys()))
        same = [k for k in range(1, n-1) if node_comp[p[k]] == c]
        if len(same) < 2: continue
        i, j = rng.sample(same, 2)
        p[i], p[j] = p[j], p[i]
    return p


def m_random(perm, rng):
    n = len(perm); p = list(perm)
    for _ in range(rng.randint(2, 5)):
        i = rng.randint(1, n-2); j = rng.randint(1, n-2)
        if i != j: p[i], p[j] = p[j], p[i]
    return p


# ── walk + SLSQP polish ─────────────────────────────────────────────
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


def slsqp_polish(kt, perm, t0, tof0, exc_set, maxiter=80):
    n_legs = len(perm) - 1
    x0 = np.array(list(t0) + list(tof0))
    bounds = [(0, MAX_T)] * n_legs + [(TOF_MIN, TOF_MAX)] * n_legs
    f = make_obj(kt, perm, exc_set)
    try:
        r = minimize(f, x0, method='SLSQP', bounds=bounds,
                     options={'maxiter': maxiter, 'ftol': 1e-6})
    except Exception:
        return None, 1e9, False
    x = r.x
    ts = list(x[:n_legs]); tfs = list(x[n_legs:])
    fit = kt.fitness(ts + tfs + [float(p) for p in perm])
    feas = bool(kt.is_feasible(fit))
    return (ts, tfs), (float(fit[0]) if len(fit) > 0 else 1e9), feas


def walk_polish(kt, perm):
    """walk_perm_chrono → if competitive, SLSQP-polish. Returns dict or None."""
    try:
        ts, tfs, dvs, ok, exc_n, _ = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception:
        return None
    if not ok or exc_n > kt.n_exc: return None
    walk_mk = ts[-1] + tfs[-1]
    if walk_mk > WALK_THRESHOLD: return {'walk_mk': walk_mk, 'polished': False}
    exc_set = {k for k in range(len(perm)-1) if dvs[k] > DV_CHEAP + 1e-6}
    res, mk, feas = slsqp_polish(kt, perm, ts, tfs, exc_set)
    if not feas: return {'walk_mk': walk_mk, 'polished': False}
    return {'walk_mk': walk_mk, 'mk': mk, 'times': res[0], 'tofs': res[1],
            'polished': True, 'feas': True}


# ── ALNS chain ──────────────────────────────────────────────────────
def alns_chain(args):
    chain_id, max_wall_s, bank_path, node_comp, comp_nodes, bridge_positions = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(chain_id * 9907 + 89)
    log = lambda m: print(f"[c{chain_id}] {m}", flush=True)

    bank = json.load(open(bank_path))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    # SA baseline must be in the walk+SLSQP metric, not the bank's DP mk —
    # walk eval of the bank perm is ~274.7d, so a DP baseline of 228.97 makes
    # every delta huge-positive and the chain can never accept (E-550 bug).
    init = walk_polish(kt, perm)
    if init is not None and init.get('polished'):
        state = {'perm': perm, 'mk': init['mk'],
                 'times': init['times'], 'tofs': init['tofs']}
    else:
        state = {'perm': perm, 'mk': bank_mk,
                 'times': list(dv[:n-1]), 'tofs': list(dv[n-1:2*(n-1)])}
    best_local = dict(state)
    log(f"init bank dp_mk={bank_mk:.4f}d sa_baseline={state['mk']:.4f}d")

    ckpt = CKPT_TMPL.format(chain_id)
    if Path(ckpt).exists():
        try:
            ck = json.load(open(ckpt))
            if ck['perm'] and len(ck['perm']) == n:
                state = ck
                if ck['mk'] < best_local['mk']: best_local = dict(state)
                log(f"resumed mk={state['mk']:.4f}d")
        except Exception: pass

    sa_temp = SA_T0
    iter_count = 0; n_walk_ok = 0; n_polish_feas = 0; n_accepted = 0
    op_counts = {}; op_accepts = {}
    t0 = time.time(); last_ckpt = time.time(); last_reseed = time.time()
    hist_fh = open(f'/tmp/ch2_e550_chain{chain_id}_hist.jsonl', 'a')

    while time.time() - t0 < max_wall_s:
        iter_count += 1
        sa_temp *= SA_DECAY

        op = rng.choices(['M5', 'M2', 'M1', 'random'],
                          weights=[60, 20, 15, 5])[0]
        op_counts[op] = op_counts.get(op, 0) + 1
        if op == 'M5':
            new_perm = m5(state['perm'], node_comp, bridge_positions, rng)
        elif op == 'M2':
            new_perm = m2(state['perm'], node_comp, rng)
        elif op == 'M1':
            new_perm = m1(state['perm'], node_comp, comp_nodes, rng)
        else:
            new_perm = m_random(state['perm'], rng)
        if len(set(new_perm)) != n: continue

        result = walk_polish(kt, new_perm)
        if result is None: continue
        n_walk_ok += 1
        if not result.get('polished'): continue
        n_polish_feas += 1
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
                        bp = bank_path + ".bak.e550"
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

        if iter_count % 50 == 0:
            elapsed = time.time() - t0
            log(f"iter={iter_count} elapsed={elapsed/60:.1f}min "
                f"walk_ok={n_walk_ok} polish_feas={n_polish_feas} "
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
                dv2 = cur[0]['decisionVector']
                perm2 = [int(x) for x in dv2[2*(n-1):]]
                if perm2 != state['perm']:
                    re = walk_polish(kt, perm2)
                    if re is not None and re.get('polished') and \
                            re['mk'] < best_local['mk'] - 0.1:
                        state = {'perm': perm2, 'mk': re['mk'],
                                 'times': re['times'], 'tofs': re['tofs']}
                        best_local = dict(state)
                        sa_temp = SA_T0
                        log(f"reseeded from global walk_mk={re['mk']:.4f}")
            except Exception: pass
            last_reseed = time.time()

    hist_fh.close()
    log(f"chain done. iters={iter_count} best={best_local['mk']:.4f}d")
    for op in op_counts:
        ac = op_accepts.get(op, 0); ct = op_counts[op]
        log(f"  {op}: {ac}/{ct} ({ac/max(ct,1)*100:.1f}%)")
    return chain_id, best_local


def main(n_chains: int = 4, wall_h: float = 24.0):
    print(f"E-550 medium walk+SLSQP ALNS. n_chains={n_chains} wall_h={wall_h}",
          flush=True)
    kt = KTTSP(INST); n = kt.n
    node_comp = get_components(COARSE)
    comp_nodes = {c: [i for i in range(n) if node_comp[i] == c]
                  for c in set(node_comp.values())}
    sizes = sorted([len(v) for v in comp_nodes.values()], reverse=True)
    print(f"  components: {sizes}", flush=True)

    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    times = list(dv[:n-1]); tofs_b = list(dv[n-1:2*(n-1)])
    bridge_positions = identify_bridges(kt, perm, times, tofs_b, node_comp)
    print(f"  bridge positions: {bridge_positions}", flush=True)

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
