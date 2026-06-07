"""E-541 — Ch2 medium: DP eval on bank perm using per-leg fine table.

After E-540 builds /tmp/ch2_medium_bank_pairs_fine.npz, this script
runs the forward DP on bank's perm using the FINE per-leg cost data
(stored at 0.1 d t-quantum, 5× finer than the production coarse 0.5 d
table). Compares to walk_perm_chrono's 274.52 d.

Differences from E-527/E-532:
  - The per-leg table is keyed by LEG INDEX (not by (i,j)) since it
    was built specifically for bank perm.
  - The DP is structurally identical to E-527's: forward sweep on
    (step, t_bucket, exc_used) states; uses the per-leg actual tofs
    for reconstruction (not bucket gaps).
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from numba import njit

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
BAK = OUT + ".bak.20260608.e541"
FINE = '/tmp/ch2_medium_bank_pairs_fine.npz'
RESULT = '/tmp/ch2_e541_result.json'

R3_MEDIUM = 216.95
R1_MEDIUM = 199.74
INF_INT = 10**9


def precompute_edges_per_leg(cheap, exc, q, T):
    """For each leg k and dep bucket t', compute (arr_bucket, actual_tof).
    Different from generic dp_numba because the input is already per-leg-indexed.
    """
    n_legs = cheap.shape[0]
    c_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, T), INF_INT, dtype=np.int32)
    e_tof = np.full((n_legs, T), np.nan, dtype=np.float32)
    for k in range(n_legs):
        c_row = cheap[k]; e_row = exc[k]
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


@njit(cache=True)
def forward_dp(c_arr, e_arr, T, n_legs, n_exc_max):
    reach = np.zeros((n_legs + 1, T, n_exc_max + 1), dtype=np.bool_)
    pred_t = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    pred_dep = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int32)
    pred_isexc = np.full((n_legs + 1, T, n_exc_max + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True

    for k in range(n_legs):
        any_reach = False
        for t in range(T):
            for e in range(n_exc_max + 1):
                if not reach[k, t, e]:
                    continue
                any_reach = True
                for tp in range(t, T):
                    arr = c_arr[k, tp]
                    if arr < INF_INT and arr < T:
                        if not reach[k+1, arr, e]:
                            reach[k+1, arr, e] = True
                            pred_t[k+1, arr, e] = t
                            pred_e[k+1, arr, e] = e
                            pred_dep[k+1, arr, e] = tp
                            pred_isexc[k+1, arr, e] = 0
                if e < n_exc_max:
                    for tp in range(t, T):
                        arr = e_arr[k, tp]
                        if arr < INF_INT and arr < T:
                            if not reach[k+1, arr, e+1]:
                                reach[k+1, arr, e+1] = True
                                pred_t[k+1, arr, e+1] = t
                                pred_e[k+1, arr, e+1] = e
                                pred_dep[k+1, arr, e+1] = tp
                                pred_isexc[k+1, arr, e+1] = 1
        if not any_reach:
            break
    return reach, pred_t, pred_e, pred_dep, pred_isexc


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


def reconstruct_times_tofs(legs, c_tof, e_tof, q):
    times = [leg[0] * q for leg in legs]
    tofs = []
    for k, (dep, arr, isexc) in enumerate(legs):
        tof = float(e_tof[k, dep] if isexc else c_tof[k, dep])
        tofs.append(tof)
    return times, tofs


def main():
    if not Path(FINE).exists():
        print(f"ERR per-leg fine table missing: {FINE} (run E-540 first)",
              flush=True); return
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    print(f"E-541 medium bank DP-fine. bank_mk={bank_mk:.4f}d", flush=True)

    print("Loading per-leg fine table...", flush=True)
    d = np.load(FINE)
    cheap = d['cheap']; exc = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    print(f"  shape cheap={cheap.shape} q={q}d T={T}", flush=True)
    n_cheap = int(np.isfinite(cheap).sum())
    n_exc = int(np.isfinite(exc).sum())
    print(f"  cheap cells: {n_cheap}/{cheap.size} "
          f"({n_cheap/cheap.size*100:.1f}%)", flush=True)
    print(f"  exc   cells: {n_exc}/{exc.size} "
          f"({n_exc/exc.size*100:.1f}%)", flush=True)
    # Verify perm match
    saved_perm = d['perm'].tolist()
    if saved_perm != perm:
        print(f"  WARN: saved table perm != current bank perm. Aborting.",
              flush=True)
        return

    n_legs = len(perm) - 1
    print(f"\nPrecomputing per-leg arr buckets...", flush=True)
    t0 = time.time()
    c_arr, c_tof, e_arr, e_tof = precompute_edges_per_leg(cheap, exc, q, T)
    print(f"  done in {time.time()-t0:.1f}s", flush=True)

    print(f"Forward DP (numba-jit warmup may take 5-10s)...", flush=True)
    t0 = time.time()
    reach, pt, pe, pd, pi = forward_dp(c_arr, e_arr, T, n_legs, kt.n_exc)
    print(f"  DP done in {time.time()-t0:.1f}s", flush=True)

    out = backtrack(reach, pt, pe, pd, pi, n_legs)
    if out is None:
        print(f"\n!!! DP found NO feasible sink", flush=True)
        Path(RESULT).write_text(json.dumps({
            'bank_was': bank_mk, 'status': 'NO_SINK'}))
        return
    min_t, e_used, legs = out
    times, tofs = reconstruct_times_tofs(legs, c_tof, e_tof, q)
    print(f"\nDP optimum (bucket-q): {min_t * q:.4f}d (exc={e_used})",
          flush=True)

    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk_udp = float(fit[0])
    print(f"UDP-validated mk: {mk_udp:.4f}d feasible={feas} "
          f"viols={fit[1:]}", flush=True)
    print(f"  vs walk_perm_chrono bank: {bank_mk:.4f}d "
          f"(delta = {bank_mk - mk_udp:+.4f}d)", flush=True)

    banked = False
    if feas and mk_udp < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x, 'problem': 'medium',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {mk_udp:.4f}d "
              f"({bank_mk - mk_udp:.4f}d under prev)", flush=True)

    print(f"\nLeaderboard context (2026-06-06):", flush=True)
    print(f"  R3 medium: {R3_MEDIUM}d  (gap from new bank: "
          f"{mk_udp - R3_MEDIUM:+.2f}d)", flush=True)
    print(f"  R1 medium: {R1_MEDIUM}d  (gap from new bank: "
          f"{mk_udp - R1_MEDIUM:+.2f}d)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_was': bank_mk, 'mk_dp_udp': mk_udp,
        'delta_d': bank_mk - mk_udp, 'feasible': feas,
        'e_used': e_used, 'banked': banked,
        'q_quantum_d': q, 'T': T,
        'R3_medium': R3_MEDIUM, 'R1_medium': R1_MEDIUM,
    }))


if __name__ == '__main__':
    main()
