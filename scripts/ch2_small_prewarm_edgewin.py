"""E-760b — parallel pre-warm of the small edge-window cache for ch2_small_order_search.

The E-740 small order-search stalled at it0 because the lazy per-edge window scan costs ~7.5 s/edge, so the
LNS never escaped warmup. Fix: warm _edge_win ONCE for all USABLE edges (dv<=600 in edges_small.npz: 138 cheap
+ 837 exception = 975), persist to the base pickle the order-search loads, then the exact-DP LNS runs millions
of fast evals. Imports the search's own _edge_win so the cache is byte-consistent with what it would compute.
Bounded (~975 edges, ETA ~30 min at 4 workers), monitored (progress log), one-time.
Usage: python ch2_small_prewarm_edgewin.py [workers=4]"""
import sys, os, time, pickle
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def _warm(ij):
    import ch2_small_order_search as oss
    i, j = ij
    return ij, oss._edge_win(i, j)


def main(workers=4):
    import ch2_small_order_search as oss
    dv = np.load(f"{ROOT}/edges_small.npz")["dv"]
    n = dv.shape[0]
    edges = [(i, j) for i in range(n) for j in range(n)
             if i != j and np.isfinite(dv[i, j]) and dv[i, j] <= 600.0]
    print(f"[E-760b] warming {len(edges)} usable edges (n={n}, dv<=600) -> {oss._BASE}", flush=True)
    cache = {}
    t0 = time.time(); done = 0
    with mp.Pool(workers) as p:
        for ij, res in p.imap_unordered(_warm, edges, chunksize=4):
            cache[ij] = res
            done += 1
            if done % 50 == 0:
                el = time.time() - t0; rate = done / el if el else 0
                eta = (len(edges) - done) / rate / 60 if rate else 0
                print(f"  {done}/{len(edges)} rate={rate:.2f}/s eta={eta:.1f}min "
                      f"[{el/60:.1f}min]", flush=True)
    pickle.dump(cache, open(oss._BASE, "wb"))
    print(f"[E-760b] DONE {len(cache)} edges in {time.time()-t0:.0f}s -> {oss._BASE}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
