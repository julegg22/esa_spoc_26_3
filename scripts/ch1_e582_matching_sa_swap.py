"""E-582 matching SA transfer-swap — inter-BASIN search for Ch1 3-D matching.

CONJECTURE (user, 2026-06-14): the matching leaderboard is NOT one basin
being polished but MANY near-equivalent configurations; top teams reach a
BETTER basin via global inter-configuration search, not basin-escape on a
single basin. Evidence (this session): (a) SCIP dual bound 34118 > our
33338 > top-team 33555 ⇒ top solution is REACHABLE in our faithful model
(E-039); (b) leaderboard shows dozens of DISTINCT near-top solutions per
team (0.2% spread) = plateau fingerprint; (c) near-uniform weights +
near-perfect matching + perfect regularity (matching-i: every node in
exactly 5 transfers) = vast plateau of near-equal basins; (d) full Gurobi
B&B is LICENSE-BLOCKED (25k vars >> 2k cap) so we can't out-solve; our
edge must be smarter SEARCH. Every prior method is single-basin: exact
repair is mass-deterministic (rebuilds bank, 0 worsening), greedy/GRASP
samples WORSE basins. NOTHING we ran moves LATERALLY between good configs.

This engine fills that gap: SA over single transfer-SWAP moves (eject the
<=3 selected transfers conflicting with an unselected one, add it), with
METROPOLIS acceptance of WORSENING moves + a TABU list on freshly-ejected
transfers. That is a TRUE configuration-space walk that can drift DOWN and
OUT of the bank basin — the one thing exact-repair LNS structurally cannot
do. Periodic ejection_improve re-tightens (greedy-fills freed nodes) to
realize plateau gains and track the best. Starts FROM the bank.

Discriminating question: does worsening-tolerant swap search climb PAST
the bank (33338 / 72206)? If yes => multi-basin crossing CONFIRMED + we
have the engine for Levers 2-3 (large structured destroy, path-relinking).

Read-only on the bank: writes best to /tmp ONLY; banks NOTHING (a separate
guarded step handles banking iff strictly better + feasible + round-trip).

Usage: python ch1_e582_matching_sa_swap.py <matching-i|matching-ii> \
        [time_s] [seed] [T0] [cool] [tabuK]
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch1_matching import (  # noqa: E402
    load_instance, _owner_maps, ejection_improve,
)

INST = {
    "matching-i": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato "
                  "Logistics/matching-i.txt",
    "matching-ii": f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato "
                   "Logistics/matching-ii.txt",
}
BANK = {p: f"{ROOT}/solutions/upload/{p}.json" for p in INST}


def load_bank_x(problem, n):
    d = json.load(open(BANK[problem]))
    vec = d[0]["decisionVector"] if isinstance(d, list) else d["decisionVector"]
    x = np.asarray(vec, dtype=np.int8)
    assert x.size == n, f"bank len {x.size} != |T| {n}"
    return x


def main():
    problem = sys.argv[1] if len(sys.argv) > 1 else "matching-i"
    time_s = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    T0 = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
    cool = float(sys.argv[5]) if len(sys.argv) > 5 else 0.9999
    tabuK = int(sys.argv[6]) if len(sys.argv) > 6 else 200
    fill_every = int(os.environ.get("E582_FILL_EVERY", "20000"))
    Tmin = float(os.environ.get("E582_TMIN", "0.05"))
    reheat_after = int(os.environ.get("E582_REHEAT", "400000"))

    e, ll, d, w = load_instance(INST[problem])
    n = w.shape[0]
    ne, nl, nd = int(e.max()) + 1, int(ll.max()) + 1, int(d.max()) + 1
    order = np.argsort(-w, kind="stable")
    rng = np.random.default_rng(seed)

    # node -> transfers adjacency (per type) for ADJACENCY-GUIDED swaps:
    # propose i that CONFLICTS with a selected j (shares a node) so |delta|
    # is small (near-lateral) -> SA actually traverses the plateau. Uniform
    # random i gave ~0% acceptance (ejects 3 good for 1 mediocre).
    adj_e = [None] * ne
    adj_l = [None] * nl
    adj_d = [None] * nd
    for arr, adj in ((e, adj_e), (ll, adj_l), (d, adj_d)):
        o = np.argsort(arr, kind="stable")
        keys = arr[o]
        bounds = np.searchsorted(keys, np.arange(len(adj) + 1))
        for nd_i in range(len(adj)):
            adj[nd_i] = o[bounds[nd_i]:bounds[nd_i + 1]]
    adj_by_type = (adj_e, adj_l, adj_d)
    node_of = (e, ll, d)

    x = load_bank_x(problem, n).copy()
    se, sl, sd = _owner_maps(e, ll, d, x, ne, nl, nd)
    bank_mass = float(w[x == 1].sum())
    # tighten start (no-op if already maximal)
    cur_mass = ejection_improve(e, ll, d, w, x, order, se, sl, sd)
    best = x.copy()
    best_mass = cur_mass
    print(f"[E-582] {problem} |T|={n} nodes={ne}/{nl}/{nd} bank={bank_mass:.3f} "
          f"start(tightened)={cur_mass:.3f} T0={T0} cool={cool} tabuK={tabuK} "
          f"fill_every={fill_every} seed={seed}", flush=True)

    last_eject = np.full(n, -10 ** 9, dtype=np.int64)  # tabu clock per transfer
    T = T0
    t0 = time.time()
    it = 0
    acc = 0
    acc_worse = 0
    since_best = 0
    while time.time() - t0 < time_s:
        it += 1
        T = max(Tmin, T * cool)
        # periodic tighten/track at TOP so early `continue`s don't bypass it
        if it % fill_every == 0:
            xt = x.copy()
            se2, sl2, sd2 = _owner_maps(e, ll, d, xt, ne, nl, nd)
            m = ejection_improve(e, ll, d, w, xt, order, se2, sl2, sd2)
            tag = ""
            if m > best_mass + 1e-9:
                best, best_mass = xt.copy(), m
                since_best = 0
                tag = " *** NEW BEST"
                if m > bank_mass + 1e-9:
                    tag += f" (BEATS BANK +{m - bank_mass:.3f})"
                    json.dump({"problem": problem, "mass": m,
                               "sel": [int(v) for v in np.flatnonzero(xt)]},
                              open(f"/tmp/ch1_e582_{problem}_best.json", "w"))
            else:
                since_best += fill_every
            print(f"  it={it} t={time.time()-t0:.0f}s T={T:.3f} "
                  f"cur~{cur_mass:.1f} tightened={m:.3f} best={best_mass:.3f} "
                  f"acc={acc} worse={acc_worse}{tag}", flush=True)
            if since_best >= reheat_after:
                T = T0
                since_best = 0
                x = best.copy()
                se, sl, sd = _owner_maps(e, ll, d, x, ne, nl, nd)
                cur_mass = best_mass
                print(f"  [reheat] T<-{T0} resume best={best_mass:.3f}",
                      flush=True)
        # ADJACENCY-GUIDED proposal: pick a selected transfer j (O(1) rejection
        # sampling), one of its nodes, then an unselected transfer i sharing
        # that node => i conflicts with j (small |delta|, near-lateral).
        j0 = int(rng.integers(n))
        if not x[j0]:
            continue
        typ = int(rng.integers(3))
        nodeid = int(node_of[typ][j0])
        cands = adj_by_type[typ][nodeid]
        i = int(cands[rng.integers(cands.size)])
        if x[i]:
            continue
        ei, li, di = e[i], ll[i], d[i]
        cset = {se[ei], sl[li], sd[di]}
        cset.discard(-1)
        # tabu: don't immediately re-add a freshly ejected transfer
        if any(it - last_eject[j] < tabuK for j in cset):
            continue
        # EJECTION-CHAIN move: add i, eject its conflicts, then GREEDY-REFILL
        # the nodes freed by the ejection (so each move lands on another
        # near-maximal config). From a tight optimum a single swap is always
        # downhill; the refill is what creates near-LATERAL plateau moves.
        removed = list(cset)
        for j in removed:
            x[j] = 0
            se[e[j]] = sl[ll[j]] = sd[d[j]] = -1
        x[i] = 1
        se[ei] = sl[li] = sd[di] = i
        # freed nodes = ejected transfers' nodes not now owned by i
        freed = []
        for j in removed:
            if se[e[j]] == -1:
                freed.append((0, int(e[j])))
            if sl[ll[j]] == -1:
                freed.append((1, int(ll[j])))
            if sd[d[j]] == -1:
                freed.append((2, int(d[j])))
        added = [i]
        for tp, nodek in freed:
            best_fill, best_w = -1, 0.0
            for cidx in adj_by_type[tp][nodek]:
                ci = int(cidx)
                if x[ci]:
                    continue
                if se[e[ci]] == -1 and sl[ll[ci]] == -1 and sd[d[ci]] == -1:
                    if w[ci] > best_w:
                        best_w, best_fill = w[ci], ci
            if best_fill >= 0:
                x[best_fill] = 1
                se[e[best_fill]] = sl[ll[best_fill]] = sd[d[best_fill]] = best_fill
                added.append(best_fill)
        net = float(w[added].sum() - w[removed].sum()) if removed else float(
            w[added].sum())
        if net >= 0 or rng.random() < np.exp(net / T):
            for j in removed:
                last_eject[j] = it
            cur_mass += net
            acc += 1
            if net < 0:
                acc_worse += 1
        else:  # reject -> undo (restore removed, drop added)
            for a in added:
                x[a] = 0
                se[e[a]] = sl[ll[a]] = sd[d[a]] = -1
            for j in removed:
                x[j] = 1
                se[e[j]] = sl[ll[j]] = sd[d[j]] = j

    print(f"[FINAL] {problem} best={best_mass:.3f} bank={bank_mass:.3f} "
          f"delta={best_mass - bank_mass:+.3f} iters={it} acc={acc} "
          f"worse={acc_worse} "
          + (f"=> BEATS BANK, candidate at /tmp/ch1_e582_{problem}_best.json"
             if best_mass > bank_mass + 1e-9 else "=> no improvement"),
          flush=True)


if __name__ == "__main__":
    main()
