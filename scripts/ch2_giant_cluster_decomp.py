"""E-720 BREAKTHROUGH LEVER — Ch2-large rank-1: inclination-band cluster decomposition.

Structural discovery (E-720): the 601 giant is organized by INCLINATION. Within a band: ~98% cheap density,
transfers as short as 0.05d. Between bands (high<->low inc): essentially no cheap edges. The forward beam's
0.527 d/leg is INFLATED by band-mixing (repeated expensive inter-band hops). Fix (TGMA-style): thread each
band internally (cheap+dense => easy & fast), order the bands, cross bands only B-1 times via the cheapest
available transition (cheap bridge if any, else one of the 5 exceptions). Concatenate -> faithful retime ->
fine verify. If giant < ~405d => full < 424.62 = RANK-1.

Usage: python ch2_giant_cluster_decomp.py [n_bands=6] [feature=inc] [tag=a]"""
import sys, json, time, itertools
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = KTTSP("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp")
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
OUTADJ = defaultdict(set)
for (i, j) in KEYS:
    if FIN[PIDX[(int(i), int(j))]].any():
        OUTADJ[int(i)].add(int(j))
opar = np.array(kt.opar)
_RF = {}


def rowfin(row):
    fe = _RF.get(row)
    if fe is None:
        fe = np.where(FIN[row])[0]; _RF[row] = fe
    return fe


def cheap_arr_t(i, j, t):                                        # fast table arrival
    row = PIDX.get((i, j))
    if row is None:
        return None
    fe = rowfin(row)
    if fe.size == 0:
        return None
    e0 = np.searchsorted(EPOCHS, t); p = np.searchsorted(fe, e0)
    if p >= fe.size:
        return None
    e = fe[p]
    return max(t, float(EPOCHS[e])) + float(VALS[row, e])


def exc_arr_t(i, j, t):                                          # cheapest exception arrival (Lambert)
    e0 = np.searchsorted(EPOCHS, t)
    best = None
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 12)):
        dep = max(t, float(EPOCHS[e]))
        for tof in np.arange(kt.min_tof, 8.0, 0.1):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_exc:
                a = dep + float(tof)
                if best is None or a < best:
                    best = a
                break
    return best


def thread_band(members, t0, used):
    """greedy earliest-arrival chain within a band (dense cheap), from the best start; returns (order, t)."""
    members = set(members) - used
    if not members:
        return [], t0
    # start from the member with most intra-band out-edges (hub)
    start = max(members, key=lambda c: len(OUTADJ[c] & members))
    order = [start]; cur = start; t = t0; members.discard(start)
    while members:
        best = None
        for j in members:
            a = cheap_arr_t(cur, j, t)
            if a is not None and (best is None or a < best[0]):
                best = (a, j)
        if best is None:
            break                                                # band fragment unreachable from here
        t = best[0]; cur = best[1]; order.append(cur); members.discard(cur)
    return order, t


def main(n_bands=6, feature="inc", tag="a"):
    inc = opar[:, 2]
    gi = np.array(cities)
    feat = inc[gi] if feature == "inc" else opar[gi, 2]
    # bands = quantile splits of the feature
    edges = np.quantile(feat, np.linspace(0, 1, n_bands + 1))
    edges[-1] += 1e-6
    band_of = {}
    bands = [[] for _ in range(n_bands)]
    for c in cities:
        b = min(n_bands - 1, int(np.searchsorted(edges, inc[c], "right") - 1))
        band_of[c] = b; bands[b].append(c)
    print(f"[CLUST-{tag}] {n_bands} inclination bands sizes {[len(b) for b in bands]}; feature={feature}", flush=True)
    t0 = time.time()
    # thread each band internally (independent of order, started at t=0 to measure intra-cost)
    threaded = {}
    for b in range(n_bands):
        o, tend = thread_band(bands[b], 0.0, set())
        threaded[b] = o
        print(f"  band {b}: {len(o)}/{len(bands[b])} threaded, intra-span {tend:.1f}d (d/leg {tend/max(len(o)-1,1):.3f})", flush=True)
    # order the bands greedily by cheapest inter-band transition, chaining in time
    order_all = []; t = 0.0; exc = 0; remaining = list(range(n_bands))
    # start with band that threads most cities
    cur_b = max(remaining, key=lambda b: len(threaded[b]))
    seq, t = thread_band(bands[cur_b], 0.0, set())
    order_all.extend(seq); remaining.remove(cur_b)
    while remaining:
        last = order_all[-1]
        # choose next band + entry city minimizing transition arrival (cheap, else exception)
        best = None  # (arrival, band, is_exc)
        for b in remaining:
            for entry in bands[b][:60]:
                a = cheap_arr_t(last, entry, t)
                ie = 0
                if a is None and exc < kt.n_exc:
                    a = exc_arr_t(last, entry, t); ie = 1
                if a is not None and (best is None or a < best[0]):
                    best = (a, b, entry, ie)
        if best is None:
            print(f"  [CLUST-{tag}] STUCK bridging to remaining bands {remaining} at t={t:.1f}", flush=True)
            break
        a, b, entry, ie = best
        t = a; exc += ie
        # thread band b starting from `entry` at time t
        seq, t = thread_band([c for c in bands[b]], t, set())
        # ensure entry first: reorder seq to start at entry if present
        if entry in seq:
            seq = [entry] + [c for c in seq if c != entry]
            # re-thread from entry for correct timing
            seq2, t = thread_band(bands[b], a, set()) if False else (seq, t)
        order_all.extend(seq); remaining.remove(b)
        print(f"  bridged to band {b} ({'EXC' if ie else 'cheap'}) -> total {len(order_all)}/601, t={t:.1f}d, exc={exc}", flush=True)
    # final faithful retime of the assembled order
    tt = 0.0; strand = 0
    for k in range(len(order_all) - 1):
        r = cheap_arr_t(order_all[k], order_all[k + 1], tt)
        if r is None:
            strand += 1; tt += 6.0
        else:
            tt = r
    print(f"\n[CLUST-{tag}] DONE: {len(order_all)}/601 cities, makespan {tt:.1f}d (d/leg {tt/600:.3f}), "
          f"strands {strand}, exc {exc} [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order_all, "makespan": tt, "strands": strand, "exc": exc},
              open(f"{ROOT}/cache/ch2_giant_cluster_{tag}.json", "w"))
    if len(order_all) >= 599 and strand <= 5 and tt < 405:
        print(f"[CLUST-{tag}] *** RANK-1 giant {tt:.0f}d -> stitch + verify + escalate.", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 6, a[2] if len(a) > 2 else "inc", a[3] if len(a) > 3 else "a")
