"""E-709b — Ch2-large: how wrong is the 8-probe cheap-edge adjacency? The entire component structure
(601-giant, 4 comps, time-ordering wall) and ALL downstream search were built on e533's adjacency, which
probed each pair at only 8 (t_start,tof) points (shortest tof 0.5d). Test: sample pairs e533 marked
NON-cheap, densely re-scan (many epochs x short tofs), count how many are ACTUALLY cheap (dv<=100). A
high error rate => the graph is under-sampled, components are artificially split, and the 'wall' + the
whole decomposition are artifacts (the search has been exploring the wrong graph).
Usage: python ch2_large_adj_recheck.py [n_sample=300] [seed=0]"""
import sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
ADJ = "/home/julian/Projects/esa_spoc_26_3/cache/ch2_e533_large_adj.npz"
kt = KTTSP(INST); n = kt.n
EPOCHS = np.arange(0.0, kt.max_time - 3, 25.0)            # dense epoch grid (~120 epochs)
TOFS = np.concatenate([np.arange(kt.min_tof, 1.0, 0.02), np.arange(1.0, 6.0, 0.2)])  # short-tof-rich


def is_cheap_dense(i, j):
    """True if compute_transfer(i,j,t,tof) <= 100 for ANY (t in EPOCHS, tof in TOFS). Returns (cheap, min_tof_if_cheap)."""
    for t in EPOCHS:
        for tof in TOFS:
            try:
                if kt.compute_transfer(i, j, float(t), float(tof)) <= kt.dv_thr:
                    return True, float(tof)
            except Exception:
                continue
    return False, None


def main(n_sample=300, seed=0):
    d = np.load(ADJ); cheap_adj = d["cheap"]; labels = d["labels"]
    n_cheap_e533 = int(cheap_adj.sum())
    sizes = np.bincount(labels)
    print(f"[E-709b] e533 adjacency: {n_cheap_e533} cheap directed edges ({100*n_cheap_e533/(n*(n-1)):.2f}%); "
          f"components (top sizes): {sorted(sizes[sizes>0].tolist(), reverse=True)[:8]}", flush=True)
    rng = np.random.default_rng(seed)
    # sample pairs e533 marked NON-cheap
    noncheap = np.argwhere(~cheap_adj)
    noncheap = noncheap[noncheap[:, 0] != noncheap[:, 1]]
    idx = rng.choice(len(noncheap), size=min(n_sample, len(noncheap)), replace=False)
    print(f"[E-709b] dense-rechecking {len(idx)} pairs e533 marked NON-cheap "
          f"({len(EPOCHS)} epochs x {len(TOFS)} tofs each) ...", flush=True)
    t0 = time.time(); now_cheap = 0; short_tofs = []
    for k, ii in enumerate(idx):
        i, j = int(noncheap[ii][0]), int(noncheap[ii][1])
        c, mtof = is_cheap_dense(i, j)
        if c:
            now_cheap += 1; short_tofs.append(mtof)
        if (k + 1) % 50 == 0:
            print(f"  {k+1}/{len(idx)}: {now_cheap} actually-cheap so far [{time.time()-t0:.0f}s]", flush=True)
    frac = now_cheap / len(idx)
    print(f"\n[E-709b] {now_cheap}/{len(idx)} ({100*frac:.0f}%) of e533-'non-cheap' pairs are ACTUALLY cheap under a dense scan", flush=True)
    if short_tofs:
        print(f"  their cheap tofs: min {min(short_tofs):.3f} med {np.median(short_tofs):.3f} (mostly missed because e533's shortest probe tof was 0.5d)", flush=True)
    if frac > 0.2:
        print(f"[E-709b] -> ADJACENCY MASSIVELY UNDER-SAMPLED. The 8-probe graph is wrong; components are "
              f"artificially split; the 'time-ordering wall' is an ARTIFACT. Rebuild the cheap graph densely "
              f"(short tofs, many epochs) -> the giant likely merges / shrinks -> global search reaches rank-1. THE FLAW.", flush=True)
    else:
        print(f"[E-709b] -> adjacency mostly correct ({100*frac:.0f}% error); the sparse graph is real, "
              f"the wall is genuine, gap is the global TD-TSP order (heavy build).", flush=True)


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    main(ns, sd)
