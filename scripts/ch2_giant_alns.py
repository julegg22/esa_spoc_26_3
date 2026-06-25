"""E-721g — Ch2-large rank-1: a PROPER continuous-time ALNS (the real TD-TSP method).

GTSP is out (continuous time can't be node-discretized, E-718). Crude LNS/SA capped ~577. This is the proper
metaheuristic: Shaw/related removal + worst + strand-targeted; REGRET-2 insertion (place the city that loses
most by waiting, prioritizing the hard cities); record-to-record acceptance; adaptive operator weights. Fine
(compute_transfer) makespan so the cascade is scored faithfully. Seed = best near-complete tour. The rigorous
test: if a PROPER ALNS still caps ~577, the wall is fundamental to local search; if it breaks, that's rank-1.
Usage: python ch2_giant_alns.py [seed_json] [iters=30000] [tag=a]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp"
kt = KTTSP(INST); ktf = KTTSP(INST, max_revs=2)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d_aug.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
INADJ = defaultdict(set); OUTADJ = defaultdict(set)
for (i, j) in KEYS:
    if FIN[PIDX[(int(i), int(j))]].any():
        INADJ[int(j)].add(int(i)); OUTADJ[int(i)].add(int(j))
opar = np.array(kt.opar)
SP = 50.0
rng = np.random.default_rng(0)


def fine_arr(i, j, t):
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 9)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if ktf.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def retime(order):
    t = 0.0; strand = 0; times = [0.0]
    for k in range(len(order) - 1):
        r = fine_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += SP
        else:
            t = r
        times.append(t)
    return times, t, strand


def cost(order):
    _, mk, st = retime(order)
    return mk + SP * st, mk, st


# ---- destroy operators ----
def d_random(order, times, k):
    idx = rng.choice(len(order), k, replace=False)
    return idx


def d_worst(order, times, k):
    legs = sorted(range(len(order) - 1), key=lambda q: -(times[q + 1] - times[q]))
    s = set()
    for q in legs:
        s.add(q + 1)
        if len(s) >= k:
            break
    return np.array(list(s))


def d_strand(order, times, k):
    sc = [q + 1 for q in range(len(order) - 1) if times[q + 1] - times[q] > 40.0]
    if len(sc) < k:
        sc = list(set(sc + rng.choice(len(order), k, replace=False).tolist()))
    return np.array(sc[:k])


def d_shaw(order, times, k):                                    # related: orbit-similar to a random seed city
    s = int(rng.integers(0, len(order))); c0 = order[s]
    o0 = opar[c0]
    dist = [(np.abs(opar[order[q]][2] - o0[2]) + abs(times[q] - times[s]) * 0.01, q) for q in range(len(order))]
    dist.sort()
    return np.array([q for _, q in dist[:k]])


DESTROYS = [d_random, d_worst, d_strand, d_shaw]


def regret_repair(kept, removed, k_regret=2):
    """regret-k insertion: each round, place the removed city with the largest (k-th best - best) insertion
    cost at its best feasible position; re-time incrementally. Prioritizes hard cities."""
    order = list(kept); tms, _, _ = retime(order)
    rem = list(removed)
    while rem:
        best_city = None; best_choice = None; best_regret = -1e18
        for c in rem:
            cand = [q for q in range(len(order) - 1) if order[q] in INADJ[c] and order[q + 1] in OUTADJ[c]]
            costs = []
            for q in cand[:25]:
                ac = fine_arr(order[q], c, tms[q])
                if ac is None:
                    continue
                an = fine_arr(c, order[q + 1], ac)
                if an is None:
                    continue
                costs.append((an - tms[q + 1], q, ac))
            if not costs:
                costs = [(SP, len(order) - 1, tms[-1] + SP)]                 # forced append (strand)
            costs.sort()
            kth = costs[min(k_regret - 1, len(costs) - 1)][0]
            regret = kth - costs[0][0]
            if regret > best_regret:
                best_regret = regret; best_city = c; best_choice = costs[0]
        _, q, ac = best_choice
        order = order[:q + 1] + [best_city] + order[q + 1:]
        tms = tms[:q + 1] + [ac]; t = ac
        for w in range(q + 1, len(order) - 1):
            r = fine_arr(order[w], order[w + 1], t)
            t = r if r is not None else t + SP
            tms.append(t)
        rem.remove(best_city)
    return order


def main(seed_json, iters=30000, tag="a"):
    global rng
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    order = json.load(open(seed_json))
    if isinstance(order, dict):
        order = order.get("order") or order.get("path")
    order = [int(c) for c in order]
    t0 = time.time()
    cur, mk, st = cost(order)
    best = cur; best_order = list(order); best_mk = mk; best_st = st
    print(f"[ALNS-{tag}] seed {len(order)} cities makespan {mk:.1f}d strands {st}; iters={iters}", flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_alns_best_{tag}.json"
    w = np.ones(len(DESTROYS)); sc = np.zeros(len(DESTROYS)); cnt = np.zeros(len(DESTROYS)); acc = 0
    for it in range(iters):
        times, _, st_cur = retime(order)
        k = int(rng.integers(8, 26))
        di = int(rng.choice(len(DESTROYS), p=w / w.sum()))
        idx = set(int(x) for x in DESTROYS[di](order, times, k))
        removed = [order[q] for q in idx]; kept = [order[q] for q in range(len(order)) if q not in idx]
        new = regret_repair(kept, removed)
        nc, nmk, nst = cost(new)
        cnt[di] += 1
        if nc < cur or nc < best * 1.02:                        # record-to-record acceptance (2% band)
            order = new; cur = nc; acc += 1; sc[di] += 1
            if nc < best:
                best = nc; best_order = list(new); best_mk = nmk; best_st = nst; sc[di] += 3
                json.dump({"order": best_order, "makespan": best_mk, "strands": best_st}, open(CKPT, "w"))
                if best_st == 0 and best_mk < 405:
                    print(f"[ALNS-{tag}] *** 601 @ {best_mk:.1f}d 0 strands (full<424 RANK-1) it{it}", flush=True)
        if it % 25 == 0 and it > 0:                             # adapt operator weights
            for x in range(len(DESTROYS)):
                if cnt[x] > 0:
                    w[x] = 0.7 * w[x] + 0.3 * max(0.1, sc[x] / cnt[x])
            sc[:] = 0; cnt[:] = 0
            print(f"[ALNS-{tag}] it{it}: cur {cur:.0f} best_mk {best_mk:.1f}d best_strands {best_st} "
                  f"acc={acc} w={np.round(w/w.sum(),2)} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[ALNS-{tag}] DONE best_mk {best_mk:.1f}d strands {best_st} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else f"{ROOT}/cache/ch2_giant_tdsa_best_D.json",
         int(a[2]) if len(a) > 2 else 30000, a[3] if len(a) > 3 else "a")
