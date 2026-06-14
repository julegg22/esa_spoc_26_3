"""E-592 component-aware TD probe for Ch2 LARGE (cheap go/no-go; read-only).

E-576 proved naive global TD-greedy NN STRANDS on all 24 starts (wastes the
5-exc budget crossing between the 4 cheap-graph components, or paints itself
into a corner). The gap-probe says 0.150d cheap hops are abundant at every
epoch, so the failure is exc-bridge PLANNING, not edge supply.

This probe answers the one question that decides the next build's shape:
does TD-greedy strand only when CROSSING components, or also WITHIN a single
component? Method:
  (1) union-find on the cheap adjacency -> component sizes (confirm the
      comp0(601) + 3x150 topology);
  (2) for comp0 and each small, run a TD-greedy NN RESTRICTED to that
      component's own nodes (candidates masked to the component, NO exc
      budget needed since a component is cheap-connected by definition):
      does it visit all its nodes, and at what intra-component makespan?

If every component completes intra-greedy at low makespan => the constructor
only needs to schedule the 3-5 inter-component exc bridges (tractable) ->
GO build a component-aware TD constructor. If even intra-component greedy
strands => need beam/backtrack within components too -> harder.

Read-only; banks NOTHING. Usage: python ch2_e592_component_td_probe.py
"""
import json
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
ADJ = "/tmp/ch2_e533_large_adj.npz"
WIN, STEPS, WAIT_DT, WAIT_MAX = 4.0, 80, 0.5, 10


def _find(p, i):
    r = i
    while p[r] != r:
        r = p[r]
    while p[i] != r:
        p[i], i = r, p[i]
    return r


def components(cheap, n):
    p = np.arange(n)
    rows, cols = np.where(cheap)
    for a, b in zip(rows, cols):
        ra, rb = _find(p, int(a)), _find(p, int(b))
        if ra != rb:
            p[rb] = ra
    roots = np.array([_find(p, i) for i in range(n)])
    _, comp = np.unique(roots, return_inverse=True)
    return comp


def best_cheap_hop(kt, cands, cur, t, dv_cap):
    bj, bt = None, None
    for j in cands:
        tof, dv = find_earliest_transfer(kt, cur, int(j), t, dv_cap, WIN, STEPS)
        if tof is not None and (bt is None or tof < bt):
            bj, bt = int(j), tof
    return bj, bt


def intra_greedy(kt, neigh, comp_nodes, start):
    """TD-greedy NN restricted to comp_nodes (cheap-only, no exc).
    Returns (order, makespan, stuck_at) — stuck_at=None if complete."""
    cset = set(int(x) for x in comp_nodes)
    visited = {start}
    order = [start]
    cur, t = start, 0.0
    target = len(cset)
    while len(order) < target:
        cands = [j for j in neigh[cur] if j in cset and j not in visited]
        j, tof = best_cheap_hop(kt, cands, cur, t, kt.dv_thr)
        if j is None:
            # wait then retry cheap (no exc inside a component)
            for w in range(1, WAIT_MAX + 1):
                tt = t + w * WAIT_DT
                if tt >= kt.max_time:
                    break
                j, tof = best_cheap_hop(kt, cands, cur, tt, kt.dv_thr)
                if j is not None:
                    t = tt
                    break
        if j is None:
            return order, t, cur  # stranded inside the component
        order.append(j)
        visited.add(j)
        t += tof
        cur = j
    return order, t, None


def main():
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    neigh = [list(np.where(cheap[i])[0]) for i in range(n)]
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]

    comp = components(cheap, n)
    sizes = np.bincount(comp)
    order_by_size = np.argsort(-sizes)
    print(f"[E-592] n={n} cheap-graph components={sizes.size} "
          f"sizes(desc)={sizes[order_by_size][:8].tolist()}", flush=True)
    print(f"[E-592] dv_thr={kt.dv_thr} dv_exc={kt.dv_exc} n_exc={kt.n_exc} "
          f"max_time={kt.max_time}", flush=True)

    # bank's per-component leg count (how the bank partitions the tour)
    bank_comp_of_pos = comp[np.array(perm0)]
    switches = int(np.sum(bank_comp_of_pos[1:] != bank_comp_of_pos[:-1]))
    print(f"[E-592] bank tour crosses components {switches} times "
          f"(=> {switches} inter-component legs)", flush=True)

    # probe intra-component TD-greedy completion for each non-trivial comp
    for ci in order_by_size:
        nodes = np.where(comp == ci)[0]
        if nodes.size < 5:
            continue
        # try 3 starts: bank's first node in this comp + 2 lowest-degree
        deg = np.array([len([x for x in neigh[i] if comp[x] == ci])
                        for i in nodes])
        starts = [int(nodes[np.argmin(deg)])]
        bank_in = [p for p in perm0 if comp[p] == ci]
        if bank_in:
            starts.append(bank_in[0])
        starts.append(int(nodes[np.argmax(deg)]))
        starts = list(dict.fromkeys(starts))[:3]
        for s in starts:
            t0 = time.time()
            order, mk, stuck = intra_greedy(kt, neigh, nodes, s)
            ok = stuck is None
            print(f"  [comp {ci} size={nodes.size}] start={s} "
                  f"{'COMPLETE' if ok else 'STRANDED'} "
                  f"visited={len(order)}/{nodes.size} intra_mk={mk:.2f}d "
                  f"({time.time()-t0:.0f}s)"
                  + ("" if ok else f" stuck_at={stuck}"), flush=True)


if __name__ == "__main__":
    main()
