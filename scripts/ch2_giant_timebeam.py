"""E-723 — Ch2-large rank-1: FIXED-ORDER time-beam (the frame fix from the 2026-06-26 audit).

Audit finding: our greedy retimer commits to the EARLIEST cheap departure window at every leg; earliest-arrival
can land at a phase from which the next leg has no cheap window -> strands (the bank's own giant order strands
111 under greedy, though it is officially valid). The bank uses only 29.6d total wait, so the gap is NOT heavy
waiting — it is that we never CONSIDER a slightly-later departure window that re-phases the chain.

Fix: for a FIXED order, a time-beam that branches over the next K cheap departure windows per leg (not just
earliest) and keeps the W earliest-arrival partial schedules. This is the joint (times,tofs) search for a given
order, on the FULL 0-950 graph (the bank needs it: 334/601 giant visits are >460d). Greedy = K=1; the fix is
K>1. Decisive test: retime the bank giant order — does window-branching thread it (0 strands) at <=932d?
Then minimize makespan (the beam keeps earliest) and wrap in order perturbation toward rank-1 (<425d).
Usage: python ch2_giant_timebeam.py [order_json=bank] [K=4] [W=250] [maxwait_epochs=25]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
import ch2_fast_transfer as ft
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST); ktf = KTTSP(INST, max_revs=2)
_OPAR = kt.opar.astype(__import__("numpy").float64); _MR = kt.max_revs; _DAY = 86400.0
def CT(i, j, dep, tof):
    return ft.transfer_dv(_OPAR[i], _OPAR[j], dep * _DAY, tof * _DAY, _MR)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d.npz"))   # FULL 0-950 horizon
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}


_FINE = {}                                                       # per-edge fine cheap-window cache (dep, tof)


def fine_scan_edge(i, j):
    """one-time FINE (0.1d epoch) scan of edge i->j over the full horizon, to recover marginal-dv / narrow-epoch
    windows the 1d table misses (the bank uses these: ~2% of its legs). Cached. tof seeded from the table's
    known cheap tofs for this edge (or a broad range if the edge is absent)."""
    key = (i, j)
    if key in _FINE:
        return _FINE[key]
    tlo, thi, tstep = kt.min_tof, 8.0, 0.03                 # FULL tof range (bank uses up to 6.7d; med±0.8 was
    #                                                        long-tof-BLIND -> stranded valid long-tof legs)
    wins = []
    eps = np.arange(0.0, float(EPOCHS[-1]), 0.2)
    tgrid = np.arange(tlo, thi, tstep)
    for dep in eps:
        for tof in tgrid:
            if CT(i, j, float(dep), float(tof)) <= kt.dv_thr:
                wins.append((float(dep), float(tof))); break    # one window per epoch
    _FINE[key] = wins
    return wins


def windows(i, j, t, K, maxwait):
    """up to K feasible (departure, arrival) options at distinct cheap epochs >= t (branch over phases).
    Falls back to a cached fine-epoch scan when the 1d table yields nothing within the wait budget."""
    row = PIDX.get((i, j))
    out = []
    if row is not None:
        e0 = np.searchsorted(EPOCHS, t)
        for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + maxwait)):
            if not FIN[row, e]:
                continue
            dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
            if CT(i, j, dep, h) > 2.5 * kt.dv_thr:
                continue
            for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
                if CT(i, j, dep, float(tof)) <= kt.dv_thr:
                    out.append((dep, dep + float(tof))); break
            if len(out) >= K:
                break
    if not out:                                                 # table gap -> fine-scan fallback (cached)
        for (dep, tof) in fine_scan_edge(i, j):
            if dep >= t - 1e-9 and dep <= t + maxwait:
                out.append((dep, dep + tof))
                if len(out) >= K:
                    break
    return out


def timebeam(order, K, W, maxwait, verbose=True, tolerate=False, SP=50.0):
    """fixed-order forward time-beam; returns (makespan, strands, reached_depth). With tolerate=True, a leg with
    no feasible window adds a penalty (SP) to every state and continues (so order-search gets a full objective
    from any seed); strands counts such legs. tolerate=False stops at the first strand (clean validation)."""
    arrivals = [0.0]
    strands = 0
    t0 = time.time()
    for p in range(len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for t in arrivals:
            for (dep, arr) in windows(i, j, t, K, maxwait):
                nxt.append(arr)
        if not nxt:
            if not tolerate:
                if verbose:
                    print(f"  STRAND at leg {p} ({i}->{j}); reached depth {p+1}/{len(order)} "
                          f"[{time.time()-t0:.0f}s]", flush=True)
                return None, len(order) - 1 - p, p + 1
            arrivals = [t + SP for t in arrivals]; strands += 1   # penalize and carry the clock forward
            continue
        nxt = sorted(set(round(x, 4) for x in nxt))[:W]      # keep W earliest (Pareto: smaller arr dominates)
        arrivals = nxt
        if verbose and (p % 50 == 0 or p == len(order) - 2):
            print(f"  leg {p+1}/{len(order)-1}: |states|={len(arrivals)} min_arr={arrivals[0]:.1f}d "
                  f"(d/leg {arrivals[0]/(p+1):.3f}) strands={strands} [{time.time()-t0:.0f}s]", flush=True)
    return arrivals[0], strands, len(order)


def main(order_json="bank", K=4, W=250, maxwait=25):
    if order_json == "bank":
        order = json.load(open(f"{ROOT}/cache/ch2_bank_giant_order.json"))
    else:
        obj = json.load(open(order_json)); order = obj["path"] if isinstance(obj, dict) else obj
    order = [int(c) for c in order]
    print(f"[E-723] FIXED-ORDER time-beam: order len {len(order)}, K={K} W={W} maxwait={maxwait}d, "
          f"full graph 0-{EPOCHS[-1]:.0f}d. Greedy strands this order at 111; bank makespan=932.5", flush=True)
    mk, st, depth = timebeam(order, K, W, maxwait)
    if st == 0:
        print(f"\n[E-723] *** THREADED full order: makespan {mk:.1f}d, 0 strands (bank giant=~913d). "
              f"K>1 window-branching RECOVERS what greedy strands -> frame fix WORKS.", flush=True)
        json.dump({"order": order, "makespan": mk, "strands": 0},
                  open(f"{ROOT}/cache/ch2_giant_timebeam_best.json", "w"))
        if mk < 425:
            print(f"[E-723] makespan {mk:.0f}d < 425 -> RANK-1 on this order!", flush=True)
    else:
        print(f"\n[E-723] order strands ({st}) even with K={K} window-branching at depth {depth}; "
              f"the ORDER (not just timing) blocks it -> need order search with this time-beam evaluator.",
              flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else "bank", int(a[2]) if len(a) > 2 else 4,
         int(a[3]) if len(a) > 3 else 250, int(a[4]) if len(a) > 4 else 25)
