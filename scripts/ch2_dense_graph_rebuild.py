"""E-680: Ch2-large DENSE cheap-graph rebuild for LOW-DEGREE giant cities (user-approved 2026-06-20).

Audit finding: the cheap-edge graph (e533) was built from only 8 (t,tof) probes/pair → it UNDERCOUNTS
edges for LOW-DEGREE cities (the hard-shell cities that strand the giant; probe showed city 778 deg
11→16 with just 2 dense times). LB=15d proves 424 is achievable; the wall is partly an artifact of the
sparse graph. This re-probes the ~120 low-degree giant cities (out-deg<40) against ALL giant successors
with a dense time×tof grid, ADDING missed cheap edges. Output: cache/ch2_giant_adj_dense.npz (augmented
cheap adjacency over the giant). Then the existing greedy/LNS on the denser graph may COMPLETE the giant.

Instrumented + checkpointed (reboot-safe cache/). Usage: python ch2_dense_graph_rebuild.py [workers=3] [degthr=40]
"""
import sys, time, os
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
OUT = f"{ROOT}/cache/ch2_giant_adj_dense.npz"
TIMES = None   # set in main (depends on max_time)
TOFS = np.linspace(0.05, 40.0, 44)     # coarse tof scan to DETECT a cheap window (not min-tof)
_K = {}


def _init(times):
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST); _K['times'] = times


def _city(args):
    """probe low-degree city i against candidate successors js; return list of NEW cheap j (any t,tof)."""
    i, js = args; kt = _K['kt']; times = _K['times']; thr = kt.dv_thr
    new = []
    for j in js:
        hit = False
        for t in times:
            for tof in TOFS:
                if kt.compute_transfer(i, int(j), float(t), float(tof)) <= thr + 1e-6:
                    hit = True; break
            if hit:
                break
        if hit:
            new.append(int(j))
    return i, new


def main(workers=3, degthr=40):
    from esa_spoc_26.ch2_kttsp import KTTSP
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse import csr_matrix
    global TIMES
    kt = KTTSP(INST)
    adj = np.load(f"{ROOT}/cache/ch2_e533_large_adj.npz")['cheap'].copy()
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    g = [int(x) for x in np.where(lab == gi)[0]]; gset = set(g)
    outdeg = adj[g][:, g].sum(axis=1)
    low = [g[k] for k in range(len(g)) if outdeg[k] < degthr]
    TIMES = np.linspace(50.0, kt.max_time - 50.0, 12)
    # resume: load prior augmented adj if exists
    done = set()
    if os.path.exists(OUT):
        try:
            prev = np.load(OUT, allow_pickle=True)
            adj = prev['cheap'].copy(); done = set(int(x) for x in prev['done'])
            print(f"[E-680] RESUME: {len(done)} cities already re-probed", flush=True)
        except Exception:
            pass
    todo = [c for c in low if c not in done]
    tasks = [(c, [j for j in g if j != c and not adj[c, j]]) for c in todo]   # only non-cheap successors
    npairs = sum(len(js) for _, js in tasks)
    print(f"[E-680] low-deg(<{degthr}) cities={len(low)} todo={len(todo)} non-cheap-pairs={npairs} "
          f"| grid {len(TIMES)}t x {len(TOFS)}tof | est~{npairs*len(TIMES)*len(TOFS)*5e-5/workers/60*0.6:.0f}min", flush=True)
    added = 0; nc_done = len(done); t0 = time.time()
    with mp.Pool(workers, initializer=_init, initargs=(TIMES,)) as p:
        for i, new in p.imap_unordered(_city, tasks, chunksize=1):
            for j in new:
                adj[i, j] = True; added += 1
            done.add(i); nc_done += 1
            if nc_done % 5 == 0:
                el = time.time() - t0; rate = (nc_done - len(set(done) - set(todo))) / max(el, 1)
                print(f"  {nc_done}/{len(low)} cities | +{added} new edges so far [{el/60:.0f}min]", flush=True)
            if nc_done % 10 == 0:
                np.savez_compressed(OUT, cheap=adj, done=np.array(sorted(done)))
    np.savez_compressed(OUT, cheap=adj, done=np.array(sorted(done)))
    # report new structure
    nc2, lab2 = connected_components(csr_matrix(adj), directed=False)
    gi2 = int(np.argmax(np.bincount(lab2))); gsz = int((lab2 == gi2).sum())
    print(f"[E-680] DONE +{added} cheap edges added to {len(low)} low-deg cities [{(time.time()-t0)/60:.0f}min]", flush=True)
    print(f"  components now: {nc2} (was 4) | giant size now: {gsz} (was 601) -> {OUT}", flush=True)
    print(f"  NEXT: re-run greedy/LNS on this denser graph (cache/ch2_giant_adj_dense.npz) — does the giant COMPLETE?", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    dt = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    main(w, dt)
