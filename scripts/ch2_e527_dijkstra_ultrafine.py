"""E-527 — Ch2 small: forward DP on ULTRAFINE (0.05 d) time-coupled table (B).

Fixes E-519's two bugs:
  1. The 0.5 d quantum was too coarse to represent bank's continuous t
     (bank's actual times[1]=0.05 d falls between buckets). The 0.05 d
     ultrafine table from E-526 resolves this.
  2. Reconstruction used (arr_bucket - dep_bucket) × q as tof, which is
     wrong (the actual tof is the fine-table value, not the bucket gap).
     This script stores and uses the ACTUAL tof per transition.

Decisive question: does the provable global optimum on bank perm under
the 0.05 d Lambert grid beat 142.2897 d?
  YES → walk_perm_chrono + SLSQP is locally optimal but not globally; new bank.
  NO  → bank IS globally optimal on its perm; the bottleneck IS perm choice.

Input: /tmp/ch2_small_tcoupled_ultrafine.npz (from E-526)
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260605.e527"
FINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
RESULT = '/tmp/ch2_e527_result.json'

BANK_MK = 142.2897
INF = 10**9


def precompute_edges(cheap, exc, perm, q):
    """For leg k and dep bucket t', compute (arr_bucket, tof) for cheap and exc.
    Returns 4 arrays: cheap_arr[k,t'], cheap_tof[k,t'], exc_arr, exc_tof.
    arr = INF if no transfer at that (i,j,t').
    """
    n_legs = len(perm) - 1
    T = cheap.shape[2]
    cheap_arr = np.full((n_legs, T), INF, dtype=np.int32)
    cheap_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    exc_arr = np.full((n_legs, T), INF, dtype=np.int32)
    exc_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    for k in range(n_legs):
        i, j = perm[k], perm[k+1]
        c_row = cheap[i, j]
        e_row = exc[i, j]
        for tp in range(T):
            ct = c_row[tp]
            if np.isfinite(ct):
                cheap_tof[k, tp] = ct
                arr = tp + int(np.ceil(float(ct) / q))
                if arr < T:
                    cheap_arr[k, tp] = arr
            et = e_row[tp]
            if np.isfinite(et):
                exc_tof[k, tp] = et
                arr = tp + int(np.ceil(float(et) / q))
                if arr < T:
                    exc_arr[k, tp] = arr
    return cheap_arr, cheap_tof, exc_arr, exc_tof


def forward_dp(cheap_arr, exc_arr, T, n_legs, n_exc_max):
    """Forward DP. State: (step, t_bucket, exc_used).
    Reachable iff predecessor exists. Records best predecessor."""
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=bool)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_isexc = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True

    for k in range(n_legs):
        ts_e = np.argwhere(reach[k])
        if ts_e.shape[0] == 0:
            print(f"  WARN step {k}: no reachable states; DP terminates",
                  flush=True)
            return reach, pred_t, pred_e, pred_dep, pred_isexc, k
        if k % 8 == 0:
            print(f"  step {k:2d}: {ts_e.shape[0]} reachable states",
                  flush=True)
        for t, e in ts_e:
            t = int(t); e = int(e)
            for tp in range(t, T):
                arr = cheap_arr[k, tp]
                if arr < INF and arr < T:
                    if not reach[k+1, arr, e]:
                        reach[k+1, arr, e] = True
                        pred_t[k+1, arr, e] = t
                        pred_e[k+1, arr, e] = e
                        pred_dep[k+1, arr, e] = tp
                        pred_isexc[k+1, arr, e] = 0
            if e < n_exc_max:
                for tp in range(t, T):
                    arr = exc_arr[k, tp]
                    if arr < INF and arr < T:
                        if not reach[k+1, arr, e+1]:
                            reach[k+1, arr, e+1] = True
                            pred_t[k+1, arr, e+1] = t
                            pred_e[k+1, arr, e+1] = e
                            pred_dep[k+1, arr, e+1] = tp
                            pred_isexc[k+1, arr, e+1] = 1
    return reach, pred_t, pred_e, pred_dep, pred_isexc, n_legs


def backtrack(reach, pred_t, pred_e, pred_dep, pred_isexc, n_legs):
    sink = reach[n_legs]
    finite_ts = np.where(sink.any(axis=1))[0]
    if len(finite_ts) == 0:
        return None
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
    return min_t, e_used, legs


def reconstruct_times_tofs_actual(legs, cheap_tof, exc_tof, q):
    """For each leg (dep_bucket, arr_bucket, isexc), use the actual
    tof from the fine table — NOT the bucket gap (E-519's bug)."""
    times = [dep * q for (dep, arr, _) in legs]
    tofs = []
    for k, (dep, arr, isexc) in enumerate(legs):
        tof = float(exc_tof[k, dep] if isexc else cheap_tof[k, dep])
        tofs.append(tof)
    return times, tofs


def main():
    if not Path(FINE).exists():
        print(f"ERR ultrafine table missing: {FINE}", flush=True); return
    print("Loading ultrafine table...", flush=True)
    t0 = time.time()
    d = np.load(FINE)
    cheap = d['cheap']; exc = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0])
    T = len(t_starts)
    print(f"  loaded in {time.time()-t0:.1f}s. shape={cheap.shape} "
          f"q={q}d T={T} horizon={T*q}d", flush=True)
    n_cheap = int(np.isfinite(cheap).sum())
    n_exc = int(np.isfinite(exc).sum())
    print(f"  cheap cells: {n_cheap} ({n_cheap/cheap.size*100:.2f}%)",
          flush=True)
    print(f"  exc   cells: {n_exc} ({n_exc/exc.size*100:.2f}%)", flush=True)

    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    n_legs = len(bank_perm) - 1
    print(f"\nBank perm: start={bank_perm[0]} end={bank_perm[-1]} "
          f"n_legs={n_legs}", flush=True)

    print("\nPrecomputing per-leg arrival buckets + actual tofs...",
          flush=True)
    t0 = time.time()
    c_arr, c_tof, e_arr, e_tof = precompute_edges(cheap, exc, bank_perm, q)
    print(f"  done in {time.time()-t0:.1f}s", flush=True)
    hopeless = [k for k in range(n_legs)
                if (c_arr[k] >= INF).all() and (e_arr[k] >= INF).all()]
    if hopeless:
        print(f"  HOPELESS legs: {len(hopeless)} → {hopeless[:5]}", flush=True)

    print("\nForward DP (this may take a few minutes due to large T)...",
          flush=True)
    t0 = time.time()
    reach, pred_t, pred_e, pred_dep, pred_isexc, last_k = forward_dp(
        c_arr, e_arr, T, n_legs, kt.n_exc)
    dp_wall = time.time() - t0
    print(f"  done in {dp_wall:.1f}s. last reachable step: {last_k}",
          flush=True)

    out = backtrack(reach, pred_t, pred_e, pred_dep, pred_isexc, n_legs)
    if out is None:
        print(f"\n!!! DP found NO feasible sink at step {n_legs}", flush=True)
        Path(RESULT).write_text(json.dumps({
            'status': 'NO_SINK', 'wall_s': dp_wall, 'verdict': 'F1 redux',
        }))
        return

    min_t_bucket, e_used, legs = out
    mk_dij_bucket = min_t_bucket * q
    print(f"\nDP optimum on bank perm: mk_dij (bucket-quantized) = "
          f"{mk_dij_bucket:.4f}d (exc_used={e_used}, sink_bucket={min_t_bucket})",
          flush=True)

    times, tofs = reconstruct_times_tofs_actual(legs, c_tof, e_tof, q)
    # Verify chronology and recompute actual makespan
    n_exc_legs = sum(1 for (_, _, isexc) in legs if isexc == 1)
    print(f"  n_exc_legs in DP reconstruction: {n_exc_legs}", flush=True)
    print(f"  first 5 legs (dep_d, tof_d, isexc): "
          f"{[(round(times[k],4), round(tofs[k],4), legs[k][2]) for k in range(5)]}",
          flush=True)

    # Validate via UDP fitness
    print(f"\nValidating reconstructed (times, tofs) via UDP fitness...",
          flush=True)
    x = list(times) + list(tofs) + [float(p) for p in bank_perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    udp_mk = float(fit[0])
    print(f"  UDP fitness: {fit} (feasible={feas})", flush=True)
    print(f"  UDP makespan: {udp_mk:.6f}d", flush=True)
    print(f"  vs BANK = {BANK_MK}d → delta = {BANK_MK - udp_mk:+.4f}d",
          flush=True)

    # Verdict
    if not feas:
        verdict = f"F2 — DP found mk={udp_mk:.4f}d but UDP rejects"
        msg = ('DP optimum schedule is UDP-infeasible. Likely the fine '
               'table marks a cell finite that real Lambert rejects '
               '(precompute boundary bug).')
    elif udp_mk < BANK_MK - 1e-4:
        verdict = 'refutes bank-as-perm-loc-opt — new bank candidate'
        msg = (f'DP found UDP-feasible mk={udp_mk:.4f}d < bank '
               f'{BANK_MK}d. The SLSQP-polish bank was locally optimal '
               f'but not globally on its perm.')
    elif abs(udp_mk - BANK_MK) < 0.05:
        verdict = 'supports bank-as-perm-loc-opt (within fine quantum)'
        msg = (f'DP found UDP-feasible mk={udp_mk:.4f}d ≈ bank. Bank IS '
               f'globally optimal on its perm; bottleneck is perm choice.')
    else:
        verdict = 'inconclusive — DP higher than bank by > 0.05 d'
        msg = (f'DP found {udp_mk:.4f}d > bank by '
               f'{udp_mk - BANK_MK:.4f}d. Bank schedule outside fine grid.')

    print(f"\n=== E-527 VERDICT ===", flush=True)
    print(verdict, flush=True)
    print(msg, flush=True)

    banked = False
    if feas and udp_mk < BANK_MK - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x, 'problem': 'small', 'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {udp_mk:.6f}d "
              f"({BANK_MK - udp_mk:.4f}d under prev)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'mk_dij_bucket_d': float(mk_dij_bucket),
        'udp_mk_d': float(udp_mk),
        'udp_feasible': feas,
        'e_used': int(e_used),
        'n_exc_legs': n_exc_legs,
        'dp_wall_s': float(dp_wall),
        'verdict': verdict, 'msg': msg,
        'banked': banked, 'bank_was': BANK_MK,
        'q_quantum_d': q, 'T': T,
    }))


if __name__ == '__main__':
    main()
