"""E-721 FOUNDATIONAL FIX — Ch2-large: recompute the giant cheap-edge graph PROPERLY.

THE BUG (E-720/721): the cheap-edge graph (cache/ch2_e533_large_adj.npz) was built by probing only 8 fixed
(t,tof) cells per pair across the 3000d horizon (ch2_e533_large_structure.py). Cheap windows are narrow and
recur on the synodic beat, so 8 samples MISS most of them => edges that ARE cheap were declared non-cheap and
vanished. The dense1d table only refined adj-accepted pairs, so it inherited every false negative. The
"566 cap / 35 hard cities / 4 components" all sit on this under-sampled graph. Confirmed: a hard city had 28
cheap predecessors absent from the graph entirely.

FIX: scan ALL giant pairs (not just adj-accepted) over the RANK-1 time window 0-HORIZON (rank-1 lives <425d,
so we don't need 0-3000), coarse-then-fine, recording min-tof per epoch for every truly-cheap pair. Output a
NEW complete table cache/ch2_giant_dense1d_v2.npz with the same schema (epochs/keys/vals) so the beam runs on
it unchanged. The giant city SET is taken from the union of dense1d keys (the 601 known giant cities) — the
SAME cities, just with their full (recovered) edge set.

Usage: python ch2_giant_graph_recompute.py [workers=4] [horizon=460] [nepochs=230]"""
import sys, time, os
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = f"{ROOT}/cache/ch2_giant_dense1d_v2.npz"
TOFS = np.concatenate([np.linspace(0.02, 2.0, 90), np.linspace(2.1, 12.0, 50)])   # 0.02-12d (short+moderate)
COARSE = 8                                                       # coarse pre-scan every 8th epoch; fine ±8
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
    """one source i vs ALL giant targets js: coarse-then-fine min-tof per epoch. Returns only CHEAP pairs."""
    i, js = args; kt = _K['kt']; eps = _K['eps']; thr = kt.dv_thr; ne = len(eps)
    cidx = list(range(0, ne, COARSE))
    res = []
    for j in js:
        j = int(j)
        if j == i:
            continue
        row = np.full(ne, np.inf, dtype=np.float32); hits = []
        for ci in cidx:
            v = _scan(kt, i, j, eps[ci], thr); row[ci] = v
            if np.isfinite(v):
                hits.append(ci)
        if not hits:
            continue                                            # genuinely non-cheap (no coarse hit) -> drop
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
    import json
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST)
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
    giant = sorted(set(d["keys"][:, 0].tolist()) | set(d["keys"][:, 1].tolist()))
    # FOCUS = the stranded hard cities; recompute their in- AND out-edges (where the 8-probe under-count bites)
    focus = sorted(int(c) for c in json.load(open(f"{ROOT}/cache/ch2_giant_stranded35.json")))
    epochs = np.linspace(0.0, min(kt.max_time, horizon), nepochs)
    print(f"[E-721] FOCUSED recompute: {len(focus)} stranded cities, in+out edges vs all {len(giant)} giant "
          f"(~{len(focus)*len(giant)*2} pairs), epochs 0-{horizon} x{nepochs}, tof 0.02-12d, COARSE={COARSE}", flush=True)
    table = {}
    # in-edges of focus: each source i (all giant) scanned vs js=focus ; out-edges: each focus f vs js=giant
    tasks = [(i, focus) for i in giant] + [(f, giant) for f in focus]
    t0 = time.time(); done = 0; ntask = len(tasks)

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
                el = time.time() - t0; rate = done / el if done else 1e-9
                print(f"  {done}/{ntask} tasks, {len(table)} focus cheap pairs recovered, "
                      f"eta={(ntask-done)/rate/60:.0f}min [{el/60:.0f}min]", flush=True)
            if done % 80 == 0:
                save()
    save()
    print(f"[E-721] DONE: {len(table)} focus cheap pairs [{(time.time()-t0)/60:.0f}min] -> {OUT}", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 460.0
    ne = int(sys.argv[3]) if len(sys.argv) > 3 else 230
    main(w, h, ne)
