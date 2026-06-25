"""E-721c — build a CLEAN complete table for fast (no-Lambert) retime.

The merge_aug table resampled the original 950-epoch table onto a 230-epoch 0-460 grid -> the stored
(epoch, min-tof) pairs became ~1d inconsistent (tof computed for the old epoch time, used at a new one). The
beam survived (it fine-verifies with compute_transfer) but a raw table-lookup retime (LNS) strands. Fix:
rescan ONLY the recovered pairs (v2 focus + nm near-miss keys) on the EXACT original 950-epoch grid, then
merge with the original dense1d (same grid => consistent) -> cache/ch2_giant_dense1d_clean.npz. table_arr is
then correct and fast for the LNS.
Usage: python ch2_giant_clean_table.py [workers=4]"""
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = f"{ROOT}/cache/ch2_giant_dense1d_clean.npz"
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
    cidx = list(range(0, ne, COARSE)); res = []
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


def main(workers=4):
    from esa_spoc_26.ch2_kttsp import KTTSP
    o = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
    OEP = o["epochs"]; OK = o["keys"]; OV = o["vals"]                 # original grid (0-950, 950 epochs)
    # recovered pairs = v2 (focus) ∪ nm (near-miss) keys, NOT already in original
    orig = set((int(a), int(b)) for (a, b) in OK)
    rec = set()
    for f in ("ch2_giant_dense1d_v2.npz", "ch2_giant_dense1d_nm.npz"):
        try:
            k = np.load(f"{ROOT}/cache/{f}")["keys"]
            for (a, b) in k:
                if (int(a), int(b)) not in orig:
                    rec.add((int(a), int(b)))
        except FileNotFoundError:
            pass
    from collections import defaultdict
    bysrc = defaultdict(list)
    for (a, b) in rec:
        bysrc[a].append(b)
    tasks = [(i, js) for i, js in bysrc.items()]
    print(f"[E-721c] rescanning {len(rec)} recovered pairs on ORIGINAL grid (0-{OEP.max():.0f}, {len(OEP)}ep), "
          f"{len(tasks)} sources", flush=True)
    table = {}
    t0 = time.time(); done = 0
    with mp.Pool(workers, initializer=_init, initargs=(OEP,)) as p:
        for res in p.imap_unordered(_row, tasks, chunksize=1):
            for (i, j, row) in res:
                table[(i, j)] = row
            done += 1
            if done % 20 == 0:
                el = time.time() - t0
                print(f"  {done}/{len(tasks)} sources, {len(table)} recovered windows [{el/60:.0f}min]", flush=True)
    # merge: original (untouched) + recovered (same grid)
    keys = list((int(a), int(b)) for (a, b) in OK)
    vals = [OV[r] for r in range(len(OK))]
    for (i, j), row in table.items():
        keys.append((i, j)); vals.append(row)
    np.savez_compressed(OUT, epochs=OEP, keys=np.array(keys), vals=np.array(vals, dtype=np.float32))
    print(f"[E-721c] DONE: clean table {len(keys)} edges (orig {len(OK)} + recovered {len(table)}) on the "
          f"original grid -> {OUT} [{(time.time()-t0)/60:.0f}min]", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
