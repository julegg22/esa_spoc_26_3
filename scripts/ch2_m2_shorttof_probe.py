"""S2 — short-ToF edge probe for Ch2-small (assumption A1).

Our precompute (ch2_e526) samples ToF in [0.025, 8.0] d, but the problem allows
ToF >= 0.001 d. This scans ToF in [0.001, 0.025) for ALL (i,j) at a sample of epochs
and counts cheap (dv<=100) and fast-exception (dv<=600) edges our table never computed.
If meaningful cheap/fast edges exist there, every order search was built on a TRUNCATED
candidate set (the Ch1 sparse-matrix analog).

Instrumented per M-general-instrument-experiments-before-launch (progress + ETA).
Usage: python ch2_s2_shorttof_probe.py [n_epochs=30] [nworkers=4]
"""
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/medium.kttsp")
_KT = {}
TOFS = np.linspace(0.01, 0.0245, 8)   # the UNSAMPLED short regime (table starts 0.025)

def _init():
    from esa_spoc_26.ch2_kttsp import KTTSP
    _KT[0] = KTTSP(INST)

def scan_pair(args):
    i, j, epochs = args; kt = _KT[0]
    best_dv = 1e9; best = None
    for t in epochs:
        for tof in TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(t), float(tof))
            except Exception:
                continue
            if dv < best_dv:
                best_dv = dv; best = (t, tof)
    return i, j, best_dv, best

def main(n_epochs=30, nw=4):
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST); n = kt.n
    # control: a known short-tof transfer must return a finite dv
    _KT[0] = kt
    cd = kt.compute_transfer(0, 1, 5.0, 0.01)
    print(f"S2 control: compute_transfer(0,1,t=5,tof=0.01) -> dv={cd:.0f} (evaluator live)", flush=True)
    epochs = np.linspace(0.0, 113.0, n_epochs)
    pairs = [(i, j, epochs) for i in range(n) for j in range(n) if i != j]
    print(f"S2: scanning ToF in [0.001,0.0245] (UNSAMPLED), {len(pairs)} pairs x {n_epochs} epochs x "
          f"{len(TOFS)} tofs; ~{len(pairs)*n_epochs*len(TOFS)*5e-4/nw/60:.0f}min", flush=True)
    cheap = 0; fast_exc = 0; ndone = 0; t0 = time.time(); results = []
    with mp.Pool(nw, initializer=_init) as p:
        for i, j, dv, best in p.imap_unordered(scan_pair, pairs, chunksize=8):
            ndone += 1
            if dv <= kt.dv_thr + 1e-6:
                cheap += 1; results.append((i, j, dv, best))
            elif dv <= kt.dv_exc + 1e-6:
                fast_exc += 1
            if ndone % 400 == 0:
                print(f"  [{ndone}/{len(pairs)}] cheap-in-shortToF={cheap} fast-exc={fast_exc} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"\n=== S2 DONE: in the UNSAMPLED ToF<0.025 regime ===", flush=True)
    print(f"  CHEAP edges (dv<=100): {cheap}/{len(pairs)} pairs (the table MISSES these)", flush=True)
    print(f"  fast EXCEPTION edges (100<dv<=600): {fast_exc}/{len(pairs)}", flush=True)
    results.sort(key=lambda r: r[2])
    for i, j, dv, best in results[:15]:
        print(f"    {i}->{j}: dv={dv:.1f} at t={best[0]:.1f} tof={best[1]:.4f}d", flush=True)
    if cheap > 0:
        print(f"  -> A1 FALSIFIED: {cheap} cheap edges exist below the table's ToF floor -> "
              f"order search ran on a TRUNCATED candidate set; rebuild table from ToF=0.001.", flush=True)
    else:
        print(f"  -> no cheap edges in short-ToF regime; A1 holds (table ToF floor is benign).", flush=True)

if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    main(ne, nw)
