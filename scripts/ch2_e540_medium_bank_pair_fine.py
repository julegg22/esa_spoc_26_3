"""E-540 — Ch2 medium: fine-resolution precompute for bank-perm pairs only.

E-532 revealed the medium coarse table (0.5d × 50 tof) is too coarse for DP
to even match walk_perm_chrono's 274.52 d on bank perm (DP gave 380.93 d).
The fine version of the full medium table is ~33-day precompute on 4 cores.

This script does a TARGETED fine precompute: only the 180 directed pairs
used by medium's current bank perm. With small-equivalent resolution
(0.05 d t-quantum, 160 tof points step 0.05 d), this is ~4.4 h on 4 cores
and unlocks fine-grained DP on bank perm.

Output: /tmp/ch2_medium_bank_pairs_fine.npz
  Storage scheme: for each leg k in bank perm (180 legs):
    cheap[k, t_bucket]   = min tof at this t_bucket if cheap-feasible
    exc[k, t_bucket]     = min tof at this t_bucket if exc-feasible
    t_starts: shape (T,)
    tofs:     shape (n_tof,) — the tof grid (not actually used; only
              the min-tof per t_bucket is stored)

  This is exactly the input format E-527's forward DP expects (it
  computes arrival buckets from the stored min-tof).
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
OUT = '/tmp/ch2_medium_bank_pairs_fine.npz'

T_QUANTUM = 0.1   # day — 5× finer than the production coarse table (0.5d)
T_STARTS = np.arange(0.0, 500.0, T_QUANTUM)  # 5 000 buckets over [0,500]
# Bank's per-leg tofs span a wide range; cover [0.025, 12] d
TOFS = np.linspace(0.025, 12.0, 160)   # step ~0.075 d
DV_CAP = 100.0
DV_EXC = 600.0

_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan(args):
    k, i, j = args   # k = leg index in bank perm
    kt = _KT[0]
    n_t = len(T_STARTS)
    cheap = np.full(n_t, np.inf, dtype=np.float32)
    exc = np.full(n_t, np.inf, dtype=np.float32)
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
    return k, cheap, exc


def main(workers=4):
    kt = KTTSP(INST)
    n = kt.n
    print(f"E-540 medium bank-perm fine precompute. n={n}, "
          f"max_time={kt.max_time}d", flush=True)

    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    n_legs = len(perm) - 1
    print(f"Bank perm: start={perm[0]} end={perm[-1]} n_legs={n_legs}",
          flush=True)

    # Build leg list (k, i, j) for each leg
    legs = [(k, perm[k], perm[k+1]) for k in range(n_legs)]
    print(f"Total work: {n_legs} legs × {len(T_STARTS)} t × {len(TOFS)} tof "
          f"= {n_legs * len(T_STARTS) * len(TOFS):,} Lambert calls",
          flush=True)
    print(f"Est wall on {workers} cores: "
          f"~{n_legs * len(T_STARTS) * len(TOFS) * 5.5e-4 / workers / 3600:.1f}h",
          flush=True)

    n_t = len(T_STARTS)
    cheap_table = np.full((n_legs, n_t), np.inf, dtype=np.float32)
    exc_table = np.full((n_legs, n_t), np.inf, dtype=np.float32)

    t0 = time.time()
    done = 0
    with mp.Pool(workers, initializer=_init) as p:
        for k, c, e in p.imap_unordered(_scan, legs, chunksize=1):
            cheap_table[k] = c
            exc_table[k] = e
            done += 1
            if done % 10 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                eta = (n_legs - done) / rate if rate > 0 else 0
                print(f"  {done}/{n_legs}  rate={rate:.2f}/s "
                      f"elapsed={elapsed/60:.1f}min eta={eta/60:.1f}min",
                      flush=True)
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s ({wall/3600:.1f}h)", flush=True)
    np.savez_compressed(OUT, cheap=cheap_table, exc=exc_table,
                        t_starts=T_STARTS, tofs=TOFS,
                        perm=np.array(perm, dtype=np.int32))
    print(f"Saved {OUT}", flush=True)
    n_cheap = int(np.isfinite(cheap_table).sum())
    n_exc = int(np.isfinite(exc_table).sum())
    total = n_legs * n_t
    print(f"Cheap cells: {n_cheap}/{total} = {n_cheap/total*100:.2f}%",
          flush=True)
    print(f"Exc cells:   {n_exc}/{total} = {n_exc/total*100:.2f}%",
          flush=True)


if __name__ == '__main__':
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
