"""E-715 stage 1 — Ch2-large rank-1: build the TIME-EXPANDED graph for GTSP.

The only construct that yields chronologically-feasible global orderings (all tractable constructors
exhausted, E-713/714). Node = (city, epoch-bucket). Edge (i,e1)->(j,e2): cheap transfer i->j departing in
bucket e1, arriving bucket e2=e1+round(tof). GTSP = visit exactly one (city,*) copy per city, minimize sum
of tofs (= makespan for a chronological tour). Bounded to buckets <= HORIZON (rank-1=424d, so 456d cap
halves node count). Saves nodes + COO edges (src,dst,cost_milli) for the Noon-Bean->LKH solve (stage 2).
Usage: python ch2_giant_texp_build.py [bucket_d=12] [horizon_d=456]"""
import sys, time
import numpy as np
ROOT = "/home/julian/Projects/esa_spoc_26_3"
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
giant = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
gidx = {c: k for k, c in enumerate(giant)}


KEEP = 5                                                     # max distinct departure-buckets per pair (sparsify)


def main(bucket=12.0, horizon=456.0):
    nb = int(horizon // bucket) + 1
    print(f"[E-715] time-expanded build: bucket={bucket}d horizon={horizon}d -> {nb} buckets, "
          f"{len(giant)} cities, <= {len(giant)*nb} nodes", flush=True)
    # node id = city_index * nb + bucket ; only materialize nodes that are an edge endpoint
    used = np.zeros((len(giant), nb), bool)
    src = []; dst = []; cost = []
    t0 = time.time()
    for r, (i, j) in enumerate(KEYS):
        ci, cj = gidx[int(i)], gidx[int(j)]
        es = np.where(FIN[r])[0]
        if es.size == 0:
            continue
        eb = (EPOCHS[es] // bucket).astype(int)             # departure buckets
        tofs = VALS[r, es]
        seen_b = set(); kept = []                           # SPARSIFY: keep <=KEEP earliest distinct buckets
        for e1, tof in zip(eb, tofs):
            if e1 in seen_b:
                continue
            seen_b.add(e1); kept.append((int(e1), float(tof)))
            if len(kept) >= KEEP:
                break
        for e1, tof in kept:
            if e1 >= nb:
                continue
            e2 = e1 + int(round(tof / bucket))
            if e2 >= nb or e2 <= e1 - 1:
                e2 = min(nb - 1, e1 + max(1, int(round(tof / bucket))))
            if e2 >= nb:
                continue
            used[ci, e1] = True; used[cj, e2] = True
            src.append(ci * nb + e1); dst.append(cj * nb + e2); cost.append(int(tof * 1000))
        if (r + 1) % 15000 == 0:
            print(f"  {r+1}/{len(KEYS)} pairs, {len(src)} edges [{time.time()-t0:.0f}s]", flush=True)
    nodes = np.where(used.ravel())[0]
    print(f"[E-715] DONE: {len(nodes)} live nodes, {len(src)} edges [{time.time()-t0:.0f}s]", flush=True)
    np.savez_compressed(f"{ROOT}/cache/ch2_giant_texp.npz",
                        nodes=nodes, src=np.array(src, np.int64), dst=np.array(dst, np.int64),
                        cost=np.array(cost, np.int64), nb=nb, bucket=bucket, giant=np.array(giant))
    # per-city copy count (cluster sizes for GTSP)
    cc = used.sum(1)
    print(f"  per-city copies: min {cc.min()} med {int(np.median(cc))} max {cc.max()} "
          f"(GTSP clusters = {len(giant)}); saved cache/ch2_giant_texp.npz", flush=True)
    print(f"[E-715] next: Noon-Bean GTSP->ATSP transform + LKH solve (stage 2).", flush=True)


if __name__ == "__main__":
    b = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 456.0
    main(b, h)
