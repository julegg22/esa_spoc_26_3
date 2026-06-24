"""P1 (audit) — Ch2-large: decompose the makespan gap into ORDER vs TIMING.

For a FIXED city order, greedy earliest-arrival retiming is only makespan-optimal under the FIFO property
(arriving earlier never hurts). Orbital transfer windows are time-dependent and may be NON-FIFO (a later
departure can arrive earlier via a different rev / window), so greedy may leave makespan on the table.
This compares: (a) greedy earliest-arrival retime vs (b) a multi-arrival timing beam (keep the K best
arrival times per city, explore several departure epochs per leg) — the optimal-timing-for-fixed-order test.

If (b) << (a): TIMING is a lever (joint NLP / DP retiming worth building).
If (b) ~ (a): timing is already near-optimal -> the gap is ORDER quality -> re-ordering (LNS) is mandatory.
Run on both the bank's 601 giant order (1.52 d/leg) and the beam's 566 order (0.527 d/leg).
Usage: python ch2_giant_p1_retime.py [order_json] [K=6]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = KTTSP("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp")
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}


def leg_arrivals(i, j, t, n_opt=4):
    """up to n_opt feasible cheap arrivals for (i,j) departing >= t, at distinct epochs (NON-FIFO aware)."""
    row = PIDX.get((i, j))
    if row is None:
        return []
    out = []
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 40)):       # wider epoch window for later-but-shorter
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                out.append(dep + float(tof)); break
        if len(out) >= n_opt:
            break
    return out


def greedy_retime(order):
    t = 0.0; strand = 0
    for k in range(len(order) - 1):
        a = leg_arrivals(order[k], order[k + 1], t, n_opt=1)
        if not a:
            strand += 1; t += 9.0
        else:
            t = a[0]
    return t, strand


def beam_retime(order, K=6):
    """timing beam on a FIXED order: keep the K earliest arrival times reachable at each city."""
    arr = [0.0]; strand = 0
    for k in range(len(order) - 1):
        nxt = []
        for t in arr:
            nxt.extend(leg_arrivals(order[k], order[k + 1], t, n_opt=4))
        if not nxt:
            strand += 1; arr = [a + 9.0 for a in arr][:K]            # penalty, carry forward
        else:
            arr = sorted(set(round(a, 4) for a in nxt))[:K]          # K earliest distinct arrivals
    return min(arr), strand


def main(order_json, K=6):
    order = json.load(open(order_json))
    if isinstance(order, dict):
        order = order.get("path") or order.get("order")
    print(f"[P1] {order_json}: {len(order)} cities", flush=True)
    t0 = time.time()
    g, gs = greedy_retime(order)
    print(f"[P1] greedy earliest-arrival: makespan {g:.1f}d (d/leg {g/max(len(order)-1,1):.3f}), strands {gs} "
          f"[{time.time()-t0:.0f}s]", flush=True)
    b, bs = beam_retime(order, K)
    print(f"[P1] multi-arrival timing beam (K={K}): makespan {b:.1f}d (d/leg {b/max(len(order)-1,1):.3f}), "
          f"strands {bs} [{time.time()-t0:.0f}s]", flush=True)
    gain = g - b
    print(f"[P1] TIMING gain: {gain:.1f}d ({100*gain/max(g,1):.1f}%). "
          f"{'>>0 => TIMING is a lever (build DP/NLP retime)' if gain > 0.05*g else '~0 => timing near-optimal; gap is ORDER => LNS re-ordering'}", flush=True)


if __name__ == "__main__":
    oj = sys.argv[1] if len(sys.argv) > 1 else f"{ROOT}/cache/ch2_bank_giant_order.json"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    main(oj, K)
