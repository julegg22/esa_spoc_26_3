"""E-721d — Ch2-large rank-1: LNS on the CORRECT (recovered) graph with the EXACT-ARRIVAL oracle.

The blocker (E-721c): the fast table-lookup retime diverges over long orders (grid-departure+min-tof vs
exact-clock+verified-tof error accumulates -> 253/566 strands on a good order). Fix here: retime with the
FINE oracle `fine_arr` (departs at the exact clock, verifies with compute_transfer) — correct, and fast for
FEASIBLE legs (early-exit on the first cheap tof). To keep LNS iterations cheap, repair uses LOCAL detour
estimates (2 oracle calls per candidate position, NOT a full retime), with one full retime per accepted move.
Runs on the aug table (fine-verify tolerates the resample). Seed = a complete 601 order (e.g. 563-tour + the
38 missing appended); objective = makespan + heavy strand penalty -> drive strands to 0 AND makespan < 405.
Usage: python ch2_giant_lns_fine.py [seed_json] [iters=20000] [destroy_k=12] [T0=6] [tag=a]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp"
kt = KTTSP(INST)
ktf = KTTSP(INST, max_revs=2)                                   # FAST low-rev verify for retime (cheap legs
# in a good order are low-rev/short-tof, so max_revs=2 matches the cheap dv at ~10x speed of max_revs=20)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d_aug.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
HASEDGE = set(PIDX.keys())
OUTADJ = defaultdict(set); INADJ = defaultdict(set)
for (i, j) in KEYS:
    if FIN[PIDX[(int(i), int(j))]].any():
        OUTADJ[int(i)].add(int(j)); INADJ[int(j)].add(int(i))
STRAND_PEN = 50.0
rng = np.random.default_rng(0)


def fine_arr(i, j, t):
    """exact-arrival oracle: earliest cheap arrival for (i,j) departing >= exact clock t, verified."""
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 9)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):  # beam-exact settings
            if ktf.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def retime(order):
    """full fine retime -> (times list, makespan, strands)."""
    t = 0.0; times = [0.0]; strand = 0
    for k in range(len(order) - 1):
        r = fine_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += STRAND_PEN
        else:
            t = r
        times.append(t)
    return times, t, strand


def cost(mk, strand):
    return mk + STRAND_PEN * strand                              # (mk already includes strand penalties; this
    # double-counts intentionally to push strands hardest)


def repair(kept, removed, times):
    """insert each removed city at its min-local-delay feasible position (2 oracle calls/candidate); times
    go stale as we insert (heuristic) — one full retime at the end gives the true makespan."""
    order = list(kept); tms = list(times)
    rem = list(removed); rng.shuffle(rem)
    for c in rem:
        cand = [k for k in range(len(order) - 1) if order[k] in INADJ[c] and order[k + 1] in OUTADJ[c]]
        best = None
        for k in cand:
            ac = fine_arr(order[k], c, tms[k] if k < len(tms) else tms[-1])
            if ac is None:
                continue
            an = fine_arr(c, order[k + 1], ac)
            if an is None:
                continue
            delay = an - (tms[k + 1] if k + 1 < len(tms) else tms[-1])
            if best is None or delay < best[0]:
                best = (delay, k, ac)
        if best is None:                                        # try append (may strand; LNS fixes later)
            ae = fine_arr(order[-1], c, tms[-1])
            order.append(c); tms.append(ae if ae is not None else tms[-1] + STRAND_PEN)
            continue
        _, k, ac = best
        order = order[:k + 1] + [c] + order[k + 1:]
        tms = tms[:k + 1] + [ac] + tms[k + 1:]                   # stale suffix; corrected by final retime
    return order


def destroy(order, times, k, op):
    n = len(order)
    if op == "worst":                                           # remove cities on the longest legs
        legs = sorted(((times[q + 1] - times[q], q) for q in range(n - 1)), reverse=True)
        idx = sorted(set([q for _, q in legs[:k]] + [q + 1 for _, q in legs[:k]]))[:k]
    elif op == "seg":
        s = int(rng.integers(0, n - k)); idx = list(range(s, s + k))
    else:
        idx = rng.choice(n, k, replace=False).tolist()
    rs = set(idx)
    removed = [order[q] for q in idx]
    kept = [order[q] for q in range(n) if q not in rs]
    kept_times = []                                             # recompute kept clock once (cheap fine retime)
    return kept, removed


def main(seed_json, iters=20000, destroy_k=12, T0=6.0, tag="a"):
    global rng
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    order = json.load(open(seed_json))
    if isinstance(order, dict):
        order = order.get("order") or order.get("path")
    order = [int(c) for c in order]
    t0 = time.time()
    times, mk, strand = retime(order)
    cur = cost(mk, strand); best = cur; best_order = list(order); best_strand = strand
    print(f"[LNS-{tag}] seed {len(order)} cities, makespan {mk:.1f}d strands {strand} cost {cur:.0f} "
          f"[{time.time()-t0:.0f}s]", flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_lnsfine_best_{tag}.json"
    ops = ["worst", "scatter", "seg"]; acc = 0
    for it in range(iters):
        T = T0 * (0.9997 ** it) + 0.05
        op = ops[it % 3]
        kept, removed = destroy(order, times, destroy_k, op)
        new = repair(kept, removed, retime(kept)[0])
        ntimes, nmk, nstrand = retime(new)
        nc = cost(nmk, nstrand)
        if nc < cur or rng.random() < np.exp(-(nc - cur) / max(T, 1e-6)):
            order = new; times = ntimes; cur = nc; acc += 1
            if nc < best:
                best = nc; best_order = list(new); best_strand = nstrand
                json.dump({"order": best_order, "makespan": nmk, "strands": nstrand}, open(CKPT, "w"))
                if nstrand == 0 and nmk < 405:
                    print(f"[LNS-{tag}] *** COMPLETE 601 @ {nmk:.1f}d, 0 strands (full <424 RANK-1) it{it} "
                          f"-> verify+stitch+escalate", flush=True)
        if it % 20 == 0:
            print(f"[LNS-{tag}] it{it}: cur_cost {cur:.0f} best_cost {best:.0f} best_strands {best_strand} "
                  f"T={T:.2f} acc={acc} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[LNS-{tag}] DONE: best_cost {best:.0f} strands {best_strand} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else f"{ROOT}/cache/ch2_giant_lns_seed.json",
         int(a[2]) if len(a) > 2 else 20000, int(a[3]) if len(a) > 3 else 12,
         float(a[4]) if len(a) > 4 else 6.0, a[5] if len(a) > 5 else "a")
