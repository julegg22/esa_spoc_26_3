"""E-670: DENSE per-(i,j) cheap-window precompute for the Ch2-large 601-GIANT (user-approved 2026-06-19).

WHY (E-669): every fast constructor (beam, LNS, table-walk) is BLIND on the coarse 120-epoch/60-tof
table — it over-reports tofs (7.8 d/leg vs faithful 0.30) because 8d epoch buckets + 60-tof grid miss
the short cheap-now windows the faithful find_earliest_transfer sees. This builds the accurate data the
global rank-1 constructor needs: for each cheap GIANT pair (i,j) over a FINE epoch grid (240 ≈ 4d) and a
FINE short-tof grid, the MIN cheap (dv≤100) tof at each epoch. ~74208 directed pairs ⇒ ~7.4h on 4 cores.
Instrumented: positive control, per-50-row ETA, incremental save every 400 rows (partial = usable).

Output: /tmp/ch2_giant_dense.npz {epochs, keys=(i,j), vals=float32[nepochs] min-cheap-tof or inf}.
Usage: python ch2_giant_dense_precompute.py [nepochs=240] [workers=4]
"""
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = "/tmp/ch2_giant_dense.npz"
# fine short-tof grid (cheap legs are short; emphasize <2d) + coarse tail to 8d
TOFS = np.concatenate([np.linspace(0.02, 2.0, 100), np.linspace(2.1, 8.0, 40)])
_K = {}


def _init(epochs):
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST); _K['eps'] = epochs


def _row(args):
    i, js = args; kt = _K['kt']; eps = _K['eps']; thr = kt.dv_thr
    out = np.full((len(js), len(eps)), np.inf, dtype=np.float32)
    for jk, j in enumerate(js):
        for ek, t in enumerate(eps):
            for tof in TOFS:
                try:
                    if kt.compute_transfer(i, int(j), float(t), float(tof)) <= thr + 1e-6:
                        out[jk, ek] = tof; break
                except Exception:
                    continue
    return i, js, out


def main(nepochs=240, workers=4):
    from esa_spoc_26.ch2_kttsp import KTTSP
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse import csr_matrix
    kt = KTTSP(INST)
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes)
    epochs = np.linspace(0.0, min(kt.max_time, 950.0), nepochs)
    pairs_by_i = {i: [int(j) for j in np.where(adj[i])[0] if int(j) in gset] for i in gnodes}
    pairs_by_i = {i: js for i, js in pairs_by_i.items() if js}
    npairs = sum(len(v) for v in pairs_by_i.values())
    cd = kt.compute_transfer(gnodes[0], gnodes[1], 0.0, 0.5)
    print(f"[E-670] giant={len(gnodes)} dir-pairs={npairs} epochs={nepochs} tofs={len(TOFS)} | "
          f"control compute_transfer={cd:.0f} | est~{npairs*nepochs*len(TOFS)*5e-5/workers/60:.0f}min",
          flush=True)
    tasks = [(i, js) for i, js in pairs_by_i.items()]
    table = {}; done = 0; t0 = time.time()
    with mp.Pool(workers, initializer=_init, initargs=(epochs,)) as p:
        for i, js, out in p.imap_unordered(_row, tasks, chunksize=1):
            for jk, j in enumerate(js):
                table[(i, int(j))] = out[jk]
            done += 1
            if done % 5 == 0:
                el = time.time() - t0; rate = done / el
                print(f"  {done}/{len(tasks)} rows  eta={(len(tasks)-done)/rate/60:.0f}min [{el/60:.0f}min]",
                      flush=True)
            if done % 100 == 0:
                np.savez_compressed(OUT, epochs=epochs, keys=np.array(list(table.keys())),
                                    vals=np.array(list(table.values()), dtype=np.float32))
    np.savez_compressed(OUT, epochs=epochs, keys=np.array(list(table.keys())),
                        vals=np.array(list(table.values()), dtype=np.float32))
    print(f"[done] {(time.time()-t0)/60:.0f}min | {len(table)} pairs x {nepochs} epochs -> {OUT}", flush=True)


if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 240
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    main(ne, w)
