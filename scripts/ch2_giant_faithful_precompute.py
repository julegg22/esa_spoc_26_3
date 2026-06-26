"""E-726d — Ch2-large rank-1: precompute the FAITHFUL epoch-dense short-TOF window table (the real enabler).

The table is epoch-sparse AND makespan-optimistic (E-726 self-correction); all our "fast" beams ran on it. To
search faithfully at scale we need each short-TOF giant edge's cheap windows under the numba (official-faithful)
evaluator, as a fast lookup. This precomputes, per city, its top-N shortest-min-TOF out-neighbours' cheap
(dep, tof) windows over 0-460 d. Checkpointed every CKPT_EVERY edges (reboot-survivable, resumable). Then a
faithful beam / order-search does instant lookups instead of 1.6 s/edge scans.
Usage: python ch2_giant_faithful_precompute.py [N=50] [dep_step=0.4] [tof_step=0.025]"""
import sys, os, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST); OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = kt.min_tof
DAY = 86400.0
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
CKPT = f"{ROOT}/cache/ch2_giant_faithful_windows.npz"
CKPT_EVERY = 1500


def main(N=50, dep_step=0.4, tof_step=0.025):
    # per city, top-N shortest-min-tof out-neighbours
    from collections import defaultdict
    outn = defaultdict(list)
    for r, (i, j) in enumerate(KEYS):
        if FIN[r].any():
            outn[int(i)].append((float(np.nanmin(VALS[r])), int(j)))
    edges = []
    for i, lst in outn.items():
        lst.sort()
        for _, j in lst[:N]:
            edges.append((i, j))
    print(f"[E-726d] {len(edges)} edges (top-{N} short-tof out-neighbours), dep_step={dep_step}d "
          f"tof_step={tof_step}d", flush=True)
    deps = np.arange(0.0, 460.0, dep_step); deps_sec = deps * DAY
    done = {}
    if os.path.exists(CKPT):                                      # resume
        z = np.load(CKPT, allow_pickle=True); done = z["windows"].item()
        print(f"[E-726d] resumed: {len(done)} edges already done", flush=True)
    ft.cheap_first_tof(OPAR[0], OPAR[1], deps_sec[:4], MINTOF * DAY, 1.3 * DAY, tof_step * DAY, THR, MAXREV)
    t0 = time.time(); n0 = len(done)
    for k, (i, j) in enumerate(edges):
        if (i, j) in done:
            continue
        tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps_sec, MINTOF * DAY, 1.3 * DAY, tof_step * DAY, THR, MAXREV)
        m = tof > 0
        done[(i, j)] = (deps[m].astype(np.float32), (tof[m] / DAY).astype(np.float32))
        if (len(done) - n0) % CKPT_EVERY == 0:
            np.savez(CKPT, windows=np.array(done, dtype=object))
            rate = (len(done) - n0) / max(time.time() - t0, 1e-9)
            eta = (len(edges) - len(done)) / max(rate, 1e-9)
            print(f"[E-726d] {len(done)}/{len(edges)} edges ({rate:.1f}/s, ETA {eta/3600:.1f}h) "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    np.savez(CKPT, windows=np.array(done, dtype=object))
    print(f"[E-726d] DONE {len(done)} edges -> {CKPT} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 50, float(a[2]) if len(a) > 2 else 0.4,
         float(a[3]) if len(a) > 3 else 0.025)
