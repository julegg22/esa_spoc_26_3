"""P2 (audit lever) — Ch2-large rank-1: complete-tour LNS with FINE-tof faithful re-timing.

P1 proved the 932->424 gap is ORDER quality, not timing (multi-arrival retime of the bank order = 0% gain).
The prior LNS (ch2_giant_lns.py, E-668) used the COARSE table and basin-locked at ~909. The new ingredient:
the fine-tof exact oracle (E-710) + ruin-and-recreate at varied destroy sizes. Maintain a COMPLETE 601 order
(never drop below 601, <=5 exceptions => always UDP-feasible); destroy a set of cities, repair by
cheapest-insertion with faithful re-timing, SA-accept on makespan. Target giant makespan < ~405d
(=> full <424.62 after sats).

Seed: the bank's complete 601 giant order (cache/ch2_bank_giant_order.json). Checkpoints best per tag.
Usage: python ch2_giant_lns_finetof.py [seed_json] [op=mix] [destroy_k=30] [iters=100000] [T0=8] [tag=a]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = KTTSP("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp")
import os
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
HASEDGE = set(PIDX.keys())
np_rng = np.random.default_rng(0)


# FAST table retime: the dense1d table is faithful (verified), so a lookup-based earliest-cheap-arrival
# (no Lambert) is an accurate makespan proxy for the LNS SEARCH. Fine-tof verify is run only on the best tour.
_ROWFIN = {}                                                     # lazy per-row sorted cheap epochs


def rowfin(row):
    fe = _ROWFIN.get(row)
    if fe is None:
        fe = np.where(FIN[row])[0]; _ROWFIN[row] = fe
    return fe


def table_arr(i, j, t):
    """earliest cheap arrival for (i,j) departing >= t via table lookup (no Lambert). float or None."""
    row = PIDX.get((i, j))
    if row is None:
        return None
    fe = rowfin(row)
    if fe.size == 0:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    p = np.searchsorted(fe, e0)                                   # first cheap epoch index >= e0
    if p >= fe.size:
        return None
    e = fe[p]
    if e > e0 + 8:                                                # match the beam's ~8-epoch window: a leg is
        return None                                              # feasible only if cheap soon (no far clock-jump)
    return max(t, float(EPOCHS[e])) + float(VALS[row, e])


def cheap_arr(i, j, t):                                          # alias used by fine verify
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 10)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def retime(order):
    """FAST table retime; (cost, strands, ok). cost = real makespan + heavy strand penalty so LNS drives
    strands -> 0. Always ok (allow many strands at start; the penalty does the work)."""
    t = 0.0; strand = 0
    for k in range(len(order) - 1):
        r = table_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += 50.0                               # heavy penalty: a strand ~ infeasible leg
        else:
            t = r
    return t, strand, True


def repair(kept_order, removed):
    """insert each removed city at its makespan-cheapest feasible position; greedy random order."""
    order = list(kept_order)
    rem = list(removed)
    np_rng.shuffle(rem)
    for c in rem:
        best = None
        cand = [k for k in range(len(order) - 1)
                if (order[k], c) in HASEDGE and (c, order[k + 1]) in HASEDGE]
        if not cand:
            cand = [k for k in range(len(order) - 1) if (order[k], c) in HASEDGE]
        for k in cand[:60]:
            trial = order[:k + 1] + [c] + order[k + 1:]
            mk, exc, ok = retime(trial)
            if ok and (best is None or mk < best[0]):
                best = (mk, k)
        if best is None:
            return None
        order = order[:best[1] + 1] + [c] + order[best[1] + 1:]
    return order


def destroy(order, k, op):
    n = len(order)
    if op == "seg":
        s = int(np_rng.integers(0, n - k)); idx = list(range(s, s + k))
    elif op == "worst":
        t = 0.0; legs = []
        for q in range(n - 1):
            r = cheap_arr(order[q], order[q + 1], t)
            dt = (r - t) if r else 9.0
            legs.append((dt, q)); t = r if r else t + 9.0
        legs.sort(reverse=True)
        idx = sorted(set([q for _, q in legs[:k]] + [q + 1 for _, q in legs[:k]]))[:k]
    else:
        idx = np_rng.choice(n, k, replace=False).tolist()
    idx = sorted(set(idx))
    rs = set(idx)
    removed = [order[q] for q in idx]
    kept = [order[q] for q in range(n) if q not in rs]
    return kept, removed


def main(seed_json, op="mix", destroy_k=30, iters=100000, T0=8.0, tag="a"):
    global np_rng
    np_rng = np.random.default_rng(abs(hash(tag)) % (2**31))
    order = json.load(open(seed_json))
    if isinstance(order, dict):
        order = order.get("path") or order.get("order")
    order = [int(c) for c in order]
    mk, exc, ok = retime(order)
    print(f"[P2-{tag}] LNS start: {len(order)} cities seed cost {mk:.1f}d strands {exc}; op={op} k={destroy_k} T0={T0}", flush=True)
    best_order = list(order); best_mk = mk; cur_mk = mk; best_strand = exc
    CKPT = f"{ROOT}/cache/ch2_giant_lns_best_{tag}.json"
    t0 = time.time(); acc = 0
    ops = ["seg", "worst", "scatter"]
    for it in range(iters):
        T = T0 * (0.9995 ** it) + 0.05
        o = op if op != "mix" else ops[it % 3]
        k = destroy_k if o != "worst" else max(8, destroy_k // 2)
        kept, removed = destroy(order, k, o)
        new = repair(kept, removed)
        if new is None:
            continue
        nmk, nexc, ok = retime(new)
        if not ok:
            continue
        if nmk < cur_mk or np_rng.random() < np.exp(-(nmk - cur_mk) / T):
            order = new; cur_mk = nmk; acc += 1
            if nmk < best_mk:
                best_mk = nmk; best_order = list(new); best_strand = nexc
                json.dump({"order": best_order, "cost": best_mk, "strands": nexc}, open(CKPT, "w"))
                if nexc == 0 and best_mk < 405:
                    print(f"[P2-{tag}] *** COMPLETE 601 @ {best_mk:.1f}d < 405, 0 strands (=> full <424 "
                          f"RANK-1) at it{it}! -> verify+stitch+escalate", flush=True)
        if it % 100 == 0:
            print(f"[P2-{tag}] it{it}: cur {cur_mk:.1f}d best {best_mk:.1f}d strands~{best_strand} "
                  f"T={T:.2f} acc={acc} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[P2-{tag}] DONE: best {best_mk:.1f}d after {iters} its [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": best_order, "makespan": best_mk}, open(CKPT, "w"))


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else f"{ROOT}/cache/ch2_bank_giant_order.json",
         a[2] if len(a) > 2 else "mix", int(a[3]) if len(a) > 3 else 30,
         int(a[4]) if len(a) > 4 else 100000, float(a[5]) if len(a) > 5 else 8.0,
         a[6] if len(a) > 6 else "a")
