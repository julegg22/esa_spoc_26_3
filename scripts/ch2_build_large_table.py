"""E-660 prerequisite for the LARGE TD-TSP build (user-approved): epoch-resolved cheap-tof table.

For each cheap (i,j) pair (e533 static adjacency, ~12.6% dense), compute the MIN cheap (dv≤100) tof
at each epoch bucket — the table the fast faithful table-walk needs (faithful for large per L1).
Sparse storage (only cheap pairs). Instrumented: positive control, per-chunk progress + ETA,
incremental save. Usage: python ch2_build_large_table.py [nepochs=120] [workers=4]
"""
import sys, time, json
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = "/tmp/ch2_large_epoch_table.npz"
TOFS = np.linspace(0.001, 8.0, 60)        # scan; cheap = first tof with dv<=100
_K = {}


def _init():
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST)
    _K['epochs'] = _EPOCHS


def _row(args):
    i, js = args; kt = _K['kt']; eps = _K['epochs']
    out = np.full((len(js), len(eps)), np.inf, dtype=np.float32)
    for jk, j in enumerate(js):
        for ek, t in enumerate(eps):
            for tof in TOFS:
                try:
                    if kt.compute_transfer(i, int(j), float(t), float(tof)) <= kt.dv_thr + 1e-6:
                        out[jk, ek] = tof; break
                except Exception:
                    continue
    return i, js, out


def main(nepochs=120, workers=4):
    global _EPOCHS
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST); n = kt.n
    _EPOCHS = np.linspace(0.0, min(kt.max_time, 950.0), nepochs)
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    pairs_by_i = {i: list(np.where(adj[i])[0]) for i in range(n) if adj[i].any()}
    npairs = sum(len(v) for v in pairs_by_i.values())
    # positive control
    cd = kt.compute_transfer(0, 1, 0.0, 0.5)
    print(f"[E-660] n={n} cheap-pairs={npairs} epochs={nepochs} | control compute_transfer(0,1,0,0.5)={cd:.0f} "
          f"est~{npairs*nepochs*len(TOFS)*5e-5/workers/60:.0f}min", flush=True)
    _EPOCHS = _EPOCHS  # captured by _init via global
    tasks = [(i, js) for i, js in pairs_by_i.items()]
    table = {}; done = 0; t0 = time.time()
    with mp.Pool(workers, initializer=_init) as p:
        for i, js, out in p.imap_unordered(_row, tasks, chunksize=2):
            for jk, j in enumerate(js):
                table[(i, int(j))] = out[jk]
            done += 1
            if done % 50 == 0:
                el = time.time() - t0; rate = done / el
                print(f"  {done}/{len(tasks)} rows  eta={(len(tasks)-done)/rate:.0f}s "
                      f"[{el:.0f}s]", flush=True)
            if done % 400 == 0:
                np.savez_compressed(OUT, epochs=_EPOCHS,
                                    keys=np.array(list(table.keys())),
                                    vals=np.array(list(table.values()), dtype=np.float32))
    np.savez_compressed(OUT, epochs=_EPOCHS, keys=np.array(list(table.keys())),
                        vals=np.array(list(table.values()), dtype=np.float32))
    print(f"[done] {time.time()-t0:.0f}s | {len(table)} cheap pairs x {nepochs} epochs -> {OUT}", flush=True)
    print(f"  -> next: SA over large orders w/ fast table-walk on this table; target 932->424 (rank2->1)", flush=True)


if __name__ == "__main__":
    ne = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    main(ne, w)
