"""E-526 — Ultra-fine time-coupled edge table for Ch2 small (B).

Quantum bumped from 0.5 d to 0.05 d (10× finer) so the DP/Dijkstra in
E-527 can actually represent bank's continuous-t schedule (E-030 F1).

Grid:
  t_start: 0.05 d quantum → 4000 buckets over [0, 200) d
  tof:     0.05 d quantum → 160 grid points over [0.025, 8.0] d
  Total cells per pair: 4000 × 160 = 640 k
  All pairs: 2352 × 640 k ≈ 1.5 B Lambert calls
  At 50 µs/call on 8 cores: ~3 h wall

Memory: 4000 × 49² × 4 bytes ≈ 76 MB per table (cheap + exc) ≈ 150 MB total.
Compressed npz ≈ 50–80 MB.

Output: /tmp/ch2_small_tcoupled_ultrafine.npz
"""
from __future__ import annotations
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = '/tmp/ch2_small_tcoupled_ultrafine.npz'

T_QUANTUM = 0.05
T_STARTS = np.arange(0.0, 200.0, T_QUANTUM)        # 4000
TOFS = np.linspace(0.025, 8.0, 160)                # 160 (step ~0.05)
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
        if ts + 8.0 > kt.max_time:
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


def main(workers=8):
    kt = KTTSP(INST)
    n = kt.n
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    print(f"Precompute ULTRAFINE: n={n}, pairs={len(pairs)}, "
          f"t_starts={len(T_STARTS)} (Δ={T_QUANTUM}d), tofs={len(TOFS)}, "
          f"total={len(pairs)*len(T_STARTS)*len(TOFS):,}", flush=True)
    print(f"Est wall: ~{len(pairs)*len(T_STARTS)*len(TOFS)*5e-5/workers/60:.0f} min",
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
            if done % 100 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                eta = (len(pairs) - done) / rate
                print(f"  {done}/{len(pairs)}  rate={rate:.1f}/s  "
                      f"elapsed={elapsed:.0f}s  eta={eta:.0f}s",
                       flush=True)
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s ({wall/60:.0f} min)", flush=True)
    np.savez_compressed(OUT, cheap=cheap_table, exc=exc_table,
                        t_starts=T_STARTS, tofs=TOFS)
    print(f"Saved {OUT}", flush=True)
    n_cheap = np.isfinite(cheap_table).sum()
    n_exc = np.isfinite(exc_table).sum()
    total = n * (n - 1) * len(T_STARTS)
    print(f"Cheap cells: {n_cheap}/{total} = {n_cheap/total*100:.2f}%",
           flush=True)
    print(f"Exc cells:   {n_exc}/{total} = {n_exc/total*100:.2f}%",
           flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    main(workers=w)
