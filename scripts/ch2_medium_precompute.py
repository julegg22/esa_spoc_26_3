"""E-731 path #2 enabler — fast FAITHFUL window table for Ch2-MEDIUM (full edge set, NO 0.025 tof floor).

The medium order was built on a truncated edge set (tof>=0.025; E-653 found 207 cheap edges below it). To search
the ORDER faithfully we need each cheap directed edge's (dep, tof) windows under the numba evaluator, as a fast
lookup — the medium analog of cache/ch2_giant_faithful_windows.npz. n=181 so we scan ALL 181*180 edges directly.
Saves cache/ch2_medium_windows.npz (dict (i,j)->(deps,tofs)). Checkpointed, resumable.
Usage: python ch2_medium_precompute.py [dep_step=0.5] [tof_step=0.04] [tof_hi=6.0]"""
import sys, os, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/medium.kttsp")
kt = KTTSP(INST); OPAR = kt.opar.astype(np.float64)
THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = max(kt.min_tof, 0.01); DAY = 86400.0
N = kt.n
CKPT = f"{ROOT}/cache/ch2_medium_windows.npz"


def main(dep_step=0.5, tof_step=0.04, tof_hi=6.0):
    deps = np.arange(0.0, kt.max_time, dep_step)
    deps_sec = deps * DAY
    deps_coarse = (np.arange(0.0, kt.max_time, 12.5) * DAY)       # sparse prefilter grid (skip never-cheap edges)
    ft.transfer_dv(OPAR[0], OPAR[1], 10 * DAY, 1 * DAY, MAXREV)   # JIT warm
    done = {}
    if os.path.exists(CKPT):
        done = dict(np.load(CKPT, allow_pickle=True)["windows"].item())
        print(f"[medium-pre] resume {len(done)} edges", flush=True)
    t0 = time.time(); scanned = 0; cheap_edges = 0
    for i in range(N):
        for j in range(N):
            if i == j or (i, j) in done:
                continue
            # PREFILTER: cheap-test on a sparse dep grid first; skip edges never cheap (kills ~90% non-cheap fast)
            pre = ft.cheap_first_tof(OPAR[i], OPAR[j], deps_coarse, MINTOF * DAY, tof_hi * DAY,
                                     tof_step * DAY, THR, MAXREV)
            scanned += 1
            if not (pre > 0).any():
                continue
            # first cheap tof per departure epoch (numba, parallel over deps; -1 = none).
            # NB cheap_first_tof works in SECONDS (tof added to dsec); convert tof grid days->sec, result sec->days.
            tofs_sec = ft.cheap_first_tof(OPAR[i], OPAR[j], deps_sec, MINTOF * DAY, tof_hi * DAY,
                                          tof_step * DAY, THR, MAXREV)
            mask = tofs_sec > 0
            if mask.any():
                done[(i, j)] = (deps[mask].copy(), (tofs_sec[mask] / DAY).copy()); cheap_edges += 1
        if i % 10 == 0:
            np.savez(CKPT, windows=np.array(done, dtype=object))
            print(f"[medium-pre] row {i}/{N}  scanned {scanned}  cheap edges {len(done)} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    np.savez(CKPT, windows=np.array(done, dtype=object))
    print(f"[medium-pre] DONE: {len(done)} cheap directed edges of {N*(N-1)} "
          f"({100*len(done)/(N*(N-1)):.1f}%) [{time.time()-t0:.0f}s] -> {CKPT}", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(float(a[1]) if len(a) > 1 else 0.5, float(a[2]) if len(a) > 2 else 0.04,
         float(a[3]) if len(a) > 3 else 6.0)
