"""E-672b: DIRECT 1-day-resolution cheap-window precompute for the Ch2-large giant (user-approved 2026-06-19).

WHY: the 4d table (E-670) OVERFITS — beam orders look 0.6 d/leg on it but retime FAITHFULLY to ~1000d
(tof sampled at the bucket epoch, used up to 2d away). A 1d grid cuts that error ~4x. Built DIRECTLY from
the cheap adjacency (no 4d-mask dependency — masking didn't actually speed it up: cheap pairs have large
masks). ~18h on 4 cores.

★ ROBUST per user 2026-06-19 (a reboot wiped /tmp mid-run): output to PERSISTENT cache/ (survives reboot),
SAVE every 25 rows, RESUME on restart (skip done cities), heartbeat every 2 rows. Usage: python ... [workers=4]
"""
import sys, time, os
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ = f"{ROOT}/cache/ch2_e533_large_adj.npz"
OUT = f"{ROOT}/cache/ch2_giant_dense1d.npz"
NEPOCHS = 950
TOFS = np.concatenate([np.linspace(0.02, 2.0, 120), np.linspace(2.1, 8.0, 50)])
_K = {}


def _init(epochs):
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST); _K['eps'] = epochs


COARSE = 16   # coarse pre-scan every 16th 1d-epoch (~16d); fine-scan ±COARSE around cheap-coarse hits


def _scan(kt, i, j, t, thr):
    for tof in TOFS:
        if kt.compute_transfer(i, j, float(t), float(tof)) <= thr + 1e-6:
            return float(tof)
    return np.inf


def _row(args):
    """COARSE-then-FINE: cheap pre-scan locates cheap regions (~60 epochs), then fine 1d-scan only
    within ±COARSE of a cheap-coarse hit — skips the expensive None-scans over empty regions."""
    i, js = args; kt = _K['kt']; eps = _K['eps']; thr = kt.dv_thr; ne = len(eps)
    out = np.full((len(js), ne), np.inf, dtype=np.float32)
    cidx = range(0, ne, COARSE)
    for jk, j in enumerate(js):
        j = int(j); hits = []
        for ci in cidx:
            v = _scan(kt, i, j, eps[ci], thr)
            out[jk, ci] = v
            if np.isfinite(v):
                hits.append(ci)
        fine = set()
        for ci in hits:
            fine.update(range(max(0, ci - COARSE), min(ne, ci + COARSE + 1)))
        for ek in fine:
            if not np.isfinite(out[jk, ek]):
                out[jk, ek] = _scan(kt, i, j, eps[ek], thr)
    return i, js, out


def main(workers=4):
    from esa_spoc_26.ch2_kttsp import KTTSP
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse import csr_matrix
    kt = KTTSP(INST)
    adj = np.load(ADJ)['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; gset = set(gnodes)
    epochs = np.linspace(0.0, min(kt.max_time, 950.0), NEPOCHS)
    pairs_by_i = {i: [int(j) for j in np.where(adj[i])[0] if int(j) in gset] for i in gnodes}
    pairs_by_i = {i: js for i, js in pairs_by_i.items() if js}
    npairs = sum(len(v) for v in pairs_by_i.values())
    # RESUME from persistent cache
    table = {}; done_cities = set()
    if os.path.exists(OUT):
        try:
            prev = np.load(OUT, allow_pickle=True)
            for (a, b), r in zip(prev['keys'], prev['vals']):
                table[(int(a), int(b))] = r; done_cities.add(int(a))
            print(f"[E-672b] RESUME: {len(table)} pairs, {len(done_cities)} cities done", flush=True)
        except Exception as e:
            print(f"[E-672b] resume failed ({str(e)[:40]}) — fresh", flush=True)
    cd = kt.compute_transfer(gnodes[0], gnodes[1], 0.0, 0.5)
    print(f"[E-672b] DIRECT-1d giant={len(gnodes)} pairs={npairs} epochs={NEPOCHS} | control={cd:.0f} "
          f"| {len(done_cities)} done | est~{npairs*NEPOCHS*len(TOFS)*5e-5/workers/3600:.1f}h", flush=True)
    tasks = [(i, js) for i, js in pairs_by_i.items() if i not in done_cities]
    total = len(pairs_by_i); done = len(done_cities); t0 = time.time()

    def save():
        np.savez_compressed(OUT, epochs=epochs, keys=np.array(list(table.keys())),
                            vals=np.array(list(table.values()), dtype=np.float32))

    with mp.Pool(workers, initializer=_init, initargs=(epochs,)) as p:
        for i, js, out in p.imap_unordered(_row, tasks, chunksize=1):
            for jk, j in enumerate(js):
                table[(i, int(j))] = out[jk]
            done += 1
            nd = done - len(done_cities)
            if done % 2 == 0:
                el = time.time() - t0; rate = nd / el if nd else 1e-9
                print(f"  {done}/{total} rows eta={(total-done)/rate/60:.0f}min [{el/60:.0f}min]", flush=True)
            if done % 25 == 0:
                save()
    save()
    print(f"[done] {(time.time()-t0)/60:.0f}min | {len(table)} pairs x {NEPOCHS} epochs -> {OUT}", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(w)
