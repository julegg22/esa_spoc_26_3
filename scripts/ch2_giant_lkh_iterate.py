"""E-713 — Ch2-large rank-1: LKH (elkai) on the giant with FINE-tof retiming, iterated.

The competitor's inferred tool is LKH. Prior static-LKH was dismissed as "inflates / diverges" — but that
used COARSE-tof retiming, which E-710 proved artificially inflates makespan (steps over the ~0.002d cheap
band). With the fine-tof oracle, the realized makespan of an LKH tour is measured ACCURATELY, and the
LKH<->retime fixed point may converge. Also: the 17 cities greedy-insertion stranded are MOSTLY high-degree
(in/out ~150) core cities it mis-placed, not periphery -> a global solver has real headroom.

Loop: build cost matrix C (min cheap tof; big penalty for non-cheap) -> elkai TSP (open path via dummy) ->
fine-tof retime -> measure realized makespan + per-leg realized tof -> set C[leg]=realized for the tour's
legs -> re-solve. Keep best realized COMPLETE tour. Target giant <~405d (rank-1 leaves ~19d for satellites).
Usage: python ch2_giant_lkh_iterate.py [iters=6]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
import elkai
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
giant = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(giant); gidx = {c: k for k, c in enumerate(giant)}
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
BIG = 9.0                                                          # non-cheap penalty (d), >> any cheap tof
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)


def cheap_arr(i, j, t, dv_cap):
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep + float(tof), float(tof)
    return None


def retime(seq):
    """fine-tof chronological retime; returns (makespan, exc, realized_tofs dict, n_strand)."""
    t = 0.0; exc = 0; tofs = {}; strand = 0
    for k in range(len(seq) - 1):
        a, b = seq[k], seq[k + 1]
        r = cheap_arr(a, b, t, kt.dv_thr)
        if r is None and exc < kt.n_exc:
            r = cheap_arr(a, b, t, kt.dv_exc)
            if r:
                exc += 1
        if r is None:
            strand += 1
            r = (t + BIG, BIG)                                    # penalize, keep going
        t = r[0]; tofs[(a, b)] = r[1]
    return t, exc, tofs, strand


def build_C():
    C = np.full((NG + 1, NG + 1), BIG, np.float64)                # node 0 = dummy (open path)
    for r, (i, j) in enumerate(KEYS):
        if np.isfinite(GMIN[r]):
            C[gidx[int(i)] + 1, gidx[int(j)] + 1] = GMIN[r]
    C[0, :] = 0.0; C[:, 0] = 0.0; np.fill_diagonal(C, 0.0)
    return C


def lkh_tour(C):
    M = (np.minimum(C, BIG) * 1000).astype(np.int64)
    cyc = elkai.solve_int_matrix(M.tolist())                      # cycle through dummy 0
    z = cyc.index(0); order = cyc[z + 1:] + cyc[:z]               # rotate so dummy first, drop it
    return [giant[n - 1] for n in order if n != 0]


def main(iters=6):
    print(f"[E-713] LKH+fine-retime on giant n={NG}; elkai; target <405d (rank-1)", flush=True)
    C = build_C(); best = None; t0 = time.time()
    for it in range(iters):
        order = lkh_tour(C)
        mk, exc, tofs, strand = retime(order)
        print(f"  it{it}: LKH tour -> realized makespan {mk:.1f}d, exc {exc}, strands {strand} "
              f"[{time.time()-t0:.0f}s]", flush=True)
        if strand == 0 and (best is None or mk < best[0]):
            best = (mk, list(order))
            json.dump({"order": order, "makespan": mk, "exc": exc},
                      open(f"{ROOT}/cache/ch2_giant_lkh_best.json", "w"))
        # update cost matrix with realized tofs for this tour's legs (teach LKH the time-dependent reality)
        for (a, b), tof in tofs.items():
            C[gidx[a] + 1, gidx[b] + 1] = min(C[gidx[a] + 1, gidx[b] + 1] + 0.0, tof)
        for k in range(len(order) - 1):
            a, b = order[k], order[k + 1]
            C[gidx[a] + 1, gidx[b] + 1] = tofs[(a, b)]
    if best:
        print(f"\n[E-713] BEST complete giant tour: {best[0]:.1f}d (rank-1 needs <~405d) [{time.time()-t0:.0f}s]", flush=True)
        if best[0] < 424:
            print(f"[E-713] *** RANK-1 TERRITORY ({best[0]:.0f}d) -> stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
        else:
            print(f"[E-713] above rank-1 ({best[0]:.0f}d); gap {best[0]-405:.0f}d. LKH+fine-retime is the right tool but "
                  f"the time-dependent realized cost still exceeds rank-1; needs more iters / better time-aware cost.", flush=True)
    else:
        print(f"\n[E-713] no strand-free LKH tour found in {iters} iters.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
