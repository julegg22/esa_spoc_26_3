"""E-711 — Ch2-large rank-1 closer: INSERTION REPAIR of the stranded periphery.

Diagnostic (strand_analysis): the ~61 stranded cities are NOT deadline-closed (windows open the full
horizon) — they are LOW-DEGREE (in-deg 11 vs visited 152), so the makespan-greedy beam skips them as
detours. Fix: splice each stranded city j into the 540-order at a position (a -> j -> b) where both legs
are cheap at the running clock, re-timing the suffix faithfully; accept the min-makespan-increase feasible
insertion (<=5 exceptions total). Uses the fast-faithful oracle (table-propose + fine verify, C-033).
Greedy: hardest (lowest-degree) cities first. Reports completed count + faithful makespan vs rank-1 424.
Usage: python ch2_giant_insertion_repair.py"""
import json, sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
indeg = defaultdict(int)
for (i, j) in KEYS:
    indeg[int(j)] += 1
ck = json.load(open(f"{ROOT}/cache/ch2_giant_fine_beam_best.json"))
order = list(ck["path"])
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
stranded = [c for c in cities if c not in set(order)]
stranded.sort(key=lambda c: indeg[c])                              # hardest (lowest in-degree) first


def cheap_arr(i, j, t, dv_cap):
    """earliest <=dv_cap arrival for (i,j) departing >= t; table-proposed + fine verify. (dep,tof,arr) or None."""
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
                return dep, float(tof), dep + float(tof)
    return None


def retime(seq, t0=0.0, exc0=0, start=0):
    """faithful forward retime of seq from index `start` at clock t0/exc0. Returns (times, makespan, exc) or
    None if it strands. times[k] = arrival at seq[k] (times[start-1] implied by t0)."""
    t = t0; exc = exc0; times = [None] * len(seq)
    for k in range(start, len(seq)):
        if k == 0:
            times[k] = 0.0
            continue
        a, b = seq[k - 1], seq[k]
        r = cheap_arr(a, b, t, kt.dv_thr)
        if r is None and exc < kt.n_exc:
            r = cheap_arr(a, b, t, kt.dv_exc)
            if r is not None:
                exc += 1
        if r is None:
            return None
        t = r[2]; times[k] = t
    return times, t, exc


def main():
    print(f"[E-711] insertion repair: order {len(order)}/{len(cities)}, {len(stranded)} stranded "
          f"(in-deg {indeg[stranded[0]]}..{indeg[stranded[-1]]})", flush=True)
    base = retime(order)
    if base is None:
        print("[E-711] base order does not retime cleanly; aborting", flush=True)
        return
    times, mk, exc = base
    print(f"[E-711] base retimed: makespan {mk:.1f}d, exc {exc}/{kt.n_exc}", flush=True)
    cur = list(order); cur_times = list(times); cur_exc = exc
    inserted = 0; t0 = time.time()
    for n, j in enumerate(stranded):
        best = None                                                # (makespan, new_order, new_times, new_exc, pos)
        preds = [c for c in set(cur) if (c, j) in PIDX]            # j's predecessors present in tour
        for k in range(len(cur) - 1):
            a, b = cur[k], cur[k + 1]
            if a not in preds:
                continue
            t_a = cur_times[k]
            r1 = cheap_arr(a, j, t_a, kt.dv_thr); use_exc = 0
            if r1 is None and cur_exc < kt.n_exc:
                r1 = cheap_arr(a, j, t_a, kt.dv_exc); use_exc = 1 if r1 else 0
            if r1 is None:
                continue
            # re-time suffix starting at j
            newseq = cur[:k + 1] + [j] + cur[k + 1:]
            rt = retime(newseq, t0=cur_times[k], exc0=cur_exc + use_exc, start=k + 1)
            if rt is None:
                continue
            nt, nmk, nexc = rt
            if best is None or nmk < best[0]:
                best = (nmk, newseq, nt, nexc, k)
        if best is not None:
            _, cur, cur_times, cur_exc, pos = best
            inserted += 1
            if inserted % 5 == 0 or n < 3:
                print(f"  inserted {inserted}/{len(stranded)} (city {j} indeg {indeg[j]} @pos {pos}); "
                      f"makespan {best[0]:.1f}d exc {cur_exc} [{time.time()-t0:.0f}s]", flush=True)
    final_mk = cur_times[-1]
    print(f"\n[E-711] DONE: inserted {inserted}/{len(stranded)} -> {len(cur)}/{len(cities)} visited, "
          f"makespan {final_mk:.1f}d, exc {cur_exc}/{kt.n_exc}; rank-1=424.62 [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": cur, "visited": len(cur), "makespan": final_mk, "exc": cur_exc},
              open(f"{ROOT}/cache/ch2_giant_repaired.json", "w"))
    if len(cur) >= len(cities) - 2 and final_mk < 424:
        print(f"[E-711] *** COMPLETE giant @ {final_mk:.0f}d < rank-1 424 -> stitch satellites + udp verify + bank.", flush=True)
    elif inserted > 0:
        print(f"[E-711] partial: closed {inserted} of {len(stranded)}. Remaining need 2-opt slack / different base order.", flush=True)
    else:
        print(f"[E-711] no insertions feasible -> stranded need slack created (2-opt) before insertion.", flush=True)


if __name__ == "__main__":
    main()
