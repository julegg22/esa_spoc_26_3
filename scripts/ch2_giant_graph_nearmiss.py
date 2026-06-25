"""E-721b — Ch2-large: graph-wide cheap-edge recovery via NEAR-MISS rescan.

The 35-focus recompute (E-721) was too narrow (whack-a-mole: beam re-routes, strands a different set). The
8-probe under-count is graph-wide. Efficient graph-wide fix: re-scan ONLY the ~60k "near-miss" pairs that the
8-probe marked exception-close (best dv <=600) but NOT cheap (<=100) — these are orbitally close, the most
likely to be cheap at an unsampled phase. Same proper scan as E-721 (fine tof, COARSE=8, 0-460 rank-1
window). Output cache/ch2_giant_dense1d_nm.npz (the newly-found cheap edges); merge with the original.

Usage: python ch2_giant_graph_nearmiss.py [workers=4] [horizon=460] [nepochs=230]"""
import sys, time, os
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = f"{ROOT}/cache/ch2_giant_dense1d_nm.npz"
TOFS = np.concatenate([np.linspace(0.02, 2.0, 90), np.linspace(2.1, 12.0, 50)])
COARSE = 8
_K = {}


def _init(epochs):
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST); _K['eps'] = epochs


def _scan(kt, i, j, t, thr):
    for tof in TOFS:
        if kt.compute_transfer(i, j, float(t), float(tof)) <= thr + 1e-6:
            return float(tof)
    return np.inf


def _row(args):
    i, js = args; kt = _K['kt']; eps = _K['eps']; thr = kt.dv_thr; ne = len(eps)
    cidx = list(range(0, ne, COARSE))
    res = []
    for j in js:
        j = int(j)
        row = np.full(ne, np.inf, dtype=np.float32); hits = []
        for ci in cidx:
            v = _scan(kt, i, j, eps[ci], thr); row[ci] = v
            if np.isfinite(v):
                hits.append(ci)
        if not hits:
            continue
        fine = set()
        for ci in hits:
            fine.update(range(max(0, ci - COARSE), min(ne, ci + COARSE + 1)))
        for ek in fine:
            if not np.isfinite(row[ek]):
                row[ek] = _scan(kt, i, j, eps[ek], thr)
        if np.isfinite(row).any():
            res.append((i, j, row))
    return res


def main(workers=4, horizon=460.0, nepochs=230):
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST)
    a = np.load(f"{ROOT}/cache/ch2_e533_large_adj.npz")
    cheap = a["cheap"]; exc = a["exc"]
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
    giant = sorted(set(d["keys"][:, 0].tolist()) | set(d["keys"][:, 1].tolist()))
    gset = set(giant)
    epochs = np.linspace(0.0, min(kt.max_time, horizon), nepochs)
    # tasks: per source i, the near-miss targets (exc & ~cheap) within the giant
    tasks = []
    for i in giant:
        js = [int(j) for j in np.where(exc[i] & ~cheap[i])[0] if int(j) in gset and int(j) != i]
        if js:
            tasks.append((i, js))
    npairs = sum(len(js) for _, js in tasks)
    print(f"[E-721b] NEAR-MISS rescan: {len(tasks)} sources, {npairs} near-miss pairs, "
          f"epochs 0-{horizon}x{nepochs}, tof 0.02-12d", flush=True)
    table = {}; done = 0; t0 = time.time()
    # RESUME
    if os.path.exists(OUT):
        try:
            prev = np.load(OUT, allow_pickle=True)
            for (x, y), r in zip(prev["keys"], prev["vals"]):
                table[(int(x), int(y))] = r
            done_src = set(int(x) for (x, y) in prev["keys"])
            tasks = [(i, js) for (i, js) in tasks if i not in done_src]
            print(f"[E-721b] RESUME: {len(table)} found, {len(done_src)} sources done", flush=True)
        except Exception:
            pass

    def save():
        if table:
            np.savez_compressed(OUT, epochs=epochs, keys=np.array(list(table.keys())),
                                vals=np.array(list(table.values()), dtype=np.float32))
    with mp.Pool(workers, initializer=_init, initargs=(epochs,)) as p:
        for res in p.imap_unordered(_row, tasks, chunksize=1):
            for (i, j, row) in res:
                table[(i, j)] = row
            done += 1
            if done % 20 == 0:
                el = time.time() - t0; rate = done / el
                print(f"  {done}/{len(tasks)} sources, {len(table)} NEW cheap edges recovered, "
                      f"eta={(len(tasks)-done)/rate/60:.0f}min [{el/60:.0f}min]", flush=True)
            if done % 60 == 0:
                save()
    save()
    print(f"[E-721b] DONE: {len(table)} previously-missing cheap edges recovered [{(time.time()-t0)/60:.0f}min] -> {OUT}", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 460.0
    ne = int(sys.argv[3]) if len(sys.argv) > 3 else 230
    main(w, h, ne)
