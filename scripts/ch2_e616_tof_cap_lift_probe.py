"""E-616 — Does the tof<=8d precompute cap artificially fragment the Ch2 cheap graph?

Every Ch2 method (beam, DP-ALNS, CP-SAT E-518) searches a cheap-edge graph built
by ch2_e526 which scans ONLY time-of-flight <= 8.0 d (and epoch <= max_time). The
official problem caps a leg only by dv (<=100 cheap / <=600 exception) and the
total makespan (<=max_time); it does NOT cap per-leg tof at 8 d. In a
time-dependent tour a longer "repositioning" leg at a better orbital phase can be
dv-cheap AND unlock a chain of short cheap legs that otherwise need an expensive
exception bridge or a long detour -> can LOWER makespan. We have never searched
with tof>8 d. This probe asks the binary question: are there dv<=100 transfers
with tof in (8, TOF_MAX] connecting pairs that are UNREACHABLE-cheap under tof<=8?

Read-only; banks nothing. Prints newly-connected directed pairs + which low-degree
nodes gain cheap edges (the scarce nodes that strand the beam tail).

Usage: python ch2_e616_tof_cap_lift_probe.py [TOF_MAX=40] [N_WORK=3]
"""
import sys
import time
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
ULTRAFINE = '/tmp/ch2_small_tcoupled_ultrafine.npz'
DV_CAP = 100.0

TOF_MAX = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
N_WORK = int(sys.argv[2]) if len(sys.argv) > 2 else 3

# scan grids (coarse epoch is fine for a reachability signal)
EPOCH_STEP = 1.0
TOF_LO = 8.0          # start above the existing precompute cap
TOF_STEP = 0.5

_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan_pair(ij):
    """Return (i, j, best_tof) for the smallest tof in (TOF_LO, TOF_MAX] with
    dv<=100 at some epoch, else (i, j, None)."""
    i, j = ij
    kt = _KT[0]
    max_t = kt.max_time
    epochs = np.arange(0.0, max_t, EPOCH_STEP)
    tofs = np.arange(TOF_LO + TOF_STEP, TOF_MAX + 1e-9, TOF_STEP)
    best = None
    for ts in epochs:
        if ts + TOF_LO > max_t:
            break
        for tof in tofs:
            if ts + tof > max_t:
                break
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= DV_CAP:
                if best is None or tof < best:
                    best = float(tof)
                break  # smallest tof at this epoch found
    return (i, j, best)


def main():
    kt = KTTSP(INST)
    n = kt.n
    d = np.load(ULTRAFINE)
    cheap = d['cheap']                      # (n, n, T) min cheap tof per epoch
    cur_adj = np.isfinite(cheap).any(axis=2)  # reachable-cheap under tof<=8
    np.fill_diagonal(cur_adj, False)
    cur_pairs = int(cur_adj.sum())
    out_deg = cur_adj.sum(axis=1)
    in_deg = cur_adj.sum(axis=0)
    print(f"[E-616] n={n} TOF_MAX={TOF_MAX}d  current cheap directed pairs="
          f"{cur_pairs}/{n*(n-1)} ({100*cur_pairs/(n*(n-1)):.1f}%)", flush=True)
    print(f"  current out-deg min/med/max="
          f"{out_deg.min()}/{int(np.median(out_deg))}/{out_deg.max()}; "
          f"low-deg(<=2) nodes="
          f"{int((out_deg<=2).sum())} -> {np.where(out_deg<=2)[0].tolist()}",
          flush=True)

    todo = [(i, j) for i in range(n) for j in range(n)
            if i != j and not cur_adj[i, j]]
    print(f"  scanning {len(todo)} currently-UNREACHABLE pairs at tof in "
          f"({TOF_LO},{TOF_MAX}]d, epoch step {EPOCH_STEP}d, {N_WORK} workers...",
          flush=True)

    t0 = time.time()
    new_edges = []
    with mp.Pool(N_WORK, initializer=_init) as pool:
        for k, (i, j, btof) in enumerate(
                pool.imap_unordered(_scan_pair, todo, chunksize=16)):
            if btof is not None:
                new_edges.append((i, j, btof))
            if (k + 1) % 500 == 0:
                print(f"    {k+1}/{len(todo)} scanned, "
                      f"{len(new_edges)} new edges, {time.time()-t0:.0f}s",
                      flush=True)

    print(f"\n[RESULT] newly-reachable directed pairs (tof in "
          f"({TOF_LO},{TOF_MAX}]): {len(new_edges)} "
          f"(+{100*len(new_edges)/(n*(n-1)):.1f}% of all pairs) "
          f"in {time.time()-t0:.0f}s", flush=True)

    if new_edges:
        new_out = np.zeros(n, dtype=int)
        new_in = np.zeros(n, dtype=int)
        for i, j, _ in new_edges:
            new_out[i] += 1
            new_in[j] += 1
        gained = [(int(v), int(out_deg[v]), int(new_out[v]))
                  for v in range(n) if out_deg[v] <= 4 and new_out[v] > 0]
        print(f"  low-deg nodes (old out-deg<=4) that GAIN cheap out-edges:")
        for v, od, ng in sorted(gained, key=lambda r: r[1]):
            print(f"    node {v}: out-deg {od} -> {od+ng} (+{ng} via tof>8)",
                  flush=True)
        tofs = sorted(e[2] for e in new_edges)
        print(f"  new-edge tof: min={tofs[0]:.1f} med={tofs[len(tofs)//2]:.1f} "
              f"max={tofs[-1]:.1f} d", flush=True)
        print(f"\n[VERDICT] tof<=8 cap DOES fragment the cheap graph. Rebuild the "
              f"adjacency/precompute with tof<={TOF_MAX}d and re-run beam/DP — the "
              f"floor may move. Especially relevant for the scarce low-deg nodes "
              f"that strand the construction tail.", flush=True)
    else:
        print(f"\n[VERDICT] NO new cheap edges from longer tof — the cheap graph "
              f"is NOT fragmented by the tof<=8 cap (for dv<=100). The floor is a "
              f"pure search/ordering gap, not a connectivity artifact.", flush=True)


if __name__ == '__main__':
    main()
