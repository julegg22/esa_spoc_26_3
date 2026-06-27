"""E-735 probe #1 enabler — FULL-coverage faithful comp0 windows (the existing npz is short-tof ≤1.3d AND
epoch ≤460, so the complete 932 bank tour cannot even be walked on it: 332/598 bank comp0 legs depart >460 and
its 1-3d/3-8d legs exceed 1.3d tof). To run the medium-style faithful order search seeded from the COMPLETE bank
tour we need each comp0 edge's cheap (dep,tof) windows over the FULL epoch range and FULL tof range.

Per edge: cheap_first_tof over deps [0, T_MAX] scanning tof up to TOF_HI. Edge set = top-N short-tof out-
neighbours per comp0 city UNION the bank's own 598 comp0->comp0 edges (so the seed walks). Checkpointed +
resumable. New output file (does NOT clobber the 0-460 short-tof npz other scripts use).
Usage: python ch2_giant_faithful_full_precompute.py [N=70] [dep_step=0.4] [tof_step=0.03] [T_MAX=960] [TOF_HI=8.5]"""
import sys, os, time, json
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
CKPT = f"{ROOT}/cache/ch2_giant_faithful_full.npz"
CKPT_EVERY = 1000


def main(N=70, dep_step=0.4, tof_step=0.03, T_MAX=960.0, TOF_HI=8.5):
    from collections import defaultdict
    outn = defaultdict(list)
    for r, (i, j) in enumerate(KEYS):
        if FIN[r].any():
            outn[int(i)].append((float(np.nanmin(VALS[r])), int(j)))
    edgeset = set()
    for i, lst in outn.items():
        lst.sort()
        for _, j in lst[:N]:
            edgeset.add((i, int(j)))
    # UNION the bank's own comp0->comp0 edges so the complete seed is walkable
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    Ncity = 1051; order = [int(c) for c in bank[2 * (Ncity - 1):]]
    comp0 = set(int(i) for ij in KEYS for i in ij)
    nb = 0
    for k in range(Ncity - 1):
        a, b = order[k], order[k + 1]
        if a in comp0 and b in comp0:
            edgeset.add((a, b)); nb += 1
    edges = sorted(edgeset)
    print(f"[E-735full] {len(edges)} edges (top-{N} out-nbrs + {nb} bank comp0 edges), "
          f"deps[0,{T_MAX}] step {dep_step}, tof_hi {TOF_HI} step {tof_step}", flush=True)
    deps = np.arange(0.0, T_MAX, dep_step); deps_sec = deps * DAY
    done = {}
    if os.path.exists(CKPT):
        z = np.load(CKPT, allow_pickle=True); done = z["windows"].item()
        print(f"[E-735full] resumed: {len(done)} edges already done", flush=True)
    ft.cheap_first_tof(OPAR[0], OPAR[1], deps_sec[:4], MINTOF * DAY, TOF_HI * DAY, tof_step * DAY, THR, MAXREV)
    t0 = time.time(); n0 = len(done)
    for k, (i, j) in enumerate(edges):
        if (i, j) in done:
            continue
        tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps_sec, MINTOF * DAY, TOF_HI * DAY, tof_step * DAY, THR, MAXREV)
        m = tof > 0
        done[(i, j)] = (deps[m].astype(np.float32), (tof[m] / DAY).astype(np.float32))
        if (len(done) - n0) % CKPT_EVERY == 0 and len(done) > n0:
            np.savez(CKPT, windows=np.array(done, dtype=object))
            rate = (len(done) - n0) / max(time.time() - t0, 1e-9)
            eta = (len(edges) - len(done)) / max(rate, 1e-9)
            print(f"[E-735full] {len(done)}/{len(edges)} ({rate:.1f}/s, ETA {eta/3600:.2f}h) [{time.time()-t0:.0f}s]", flush=True)
    np.savez(CKPT, windows=np.array(done, dtype=object))
    print(f"[E-735full] DONE {len(done)} edges -> {CKPT} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 70, float(a[2]) if len(a) > 2 else 0.4,
         float(a[3]) if len(a) > 3 else 0.03, float(a[4]) if len(a) > 4 else 960.0,
         float(a[5]) if len(a) > 5 else 8.5)
