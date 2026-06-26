"""E-726c — Ch2-large rank-1: faithful insertion-COMPLETION of the 583-city beam order.

Audit E-726 + targeted test: the beam threads 583/601 at rank-1 pace; 17/18 missing cities are reachable from
an in-tour predecessor via the FAITHFUL epoch-dense evaluator (the sparse table lacked the windows). So instead
of a full ~2h window precompute or a from-scratch beam, INSERT the 18 missing cities into the 583-order using
faithful windows + faithful incremental re-time. Tests whether the faithful windows complete 601 near rank-1
pace (the corner-paint was a window-SPARSITY artifact). Reuses the faithful timebeam (numba evaluator).
Usage: python ch2_giant_faithful_complete.py [order_json] [maxwait=25]"""
import sys, json, time, glob
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_timebeam as tb                                   # faithful windows() (numba CT + fine fallback)
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
KEYS = tb.KEYS; FIN = tb.FIN
giant = set(int(c) for c in set(KEYS[:, 0]) | set(KEYS[:, 1]))
INADJ = defaultdict(set); OUTADJ = defaultdict(set)
for r, (i, j) in enumerate(KEYS):
    if FIN[r].any():
        INADJ[int(j)].add(int(i)); OUTADJ[int(i)].add(int(j))
INDEG = {c: len(INADJ[c]) for c in giant}
SP = 50.0


def retime(order, maxwait, frm=0, t0=0.0):
    """faithful greedy W=1 retime from position frm; returns arrival times list and strand count."""
    times = [0.0] * (frm + 1) if frm == 0 else None
    t = t0; out = []; strand = 0
    for k in range(frm, len(order) - 1):
        w = tb.windows(order[k], order[k + 1], t, 1, maxwait)
        if w:
            t = w[0][1]
        else:
            t += SP; strand += 1
        out.append(t)
    return out, strand


def full_retime(order, maxwait):
    t = 0.0; times = [0.0]; strand = 0
    for k in range(len(order) - 1):
        w = tb.windows(order[k], order[k + 1], t, 1, maxwait)
        if w:
            t = w[0][1]
        else:
            t += SP; strand += 1
        times.append(t)
    return times, strand


def main(order_json=None, maxwait=25):
    if order_json is None:
        order_json = max(glob.glob(f"{ROOT}/cache/ch2_giant_reach_beam_*.json") +
                         glob.glob(f"{ROOT}/cache/ch2_giant_coverage_beam_best_*.json"),
                         key=lambda x: len(json.load(open(x)).get("path", [])))
    o = json.load(open(order_json)); order = [int(c) for c in (o["path"] if isinstance(o, dict) else o)]
    missing = [c for c in giant if c not in set(order)]
    missing.sort(key=lambda c: INDEG[c])                          # hardest (lowest in-degree) first
    t0 = time.time()
    times, st = full_retime(order, maxwait)
    print(f"[E-726c] seed {len(order)} cities, makespan {times[-1]:.1f}d strands {st}, missing {len(missing)} "
          f"[{time.time()-t0:.0f}s warmup]", flush=True)
    inserted = 0
    for c in missing:
        best = None                                               # (added_makespan, strands_after, pos)
        cand = [p for p in range(len(order) - 1) if order[p] in INADJ[c] and order[p + 1] in OUTADJ[c]]
        base_mk = times[-1]
        for p in cand:
            w1 = tb.windows(order[p], c, times[p], 1, maxwait)
            if not w1:
                continue
            ac = w1[0][1]
            w2 = tb.windows(c, order[p + 1], ac, 1, maxwait)
            if not w2:
                continue
            # quick local delay proxy: arrival at order[p+1] via c vs original
            delay = w2[0][1] - times[p + 1]
            if best is None or delay < best[0]:
                best = (delay, p, ac)
        if best is None:                                          # no cheap 2-sided slot; append at end
            w = tb.windows(order[-1], c, times[-1], 1, maxwait)
            if w:
                order.append(c); times.append(w[0][1]); inserted += 1
            continue
        delay, p, ac = best
        neworder = order[:p + 1] + [c] + order[p + 1:]
        # full faithful re-time (cheap enough: ~600 legs, edges cached after warmup)
        nt, nst = full_retime(neworder, maxwait)
        order = neworder; times = nt; inserted += 1
        print(f"[E-726c] inserted city {c} (indeg {INDEG[c]}) at pos {p}: now {len(order)} cities, "
              f"makespan {times[-1]:.1f}d strands {nst} [{time.time()-t0:.0f}s]", flush=True)
    times, st = full_retime(order, maxwait)
    threaded = len(order) - st
    print(f"\n[E-726c] DONE: {len(order)} cities, threaded {threaded}, makespan {times[-1]:.1f}d strands {st} "
          f"(d/leg {times[-1]/max(len(order)-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order, "makespan": times[-1], "strands": st},
              open(f"{ROOT}/cache/ch2_giant_faithful_complete_best.json", "w"))
    if threaded >= 600 and times[-1] < 405:
        print(f"[E-726c] *** {threaded}/601 @ {times[-1]:.0f}d < 405 -> RANK-1 giant candidate; "
              f"OFFICIAL verify + stitch + escalate", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else None, int(a[2]) if len(a) > 2 else 25)
