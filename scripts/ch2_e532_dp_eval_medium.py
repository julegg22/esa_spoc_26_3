"""E-532 — Ch2 medium: DP evaluation on current medium bank.

Step 1 of the medium re-attack: once E-531 produces the medium tcoupled
table, run DP on the current medium bank perm (274.52 d) to find the
provable global optimum schedule on that perm.

Mirrors E-527 but for medium (n=181, max_time=500, 0.5 d quantum).

Decisive question: how much does the DP improve over walk_perm_chrono's
274.52 d on the same perm? Per the small-instance analogy, expect 5-30 d
improvement.
"""
from __future__ import annotations
import sys, os, json, time
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ch2_dp_numba import evaluate_perm_dp_numba

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
BAK = OUT + ".bak.20260606.e532"
FINE = '/tmp/ch2_medium_tcoupled.npz'
RESULT = '/tmp/ch2_e532_result.json'


def main():
    if not Path(FINE).exists():
        print(f"ERR medium table missing: {FINE}", flush=True); return
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk = float(kt.fitness(dv)[0])
    print(f"E-532 medium DP. n={n} bank_mk={bank_mk:.4f}d "
          f"start={perm[0]} end={perm[-1]}", flush=True)

    print("Loading medium tcoupled table...", flush=True)
    t0 = time.time()
    d = np.load(FINE)
    cheap = d['cheap']; exc = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    print(f"  loaded in {time.time()-t0:.1f}s shape={cheap.shape} q={q}d "
          f"T={T} horizon={T*q}d", flush=True)
    n_cheap = int(np.isfinite(cheap).sum())
    n_exc = int(np.isfinite(exc).sum())
    print(f"  cheap density: {n_cheap/cheap.size*100:.2f}%", flush=True)
    print(f"  exc density: {n_exc/exc.size*100:.2f}%", flush=True)

    print(f"\nRunning DP on bank perm (n_legs={n-1})...", flush=True)
    t0 = time.time()
    result = evaluate_perm_dp_numba(kt, perm, cheap, exc, q, T)
    wall = time.time() - t0
    print(f"DP wall: {wall:.1f}s", flush=True)

    if result is None:
        print(f"\n!!! DP found NO feasible sink — bank perm is "
              f"DP-infeasible at this resolution/grid !!!", flush=True)
        Path(RESULT).write_text(json.dumps({
            'status': 'NO_SINK', 'wall_s': wall}))
        return

    new_mk = result['mk']
    print(f"\nDP optimum on bank perm: {new_mk:.4f}d "
          f"(was walk: {bank_mk:.4f}d)", flush=True)
    print(f"  delta: {bank_mk - new_mk:+.4f}d", flush=True)
    print(f"  exc used: {result['e_used']}", flush=True)

    banked = False
    if new_mk < bank_mk - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        x_full = list(result['times']) + list(result['tofs']) + \
                  [float(p) for p in perm]
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_full, 'problem': 'medium',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {new_mk:.4f}d "
              f"({bank_mk - new_mk:.4f}d under prev)", flush=True)
        # Verify
        fit = kt.fitness(x_full)
        print(f"  UDP verify: mk={fit[0]:.4f}d feasible={kt.is_feasible(fit)} "
              f"viols={fit[1:]}", flush=True)

    # Leaderboard context
    R3_medium = 216.95; R1_medium = 199.74
    print(f"\nLeaderboard context (2026-06-06 snapshot):", flush=True)
    print(f"  R3 medium: {R3_medium}d (gap from new bank: {new_mk - R3_medium:+.2f}d)",
          flush=True)
    print(f"  R1 medium: {R1_medium}d (gap from new bank: {new_mk - R1_medium:+.2f}d)",
          flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_was': bank_mk, 'mk_dp': new_mk,
        'delta_d': bank_mk - new_mk, 'e_used': result['e_used'],
        'banked': banked, 'wall_s': wall, 'q_quantum_d': q, 'T': T,
        'R3_medium': R3_medium, 'R1_medium': R1_medium,
        'gap_to_R3': new_mk - R3_medium, 'gap_to_R1': new_mk - R1_medium,
    }))


if __name__ == '__main__':
    main()
