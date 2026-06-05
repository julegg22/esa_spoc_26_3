"""E-519 — Ch2 small: Dijkstra (forward DP) on time-expanded graph,
bank perm fixed.

See vault/experiments/E-030-ch2-dijkstra-bank-perm.md for the
pre-registered hypothesis.

Method:
  State: (step ∈ [0,48], t_bucket ∈ [0,400], exc_used ∈ [0,5]).
  Forward DP using fine-table edges. No tof_window, no wait_steps,
  no greedy commit — exact (within the 0.5 d × ~0.08 d quantum).
  Reconstruct best (times, tofs); validate via kt.fitness; auto-bank
  if UDP-feasible and < 142.8913 d.

Outcomes (pre-registered):
  mk_dij < 142.89 → walk_perm_chrono was suboptimal; new bank.
  mk_dij = 142.89 (±0.5d) → bank is globally optimal on its perm.
  mk_dij > 142.89 → F1 (fine-table grid misses bank's actual cells).
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
BAK = OUT + ".bak.20260602.e519"
FINE = '/tmp/ch2_small_tcoupled_fine.npz'
RESULT = '/tmp/ch2_e519_result.json'
BANK_MK = 142.8913

INF = 10**9


def load_fine_table():
    d = np.load(FINE)
    cheap = d['cheap']       # (n, n, T) — min tof at each t (or nan)
    exc = d['exc']
    t_starts = d['t_starts'] # (T,) — start times, step 0.5 d
    tofs_grid = d['tofs']    # (Tof,) — tof grid (not directly needed)
    return cheap, exc, t_starts, tofs_grid


def precompute_edges(cheap, exc, t_starts, perm, q):
    """For each leg k (perm[k]→perm[k+1]) and each departure bucket t' ∈
    [0, T-1], compute the arrival bucket (rounded up). Returns:
      cheap_arr[k, t'] = arrival_bucket (or INF if no cheap at t')
      exc_arr[k, t']   = arrival_bucket (or INF if no exc at t')
    """
    n_legs = len(perm) - 1
    T = len(t_starts)
    cheap_arr = np.full((n_legs, T), INF, dtype=np.int32)
    exc_arr = np.full((n_legs, T), INF, dtype=np.int32)
    for k in range(n_legs):
        i, j = perm[k], perm[k+1]
        for tp in range(T):
            c_tof = cheap[i, j, tp]
            if np.isfinite(c_tof):
                # arrival quantum = t' + ceil(tof / q)
                arr = tp + int(np.ceil(float(c_tof) / q))
                if arr < T:
                    cheap_arr[k, tp] = arr
            e_tof = exc[i, j, tp]
            if np.isfinite(e_tof):
                arr = tp + int(np.ceil(float(e_tof) / q))
                if arr < T:
                    exc_arr[k, tp] = arr
    return cheap_arr, exc_arr


def forward_dp(cheap_arr, exc_arr, T, n_legs, n_exc_max):
    """Forward DP. State: (step, t_bucket, exc_used).
    Reachable iff predecessor exists.
    Returns:
      reach[k, t, e] bool array
      pred[k, t, e] = (prev_t, prev_e, departure_t', is_exc) or None
    """
    # reach[k, t, e] — bool. We use shape (n_legs+1, T, n_exc_max+1).
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=bool)
    # Predecessor info per reachable (k, t, e): we keep one pred per state.
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_isexc = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)

    reach[0, 0, 0] = True

    for k in range(n_legs):
        # iterate over reachable (t, e) at step k
        ts_e = np.argwhere(reach[k])  # (n_reach, 2): (t, e)
        if ts_e.shape[0] == 0:
            print(f"  WARN step {k}: no reachable states; DP terminates", flush=True)
            break
        for t, e in ts_e:
            t = int(t); e = int(e)
            # cheap transitions: depart at t' ∈ [t, T-1], arrive at cheap_arr[k, t']
            for tp in range(t, T):
                arr = cheap_arr[k, tp]
                if arr < INF and arr < T:
                    if not reach[k+1, arr, e]:
                        reach[k+1, arr, e] = True
                        pred_t[k+1, arr, e] = t
                        pred_e[k+1, arr, e] = e
                        pred_dep[k+1, arr, e] = tp
                        pred_isexc[k+1, arr, e] = 0
            # exc transitions
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
    return reach, pred_t, pred_e, pred_dep, pred_isexc


def backtrack(reach, pred_t, pred_e, pred_dep, pred_isexc, n_legs):
    """Find best sink: min t at (n_legs, t, e) with e ≤ 5.
    Return: (mk_t_bucket, e_used, list[(dep_bucket, arr_bucket, is_exc)])
    """
    sink_reach = reach[n_legs]  # (T, n_exc_max+1)
    # find min t in any e
    finite_ts = np.where(sink_reach.any(axis=1))[0]
    if len(finite_ts) == 0:
        return None
    min_t = int(finite_ts.min())
    # find e
    e_used = int(np.where(sink_reach[min_t])[0].min())
    # backtrack
    legs = []  # list of (dep_bucket, arr_bucket, is_exc)
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


def reconstruct_times_tofs(legs, q):
    """legs[k] = (dep_bucket_k, arr_bucket_k, is_exc_k).
    Returns (times_list, tofs_list) in days.
    times[k] = departure time of leg k (the t at which we depart from
               perm[k] toward perm[k+1]).
    tofs[k]  = arrival - departure in days.
    """
    times = [dep * q for (dep, arr, _) in legs]
    tofs = [(arr - dep) * q for (dep, arr, _) in legs]
    return times, tofs


def main():
    if not Path(FINE).exists():
        print("ERR fine table missing"); return
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    print(f"E-519 Dijkstra. bank perm len={len(bank_perm)} "
          f"start={bank_perm[0]} end={bank_perm[-1]} "
          f"BANK_MK={BANK_MK}", flush=True)

    print("Loading fine table...", flush=True)
    cheap, exc, t_starts, tofs_grid = load_fine_table()
    q = float(t_starts[1] - t_starts[0])
    T = len(t_starts)
    print(f"  T={T} buckets × q={q}d (horizon={T*q}d)", flush=True)
    print(f"  cheap finite cells: {int(np.isfinite(cheap).sum())}", flush=True)
    print(f"  exc   finite cells: {int(np.isfinite(exc).sum())}", flush=True)

    print("\nPrecomputing per-leg arrival buckets...", flush=True)
    t0 = time.time()
    cheap_arr, exc_arr = precompute_edges(cheap, exc, t_starts, bank_perm, q)
    print(f"  done in {time.time()-t0:.2f}s. "
          f"cheap_arr finite per leg: avg={(cheap_arr<INF).sum(axis=1).mean():.1f}, "
          f"min={(cheap_arr<INF).sum(axis=1).min()}, "
          f"max={(cheap_arr<INF).sum(axis=1).max()}", flush=True)
    print(f"  exc_arr  finite per leg: avg={(exc_arr<INF).sum(axis=1).mean():.1f}",
          flush=True)
    # Identify hopeless legs (no feasible transfer ever)
    hopeless = [(k, bank_perm[k], bank_perm[k+1])
                for k in range(len(bank_perm)-1)
                if (cheap_arr[k] >= INF).all() and (exc_arr[k] >= INF).all()]
    if hopeless:
        print(f"  HOPELESS legs (no transfer at any t): {len(hopeless)}", flush=True)
        for k, i, j in hopeless[:5]:
            print(f"    leg {k}: {i}->{j}", flush=True)

    print("\nForward DP...", flush=True)
    t0 = time.time()
    n_legs = len(bank_perm) - 1
    reach, pred_t, pred_e, pred_dep, pred_isexc = forward_dp(
        cheap_arr, exc_arr, T, n_legs, kt.n_exc)
    dp_wall = time.time() - t0
    print(f"  done in {dp_wall:.1f}s", flush=True)

    # Backtrack
    out = backtrack(reach, pred_t, pred_e, pred_dep, pred_isexc, n_legs)
    if out is None:
        print("\n!!! DP found NO feasible sink !!! "
              "Fine-table grid cannot support a full tour on bank perm.",
              flush=True)
        Path(RESULT).write_text(json.dumps({
            'status': 'NO_SINK', 'wall_s': dp_wall,
            'verdict': 'inconclusive (F1)',
            'reason': 'no reachable sink within fine-table grid',
        }))
        return

    min_t_bucket, e_used, legs = out
    mk_dij = min_t_bucket * q
    print(f"\nDP optimum on bank perm: mk_dij = {mk_dij:.3f} d "
          f"(exc_used={e_used}, sink t_bucket={min_t_bucket})", flush=True)
    print(f"vs BANK_MK = {BANK_MK} d → delta = {BANK_MK - mk_dij:+.3f} d", flush=True)

    # Reconstruct (times, tofs)
    times, tofs = reconstruct_times_tofs(legs, q)
    print(f"\nReconstructed schedule:")
    n_exc_legs = sum(1 for (_, _, e) in legs if e == 1)
    print(f"  #exc legs in reconstruction: {n_exc_legs}", flush=True)
    print(f"  first 5 legs (dep_d, tof_d, isexc): "
          f"{[(round(times[k],3), round(tofs[k],3), legs[k][2]) for k in range(5)]}",
          flush=True)
    print(f"  last 5 legs: "
          f"{[(round(times[k],3), round(tofs[k],3), legs[k][2]) for k in range(len(legs)-5, len(legs))]}",
          flush=True)

    # UDP validation
    print(f"\nValidating reconstructed (times, tofs) via UDP fitness...", flush=True)
    x = list(times) + list(tofs) + [float(p) for p in bank_perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    udp_mk = float(fit[0]) if hasattr(fit, '__len__') and len(fit) > 0 else float(fit)
    print(f"  UDP fitness: {fit} (feasible={feas})", flush=True)
    print(f"  UDP makespan: {udp_mk:.4f} d", flush=True)

    # Compare to walk_perm_chrono on the same perm (for context)
    print(f"\nFor reference — walk_perm_chrono on bank perm:", flush=True)
    for label, kw in [('S1 wait_dt=1.0', dict(tof_window=18.0, n_steps=180, wait_steps=12, wait_dt=1.0)),
                       ('S2 wait_dt=0.2', dict(tof_window=18.0, n_steps=360, wait_steps=60, wait_dt=0.2))]:
        ts, tfs, dvs, ok, exc_n, last = walk_perm_chrono(kt, bank_perm, **kw)
        if ok:
            wmk = ts[-1] + tfs[-1]
            print(f"  {label}: mk={wmk:.3f}d  exc_used={exc_n}", flush=True)
        else:
            print(f"  {label}: REJECTED at leg {last}", flush=True)

    # Verdict
    if not feas:
        verdict = 'inconclusive (F2)'
        msg = (f"DP found mk_dij={mk_dij:.3f}d but UDP rejects "
               f"reconstructed (times,tofs) — fine-table cell is finite "
               f"but real Lambert is sub-threshold.")
    elif udp_mk < BANK_MK - 0.001:
        verdict = 'refutes evaluator-optimality of walk_perm_chrono'
        msg = (f"UDP mk={udp_mk:.4f}d < bank {BANK_MK} → "
               f"walk_perm_chrono was suboptimal; banking new value.")
    elif udp_mk <= BANK_MK + 0.5:
        verdict = 'supports walk_perm_chrono≈optimal on bank perm'
        msg = (f"UDP mk={udp_mk:.4f}d ≈ bank — bank is globally "
               f"optimal on its perm within fine-grid quantum.")
    else:
        verdict = 'inconclusive (F1)'
        msg = (f"UDP mk={udp_mk:.4f}d > bank by >0.5d — DP missed a "
               f"better schedule; F1 (fine-table grid coverage).")

    print(f"\n=== E-519 VERDICT ===", flush=True)
    print(verdict, flush=True)
    print(msg, flush=True)

    # Auto-bank if better
    banked = False
    if feas and udp_mk < BANK_MK:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x,
            'problem': 'small', 'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {udp_mk:.4f}d ({BANK_MK - udp_mk:.4f}d under prev)",
              flush=True)

    Path(RESULT).write_text(json.dumps({
        'mk_dij_d': float(mk_dij),
        'udp_mk_d': float(udp_mk),
        'udp_feasible': feas,
        'e_used': int(e_used),
        'dp_wall_s': float(dp_wall),
        'verdict': verdict,
        'msg': msg,
        'banked': banked,
        'bank_was': BANK_MK,
        'perm_start': int(bank_perm[0]),
        'perm_end': int(bank_perm[-1]),
        'n_exc_legs_in_dp_reconstruction': int(n_exc_legs),
        'first_5_legs': [(round(times[k],3), round(tofs[k],3), int(legs[k][2]))
                          for k in range(5)],
    }))


if __name__ == '__main__':
    main()
