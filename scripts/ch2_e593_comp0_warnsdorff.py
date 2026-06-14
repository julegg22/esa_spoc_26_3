"""E-593 comp0 Warnsdorff TD constructor for Ch2 LARGE (cheap probe; read-only).

E-592 decomposed the difficulty: the three 150-node SMALL components are
fully greedy-TD-solvable (~14d each, every start COMPLETES), but the
601-node comp0 STRANDS on every plain-NN start (163/250/188 of 601). So
comp0 is the ENTIRE difficulty; smalls + 5 exc bridges are tractable.

Plain greedy NN strands because it hops to the locally-cheapest node and
leaves low-degree nodes isolated. The classic anti-stranding fix for
greedy Hamiltonian-path construction is the WARNSDORFF rule: among feasible
cheap hops, go to the node with the FEWEST onward unvisited cheap-neighbors
(visit the most-constrained nodes first, keep flexible nodes for last),
tie-broken by tof. Same per-step cost as NN; often completes where NN fails.

This probe: run Warnsdorff-ordered TD-greedy on comp0 from several starts.
Binary question -> does it COMPLETE all 601 (where plain NN stranded)?
If yes + low makespan => GO assemble (comp0-path + greedy smalls + 5 bridges)
next tick. If still strands => need beam/backtrack on comp0.

Read-only; banks NOTHING. Usage: python ch2_e593_comp0_warnsdorff.py [n_starts]
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
import os  # noqa: E402
WIN = float(os.environ.get("E593_WIN", "4.0"))
STEPS = int(os.environ.get("E593_STEPS", "80"))
WAIT_DT = float(os.environ.get("E593_WAITDT", "0.5"))
WAIT_MAX = int(os.environ.get("E593_WAITMAX", "10"))


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


def warnsdorff_greedy(kt, neigh_in, comp_nodes, start):
    """TD-greedy on comp_nodes; among feasible cheap hops pick the target
    with FEWEST onward unvisited cheap-neighbors (Warnsdorff), tie by tof."""
    cset = set(int(x) for x in comp_nodes)
    visited = np.zeros(kt.n, dtype=bool)
    visited[start] = True
    order = [start]
    cur, t = start, 0.0
    target = len(cset)
    while len(order) < target:
        cands = [j for j in neigh_in[cur] if not visited[j]]
        feas = []  # (onward_deg, tof, j)
        for j in cands:
            tof, dv = find_earliest_transfer(kt, cur, int(j), t, kt.dv_thr,
                                             WIN, STEPS)
            if tof is None:
                continue
            onward = sum(1 for k in neigh_in[j] if not visited[k] and k != cur)
            feas.append((onward, tof, int(j)))
        chosen = None
        if feas:
            feas.sort()  # min onward-degree first, then min tof
            chosen = feas[0]
            t_used = t
        else:
            # wait then retry (no exc inside a component)
            for w in range(1, WAIT_MAX + 1):
                tt = t + w * WAIT_DT
                if tt >= kt.max_time:
                    break
                feasw = []
                for j in cands:
                    tof, dv = find_earliest_transfer(kt, cur, int(j), tt,
                                                     kt.dv_thr, WIN, STEPS)
                    if tof is None:
                        continue
                    onward = sum(1 for k in neigh_in[j]
                                 if not visited[k] and k != cur)
                    feasw.append((onward, tof, int(j)))
                if feasw:
                    feasw.sort()
                    chosen = feasw[0]
                    t_used = tt
                    break
        if chosen is None:
            return order, t, cur  # stranded
        onward, tof, j = chosen
        order.append(j)
        visited[j] = True
        t = t_used + tof
        cur = j
    return order, t, None


def main():
    n_starts = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    neigh = [list(np.where(cheap[i])[0]) for i in range(n)]
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]

    comp = components(cheap, n)
    sizes = np.bincount(comp)
    c0 = int(np.argmax(sizes))  # the 601-node giant
    nodes = np.where(comp == c0)[0]
    # comp0-internal neighbor lists (restrict to comp0 for onward-degree)
    neigh_in = {int(i): [j for j in neigh[i] if comp[j] == c0] for i in nodes}
    deg = np.array([len(neigh_in[int(i)]) for i in nodes])
    print(f"[E-593] comp0 size={nodes.size} internal-deg "
          f"min={deg.min()} med={int(np.median(deg))} max={deg.max()}",
          flush=True)

    # starts: bank's first comp0 node + lowest-degree (hardest) + highest-deg
    bank_in = [p for p in perm0 if comp[p] == c0]
    order_lowdeg = nodes[np.argsort(deg)]
    starts = ([bank_in[0]] if bank_in else []) + list(order_lowdeg[:n_starts])
    starts += list(order_lowdeg[::-1][:2])
    seen = set()
    starts = [int(s) for s in starts
              if not (s in seen or seen.add(s))][:n_starts]

    best = None
    for s in starts:
        t0 = time.time()
        order, mk, stuck = warnsdorff_greedy(kt, neigh_in, nodes, s)
        ok = stuck is None
        tag = ""
        if ok and (best is None or mk < best):
            best = mk
            tag = " *** BEST comp0 path"
        print(f"  [start={s}] {'COMPLETE' if ok else 'STRANDED'} "
              f"{len(order)}/{nodes.size} mk={mk:.2f}d "
              f"({time.time()-t0:.0f}s)"
              + ("" if ok else f" stuck_at={stuck}") + tag, flush=True)

    if best is None:
        print("[FINAL] Warnsdorff STILL strands comp0 on all starts "
              "=> need beam/backtrack.", flush=True)
    else:
        print(f"[FINAL] best comp0 Warnsdorff path mk={best:.2f}d over 601 "
              f"nodes ({best/601:.3f} d/leg). GO assemble next tick.",
              flush=True)


if __name__ == "__main__":
    main()
