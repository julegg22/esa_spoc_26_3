"""E-542 — Ch2 medium: fine precompute on a CURATED pair set.

Selects ~5000 pairs to precompute fine for, prioritizing:
  1. All bank-perm directed pairs (180)
  2. All pairs cheap-feasible at coarse resolution (~3181 pairs)
  3. Top-1500 lowest-min-exc-tof pairs (for ALNS exc legs)
  Total ≈ 5000 pairs.

Resolution: 0.1 d t-quantum × 100 tof points (step ~0.12 d, range
[0.025, 12.0] d). Pair-keyed (i, j) so ALNS can look up arbitrary perms.

Output: /tmp/ch2_medium_fine_pair_set.npz
  cheap[i, j, t_bucket]  — min tof for cheap-feasible cells (else nan)
  exc[i, j, t_bucket]    — min tof for exc-feasible cells (else nan)
  t_starts: shape (T,)
  pair_set: list of (i, j) tuples actually precomputed
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
COARSE = '/tmp/ch2_medium_tcoupled.npz'
OUT = '/tmp/ch2_medium_fine_pair_set.npz'

T_QUANTUM = 0.1
T_STARTS = np.arange(0.0, 220.0, T_QUANTUM)  # capped to medium tour span (<182d)+margin (e545 reads len from table)
TOFS = np.linspace(0.025, 12.0, 100)         # 100 points
DV_CAP = 100.0
DV_EXC = 600.0
N_EXC_PAIRS_EXTRA = 1500  # additional exc-only pairs to include

_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan(args):
    pair_idx, i, j = args
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
    return pair_idx, cheap, exc


def select_pairs(kt, perm, n_extra=1500):
    """Build curated pair set."""
    n = kt.n
    pairs = set()
    # 1) Bank perm pairs
    for k in range(len(perm) - 1):
        pairs.add((perm[k], perm[k+1]))
    # 2) All cheap-feasible pairs at coarse
    d = np.load(COARSE)
    cheap = d['cheap']; exc = d['exc']
    cheap_min = np.nanmin(cheap, axis=2)
    np.fill_diagonal(cheap_min, np.inf)
    cheap_pairs = [(int(i), int(j)) for i, j in np.argwhere(np.isfinite(cheap_min))]
    pairs.update(cheap_pairs)
    n_after_cheap = len(pairs)
    # 3) Top-K exc-only pairs by lowest min-exc-tof
    exc_min = np.nanmin(exc, axis=2)
    np.fill_diagonal(exc_min, np.inf)
    # Mask out pairs already in pairs set
    exc_min_only = np.where(np.isfinite(cheap_min), np.inf, exc_min)
    # Sort by ascending tof
    flat = exc_min_only.flatten()
    order = np.argsort(flat)
    n_total = 0
    for idx in order:
        if not np.isfinite(flat[idx]): break
        i = idx // n; j = idx % n
        pairs.add((int(i), int(j)))
        n_total += 1
        if n_total >= n_extra: break
    return sorted(pairs), n_after_cheap


def main(workers=4):
    kt = KTTSP(INST)
    n = kt.n
    print(f"E-542 medium curated fine precompute. n={n}", flush=True)
    bank = json.load(open(BANK))
    dv = bank[0]['decisionVector']
    perm = [int(x) for x in dv[2*(n-1):]]
    print(f"Bank perm: start={perm[0]} end={perm[-1]} legs={len(perm)-1}",
          flush=True)

    pair_list, n_after_cheap = select_pairs(kt, perm, n_extra=N_EXC_PAIRS_EXTRA)
    print(f"Pair set: |bank+cheap|={n_after_cheap}, +{N_EXC_PAIRS_EXTRA} exc-extra "
          f"= {len(pair_list)} unique pairs", flush=True)
    n_t = len(T_STARTS)
    total_cells = len(pair_list) * n_t * len(TOFS)
    print(f"Total cells: {total_cells:,}", flush=True)
    print(f"Est wall on {workers} cores: "
          f"~{total_cells * 8e-6 / workers / 3600:.1f}h "
          f"(based on E-540 rate ~120k cells/s/core)", flush=True)

    # Build per-pair index
    n_pairs = len(pair_list)
    args = [(i, p[0], p[1]) for i, p in enumerate(pair_list)]
    cheap_table = np.full((n_pairs, n_t), np.inf, dtype=np.float32)
    exc_table = np.full((n_pairs, n_t), np.inf, dtype=np.float32)

    t0 = time.time()
    done = 0
    with mp.Pool(workers, initializer=_init) as p:
        for k, c, e in p.imap_unordered(_scan, args, chunksize=4):
            cheap_table[k] = c
            exc_table[k] = e
            done += 1
            if done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (n_pairs - done) / rate if rate > 0 else 0
                print(f"  {done}/{n_pairs} pairs  rate={rate:.1f}/s "
                      f"elapsed={elapsed/3600:.2f}h eta={eta/3600:.2f}h",
                      flush=True)
    wall = time.time() - t0
    print(f"\nDone in {wall:.0f}s ({wall/3600:.2f}h)", flush=True)

    # Save as dense (n, n, T) tables for compatibility with existing DP code
    cheap_dense = np.full((n, n, n_t), np.inf, dtype=np.float32)
    exc_dense = np.full((n, n, n_t), np.inf, dtype=np.float32)
    for k, (i, j) in enumerate(pair_list):
        cheap_dense[i, j] = cheap_table[k]
        exc_dense[i, j] = exc_table[k]
    np.savez_compressed(OUT,
                        cheap=cheap_dense, exc=exc_dense,
                        t_starts=T_STARTS, tofs=TOFS,
                        pair_set=np.array(pair_list, dtype=np.int32))
    print(f"Saved {OUT}", flush=True)
    n_cheap = int(np.isfinite(cheap_dense).sum())
    n_exc = int(np.isfinite(exc_dense).sum())
    total = n_pairs * n_t
    print(f"Cheap cells (per stored pairs): {n_cheap} / {total} "
          f"= {n_cheap/total*100:.1f}%", flush=True)
    print(f"Exc cells   (per stored pairs): {n_exc} / {total} "
          f"= {n_exc/total*100:.1f}%", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
