"""E-531 — Ch2 medium: coarse time-coupled edge table for the DP evaluator.

Adapts ch2_e526_precompute_ultrafine.py to medium (n=181, max_time=500d).
Uses coarse params to fit the 4-core hardware budget:
  T_QUANTUM = 0.5 d → 1000 buckets over [0, 500] d
  TOFS = 50 grid points over [0.025, 12.0] d
Total cells per pair: 1000 × 50 = 50 k
All pairs: 32580 × 50 k = 1.63 B Lambert calls
At ~300 µs/call on 4 cores: ~33 h wall

Resolution rationale: 0.5 d quantum gives 0.25% relative resolution on
medium's ~200d target — enough for DP-driven perm search. Can refine
later if needed.

Output: /tmp/ch2_medium_tcoupled.npz
"""
from __future__ import annotations
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/medium.kttsp")
OUT = '/tmp/ch2_medium_tcoupled.npz'

T_QUANTUM = 0.5
T_STARTS = np.arange(0.0, 220.0, T_QUANTUM)   # capped to medium tour span (<182d)+margin: 44% cost
TOFS = np.linspace(0.025, 12.0, 50)            # 50 (step ~0.24)
DV_CAP = 100.0
DV_EXC = 600.0

_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan(args):
    i, j = args
    kt = _KT[0]
    cheap = np.full(len(T_STARTS), np.inf, dtype=np.float32)
    exc = np.full(len(T_STARTS), np.inf, dtype=np.float32)
    for ki, ts in enumerate(T_STARTS):
        if ts + TOFS[-1] > kt.max_time:
            break
        for tof in TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= DV_CAP:
                cheap[ki] = tof
                exc[ki] = tof
                break
            elif dv <= DV_EXC and tof < exc[ki]:
                exc[ki] = tof
    return i, j, cheap, exc


def main(workers=4):
    kt = KTTSP(INST)
    n = kt.n
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    print(f"Precompute MEDIUM coarse: n={n}, pairs={len(pairs)}, "
          f"t_starts={len(T_STARTS)} (Δ={T_QUANTUM}d), tofs={len(TOFS)}, "
          f"total={len(pairs)*len(T_STARTS)*len(TOFS):,}",
          flush=True)
    print(f"Est wall: ~{len(pairs)*len(T_STARTS)*len(TOFS)*3e-4/workers/3600:.1f}h",
          flush=True)

    cheap_table = np.full((n, n, len(T_STARTS)), np.inf, dtype=np.float32)
    exc_table = np.full((n, n, len(T_STARTS)), np.inf, dtype=np.float32)
    t0 = time.time()
    done = 0
    with mp.Pool(workers, initializer=_init) as p:
        for i, j, c, e in p.imap_unordered(_scan, pairs, chunksize=4):
            cheap_table[i, j] = c
            exc_table[i, j] = e
            done += 1
            if done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                eta = (len(pairs) - done) / rate
                print(f"  {done}/{len(pairs)}  rate={rate:.1f}/s  "
                      f"elapsed={elapsed/3600:.1f}h  eta={eta/3600:.1f}h",
                      flush=True)
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s ({wall/3600:.1f}h)", flush=True)
    np.savez_compressed(OUT, cheap=cheap_table, exc=exc_table,
                        t_starts=T_STARTS, tofs=TOFS)
    print(f"Saved {OUT}", flush=True)
    n_cheap = int(np.isfinite(cheap_table).sum())
    n_exc = int(np.isfinite(exc_table).sum())
    total = n * (n - 1) * len(T_STARTS)
    print(f"Cheap cells: {n_cheap}/{total} = {n_cheap/total*100:.2f}%",
          flush=True)
    print(f"Exc cells:   {n_exc}/{total} = {n_exc/total*100:.2f}%",
          flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
