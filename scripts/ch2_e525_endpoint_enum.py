"""E-525 — Ch2 small: 6-endpoint configuration enumeration with SLSQP polish (C).

Bank uses (start_comp=comp3, end_comp=comp2) — 1 of 6 valid endpoint configs
under the K-1=3 inter-comp rule. The original E-028 tested only this config
under walk_perm_chrono (which is broken; see E-519b). Re-test all 6 configs
with the SLSQP-polish evaluator.

For each (s_start, s_end) ∈ {(1,2),(1,3),(2,1),(2,3),(3,1),(3,2)}
(where comp1={4,11,17}, comp2={16,27,32}, comp3={18,23,34}):
  For each start_node ∈ s_start (3 options):
    For each end_node ∈ s_end (3 options):
      For each ordering of remaining s_start nodes (2 options):
        For each ordering of remaining s_end nodes (2 options):
          Build candidate perm:
            [start_triplet] + [bank's mid, preserving relative order] + [end_triplet]
          where bank's mid = bank perm minus {start_triplet ∪ end_triplet}.
          Walk → SLSQP polish.
          Bank if mk < 142.2897.

Total: 6 × 3 × 3 × 2 × 2 = 216 candidates.
"""
from __future__ import annotations
import sys, os, json, time
from itertools import permutations
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
BAK = OUT + ".bak.20260604.e525"
RESULT = '/tmp/ch2_e525_result.json'
HIST = '/tmp/ch2_e525_history.jsonl'

DV_CHEAP = 100.0
DV_EXC = 600.0
TOF_MIN = 0.001
TOF_MAX = 8.0
MAX_T = 200.0
PEN_CHRONO = 1e6
PEN_DV = 1e4

# Verified small-comp memberships (audit + today's diagnostics)
COMP_NODES = {
    1: [4, 11, 17],
    2: [16, 27, 32],
    3: [18, 23, 34],
}
ENDPOINT_PAIRS = [(1,2),(1,3),(2,1),(2,3),(3,1),(3,2)]

_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)


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


def slsqp_polish(kt, perm, times0, tofs0, exc_set, maxiter=150):
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
    fit = kt.fitness(ts + tfs + [float(p) for p in perm])
    feas = bool(kt.is_feasible(fit))
    return (ts, tfs), (float(fit[0]) if len(fit) > 0 else 1e9), feas


def build_candidate(bank_perm, start_triplet, end_triplet):
    """Build candidate perm: start_triplet + bank's mid (rel order) + end_triplet."""
    start_set = set(start_triplet)
    end_set = set(end_triplet)
    mid = [v for v in bank_perm if v not in start_set and v not in end_set]
    return list(start_triplet) + mid + list(end_triplet)


