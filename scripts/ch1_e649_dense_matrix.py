"""E-649 — densify the E->L cost matrix for ALL 400 idE (the full re-assignment lever).

E-647 filled the 99 UNFILLED idE; the rematch banked +8,511 (21 filled, 78 left).
The bigger lever: a denser candidate matrix over ALL 400 idE so the global Hungarian
can re-assign optimally (incl. shuffling existing 301 to free idL for the 78). Cache
is 6959 pairs, Hohmann-biased (low-incl); inclination-matched candidates for most idE
are missing. This computes ALL 400 idE x 8 inclination-closest idL, row-capturing,
SKIPPING already-cached pairs.

INSTRUMENTED + INCREMENTAL SAVE per M-general-instrument-experiments-before-launch:
startup control, per-pair log, ETA, and cache flushed every SAVE_EVERY pairs so the
rematch can run on partial results if interrupted.
Usage: python ch1_e649_dense_matrix.py [K=8] [nworkers=4]
"""
import sys, json, glob, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
B = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
OUT = f"{ROOT}/runs/ch1/e649_dense_results.json"
SAVE_EVERY = 80
_UDP = {}

def _init():
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    _UDP[0] = LtlTrajectory(B)

def solve_pair(args):
    from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
    idE, idL = args; udp = _UDP[0]; best = None
    for raan_e in np.linspace(0, 2*np.pi, 4, endpoint=False):   # coarse 128
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                for t0_val in (0.0, np.pi):
                    for ea_arr in (0.0, np.pi):
                        for t2_d in (0.4, 1.0):
                            res = try_bcp_apogee_3impulse(udp, idE, idL, raan_e, argp_e,
                                  ea_dep, t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                            if res is not None and (best is None or res[0] > best[0]):
                                best = res
    if best is None: return idE, idL, None
    return idE, idL, [float(best[0]), [float(x) for x in best[1]], float(best[2])]

def cached_pairs():
    p=set()
    for f in glob.glob(f"{ROOT}/runs/ch1/*results.json"):
        try: d=json.load(open(f))
        except: continue
        if isinstance(d,dict):
            for k in d:
                try: e,l=k.split(","); p.add((int(e),int(l)))
                except: pass
    return p

def main(K=8, nw=4):
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
    E = np.loadtxt(B+"Earth_orbits.txt"); M = np.loadtxt(B+"Moon_orbits.txt")
    ie, il = E[:,3], M[:,3]
    # startup control: a real SWEEP on a KNOWN-good banked pair must yield positive mass
    _UDP[0] = LtlTrajectory(B)
    cm = solve_pair((245, 264))[2]   # (245,264) is a banked pair (E-605 winner)
    print(f"E-649 startup control: sweep (245,264) -> "
          f"{('mass=%.0f OK' % cm[0]) if cm else 'None — SOLVER/PAIRING BROKEN'} (sweep live)", flush=True)
    if cm is None:
        print("  ABORT: control returned None; fix before the long run.", flush=True); return

    have = cached_pairs()
    pairs=[]
    for e in range(400):
        for l in sorted(range(400), key=lambda x: abs(ie[e]-il[x]))[:K]:
            if (e,l) not in have: pairs.append((e,l))
    print(f"E-649: 400 idE x {K} incl-matched, {len(pairs)} NEW pairs (skipped {400*K-len(pairs)} cached); "
          f"~{len(pairs)*30/nw/60:.0f}min", flush=True)

    results={}; ndone=0; t0=time.time()
    with mp.Pool(nw, initializer=_init) as p:
        for e,l,best in p.imap_unordered(solve_pair, pairs, chunksize=1):
            ndone+=1
            if best is not None:
                results[f"{e},{l}"]=best
                if best[0]>200:
                    print(f"  [{ndone}/{len(pairs)}] {e}->{l}: {best[0]:.0f}kg dv={best[2]:.0f}", flush=True)
            if ndone%SAVE_EVERY==0:
                json.dump(results, open(OUT,"w"))   # INCREMENTAL SAVE
                print(f"  [{ndone}/{len(pairs)}] saved {len(results)} feasible, {time.time()-t0:.0f}s", flush=True)
    json.dump(results, open(OUT,"w"))
    print(f"\n=== E-649 DONE: {len(results)} feasible saved to {OUT} ===", flush=True)
    print(f"  NEXT: add e649_dense_results.json to ledger_rematch CACHES + re-solve assignment.", flush=True)

if __name__=="__main__":
    K=int(sys.argv[1]) if len(sys.argv)>1 else 8
    nw=int(sys.argv[2]) if len(sys.argv)>2 else 4
    main(K,nw)
