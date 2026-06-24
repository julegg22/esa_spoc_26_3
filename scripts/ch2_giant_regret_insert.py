"""E-720 lever — Ch2-large rank-1: time-aware REGRET-insertion constructor (non-forward).

Audit (E-720): forward beam caps 566/601 by frontier exhaustion (strands the last ~35, which ARE richly
reachable). A from-scratch INSERTION construction is the opposite paradigm: it can place a hard city EARLY
(when its window is open) instead of deferring it. Regret-k insertion = insert the city with the largest
(2nd-best - best) insertion cost first (the one that loses most by waiting) — so high-inclination low-degree
cities get scheduled early, not stranded late. Faithful table retime (faithful clock); fine-tof verify the
result. Target giant makespan < ~405d (=> full < 424.62).

Usage: python ch2_giant_regret_insert.py [regret_k=2] [shortlist=40] [tag=a]"""
import sys, json, time
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
HASEDGE = set(PIDX.keys())
OUTADJ = defaultdict(set); INADJ = defaultdict(set)
for (i, j) in KEYS:
    OUTADJ[int(i)].add(int(j)); INADJ[int(j)].add(int(i))
INDEG = {c: len(INADJ[c]) for c in cities}
_RF = {}


def rowfin(row):
    fe = _RF.get(row)
    if fe is None:
        fe = np.where(FIN[row])[0]; _RF[row] = fe
    return fe


def table_arr(i, j, t):
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


def retime(order):
    """faithful table retime -> (arrival_times list, makespan, strands)."""
    t = 0.0; ts = [0.0]; strand = 0
    for k in range(len(order) - 1):
        r = table_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += 6.0
        else:
            t = r
        ts.append(t)
    return ts, t, strand


def best_insertions(c, order, times, shortlist):
    """return sorted list of (delta_makespan, pos) for inserting c; local 2-leg detour estimate."""
    res = []
    # positions where pred->c is a cheap edge (so c can be reached); cap by shortlist
    cand = [k for k in range(len(order) - 1)
            if order[k] in INADJ[c] and order[k + 1] in OUTADJ[c]]
    if not cand:
        cand = [k for k in range(len(order) - 1) if order[k] in INADJ[c]]
    for k in cand[:shortlist]:
        a, b = order[k], order[k + 1]
        t_a = times[k]
        arr_c = table_arr(a, c, t_a)
        if arr_c is None:
            continue
        arr_b_new = table_arr(c, b, arr_c)
        if arr_b_new is None:
            continue
        delta = arr_b_new - times[k + 1]                          # local delay introduced at b
        res.append((max(delta, 0.0), k))
    # also allow append at the end
    if order[-1] in INADJ[c]:
        arr_c = table_arr(order[-1], c, times[-1])
        if arr_c is not None:
            res.append((arr_c - times[-1], len(order) - 1))
    res.sort()
    return res


def main(regret_k=2, shortlist=40, tag="a"):
    rng = np.random.default_rng(abs(hash(tag)) % (2**31))
    # seed: start from a hard (lowest-degree) city + its cheapest reachable neighbor
    hard_sorted = sorted(cities, key=lambda c: INDEG[c])
    s0 = hard_sorted[0]
    nb = min((j for j in OUTADJ[s0]), key=lambda j: INDEG[j], default=None)
    order = [s0, nb] if nb is not None else [s0]
    placed = set(order)
    unplaced = [c for c in cities if c not in placed]
    print(f"[REGRET-{tag}] regret-{regret_k} insertion, shortlist={shortlist}; seed {order}; "
          f"{len(unplaced)} to place", flush=True)
    t0 = time.time()
    while unplaced:
        times, mk, _ = retime(order)
        best_city = None; best_choice = None; best_regret = -1
        # evaluate a sample of unplaced (hard ones first for regret) to bound cost
        cohort = sorted(unplaced, key=lambda c: INDEG[c])[:120] if len(unplaced) > 120 else unplaced
        for c in cohort:
            ins = best_insertions(c, order, times, shortlist)
            if not ins:
                continue
            best_cost = ins[0][0]
            second = ins[regret_k - 1][0] if len(ins) >= regret_k else ins[-1][0] + 50.0
            regret = second - best_cost
            # prioritize: high regret, tie-break low insertion cost
            score = regret - 0.01 * best_cost
            if best_city is None or score > best_regret:
                best_regret = score; best_city = c; best_choice = ins[0]
        if best_city is None:
            # no cohort city insertable -> try ALL unplaced once
            for c in unplaced:
                ins = best_insertions(c, order, times, shortlist)
                if ins:
                    best_city = c; best_choice = ins[0]; break
            if best_city is None:
                print(f"[REGRET-{tag}] STUCK: {len(unplaced)} cities have no feasible insertion at "
                      f"makespan {mk:.1f}d (placed {len(order)}/601) [{time.time()-t0:.0f}s]", flush=True)
                break
        pos = best_choice[1]
        order = order[:pos + 1] + [best_city] + order[pos + 1:]
        placed.add(best_city); unplaced.remove(best_city)
        if len(order) % 50 == 0:
            _, mk2, st = retime(order)
            print(f"  placed {len(order)}/601, makespan {mk2:.1f}d (d/leg {mk2/max(len(order)-1,1):.3f}), "
                  f"strands {st} [{time.time()-t0:.0f}s]", flush=True)
    _, mk, st = retime(order)
    print(f"\n[REGRET-{tag}] DONE: placed {len(order)}/601, makespan {mk:.1f}d (d/leg {mk/600:.3f}), "
          f"strands {st}; rank-1 giant<405 [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": order, "makespan": mk, "strands": st, "placed": len(order)},
              open(f"{ROOT}/cache/ch2_giant_regret_{tag}.json", "w"))
    if len(order) >= 599 and st <= 5 and mk < 405:
        print(f"[REGRET-{tag}] *** complete giant @ {mk:.0f}d -> stitch + udp verify + escalate.", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 2, int(a[2]) if len(a) > 2 else 40, a[3] if len(a) > 3 else "a")