def eval_candidate(args):
    cand_id, perm = args
    kt = _GLOB['kt']
    rec = {'cand_id': cand_id, 'start': perm[0], 'end': perm[-1]}
    try:
        ts, tfs, dvs, ok, exc_n, last = walk_perm_chrono(
            kt, perm, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
    except Exception as e:
        rec['walk_err'] = str(e)[:60]; return rec
    if not ok:
        rec['walk_ok'] = False; rec['walk_last_leg'] = int(last); return rec
    walk_mk = ts[-1] + tfs[-1]
    rec['walk_ok'] = True
    rec['walk_mk'] = float(walk_mk)
    rec['walk_exc'] = int(exc_n)
    if walk_mk > 200.0 or exc_n > kt.n_exc:
        return rec
    exc_set = {k for k in range(len(perm)-1) if dvs[k] > DV_CHEAP + 1e-6}
    res, slsqp_mk, feas = slsqp_polish(kt, perm, ts, tfs, exc_set)
    rec['slsqp_mk'] = slsqp_mk; rec['slsqp_feas'] = feas
    if feas:
        rec['perm'] = perm; rec['ts'] = res[0]; rec['tfs'] = res[1]
    return rec


def main(n_workers=6):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(bank[0]['decisionVector'])[0])
    print(f"E-525 endpoint-config enumeration. bank_mk={bank_mk:.4f}d  "
          f"start={bank_perm[0]} end={bank_perm[-1]}", flush=True)

    candidates = []
    cid = 0
    for s_start, s_end in ENDPOINT_PAIRS:
        nodes_start = COMP_NODES[s_start]
        nodes_end = COMP_NODES[s_end]
        for start_node in nodes_start:
            others_start = [v for v in nodes_start if v != start_node]
            # 2 orderings of the other 2 start-comp nodes
            for s_order in permutations(others_start):
                for end_node in nodes_end:
                    others_end = [v for v in nodes_end if v != end_node]
                    for e_order in permutations(others_end):
                        start_triplet = [start_node, s_order[0], s_order[1]]
                        end_triplet = [e_order[0], e_order[1], end_node]
                        perm = build_candidate(bank_perm, start_triplet,
                                                end_triplet)
                        if len(set(perm)) != n:
                            continue
                        candidates.append((cid, perm))
                        cid += 1
    print(f"Total candidates: {len(candidates)} = 6 configs × 3 starts "
          f"× 2 start-orders × 3 ends × 2 end-orders", flush=True)

    best = (bank_mk, None, None, None, None, None)  # (mk, perm, ts, tfs, start, end)
    n_walk_ok = 0; n_polished = 0; n_feas = 0; n_under_bank = 0
    t0 = time.time()
    hist = open(HIST, 'w')
    with mp.Pool(n_workers, initializer=_init) as pool:
        for rec in pool.imap_unordered(eval_candidate, candidates):
            slim = {k: v for k, v in rec.items()
                    if k not in ('perm', 'ts', 'tfs')}
            hist.write(json.dumps(slim) + '\n'); hist.flush()
            if rec.get('walk_ok'): n_walk_ok += 1
            if 'slsqp_mk' in rec:
                n_polished += 1
                if rec.get('slsqp_feas'):
                    n_feas += 1
                    print(f"  cid={rec['cand_id']:3d} "
                          f"start={rec['start']:2d} end={rec['end']:2d} "
                          f"walk={rec['walk_mk']:7.2f} → "
                          f"slsqp={rec['slsqp_mk']:7.4f}d feas=YES",
                           flush=True)
                    if rec['slsqp_mk'] < bank_mk - 1e-4:
                        n_under_bank += 1
                        if rec['slsqp_mk'] < best[0]:
                            best = (rec['slsqp_mk'], rec['perm'],
                                     rec['ts'], rec['tfs'],
                                     rec['start'], rec['end'])
                            print(f"    >>> NEW BEST: {best[0]:.4f}d",
                                   flush=True)
    hist.close()
    wall = time.time() - t0
    print(f"\n=== E-525 done in {wall:.0f}s ===", flush=True)
    print(f"  walk-feasible: {n_walk_ok}/{len(candidates)}", flush=True)
    print(f"  polished-feasible: {n_feas}", flush=True)
    print(f"  under bank ({bank_mk:.4f}): {n_under_bank}", flush=True)
    print(f"  best mk: {best[0]:.4f}d (start={best[4]}, end={best[5]})",
          flush=True)

    banked = False
    if best[1] is not None and best[0] < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_final = list(best[2]) + list(best[3]) + [float(p) for p in best[1]]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {best[0]:.4f}d  start={best[4]} end={best[5]}  "
              f"({bank_mk - best[0]:.4f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_entry': float(bank_mk), 'best': float(best[0]),
        'best_start': int(best[4]) if best[4] is not None else None,
        'best_end': int(best[5]) if best[5] is not None else None,
        'n_candidates': len(candidates),
        'n_walk_ok': n_walk_ok, 'n_polished': n_polished,
        'n_feasible': n_feas, 'n_under_bank': n_under_bank,
        'banked': banked, 'wall_s': wall,
    }))


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    main(n_workers=nw)
