"""Augment the Ch2-small ultrafine cheap-edge table into the UNSAMPLED short-ToF
regime [0.001, 0.025) — the A1 fix (S2 probe proved cheap edges exist below the
0.025 floor the table was built with). For each (i,j,t_start) we find the SHORTEST
cheap (dv<=100) / exc (dv<=600) tof in the short slice and merge-min it into the
existing table, then re-search can place legs on those faster edges.

Surgical: only the 24 short tofs are scanned (not a full rebuild); existing entries
are kept unless a shorter cheap tof is found. Instrumented per
M-general-instrument-experiments-before-launch: startup positive control, per-chunk
progress + ETA, incremental save.

Output: /tmp/ch2_small_tcoupled_ultrafine_v2.npz  (cheap/exc/t_starts/tofs)
Usage: python ch2_augment_small_shorttof.py [workers=4]
"""
from __future__ import annotations
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
SRC = '/tmp/ch2_small_tcoupled_ultrafine.npz'
OUT = '/tmp/ch2_small_tcoupled_ultrafine_v2.npz'

SHORT_TOFS = np.round(np.arange(0.001, 0.025, 0.001), 4)   # 24 pts, all < 0.025 floor
DV_CAP = 100.0
DV_EXC = 600.0
_KT = [None]
_TS = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan_short(args):
    """Shortest cheap/exc tof in the short slice for pair (i,j) at every t_start."""
    i, j = args
    kt = _KT[0]; T_STARTS = _TS[0]
    cheap = np.full(len(T_STARTS), np.inf, dtype=np.float32)
    exc = np.full(len(T_STARTS), np.inf, dtype=np.float32)
    for ki, ts in enumerate(T_STARTS):
        if ts + 8.0 > kt.max_time:
            break
        for tof in SHORT_TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= DV_CAP:
                cheap[ki] = tof
                exc[ki] = tof
                break          # ascending → first cheap is shortest
            elif dv <= DV_EXC and tof < exc[ki]:
                exc[ki] = tof
    return i, j, cheap, exc


def main(workers=4):
    d = np.load(SRC)
    cheap_t = d['cheap'].copy(); exc_t = d['exc'].copy()
    T_STARTS = d['t_starts']; old_tofs = d['tofs']
    _TS[0] = T_STARTS
    n = cheap_t.shape[0]
    kt = KTTSP(INST)

    # ── startup positive control: short scan of one pair at one epoch ──
    ci = kt.compute_transfer(0, 1, float(T_STARTS[100]), 0.02)
    print(f"[control] compute_transfer(0,1,t={T_STARTS[100]:.2f},tof=0.02)->dv={ci:.1f} "
          f"(evaluator live); old table floor tof={old_tofs.min():.4f}, "
          f"short slice [{SHORT_TOFS[0]:.3f},{SHORT_TOFS[-1]:.3f}] {len(SHORT_TOFS)}pts",
          flush=True)
    pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    print(f"[start] augment short-ToF: n={n} pairs={len(pairs)} t_starts={len(T_STARTS)} "
          f"evals~{len(pairs)*len(T_STARTS)*len(SHORT_TOFS):,} "
          f"est~{len(pairs)*len(T_STARTS)*len(SHORT_TOFS)*5e-5/workers/60:.0f}min", flush=True)

    t0 = time.time(); done = 0; n_improved = 0
    with mp.Pool(workers, initializer=_init) as p:
        for i, j, c_short, e_short in p.imap_unordered(_scan_short, pairs, chunksize=4):
            # merge-min: keep shorter cheap/exc tof
            imp = (c_short < cheap_t[i, j]).sum()
            n_improved += int(imp)
            cheap_t[i, j] = np.minimum(cheap_t[i, j], c_short)
            exc_t[i, j] = np.minimum(exc_t[i, j], e_short)
            done += 1
            if done % 100 == 0:
                el = time.time() - t0; rate = done / el
                print(f"  {done}/{len(pairs)} rate={rate:.1f}/s elapsed={el:.0f}s "
                      f"eta={(len(pairs)-done)/rate:.0f}s cheap-cells-shortened={n_improved}",
                      flush=True)
            if done % 800 == 0:   # incremental save
                np.savez_compressed(OUT, cheap=cheap_t, exc=exc_t,
                                    t_starts=T_STARTS, tofs=old_tofs)
    np.savez_compressed(OUT, cheap=cheap_t, exc=exc_t, t_starts=T_STARTS, tofs=old_tofs)
    print(f"\n[done] {time.time()-t0:.0f}s | cheap cells shortened by short-ToF: "
          f"{n_improved} | saved {OUT}", flush=True)
    print(f"  (re-point the small order-search at {OUT} and re-run to test if the "
          f"corrected edge set breaks 112.996)", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
