"""E-594 beam-search TD constructor for Ch2 LARGE comp0 (the prize bottleneck).

Established this session (E-576/592/593): the three 150-node smalls are
greedy-TD-solvable (~14d each), but the 601-node comp0 STRANDS under every
greedy flavor (plain NN, Warnsdorff, wide-window) — a time-dependent
phasing wall around ~190-270 nodes that single-path greedy cannot cross.
comp0 needs a constructor that keeps MULTIPLE partial paths alive.

Beam search: keep B partial paths; each step expand every path by its top-K
cheapest feasible cheap hops; score a path by realized makespan + a
stranding penalty (count of unvisited nodes that currently have 0 feasible
onward cheap hops from anywhere reachable -> approximated by unvisited
low-onward-degree count); keep the best B, REQUIRING distinct current nodes
for diversity (so beams don't collapse to near-copies and all hit the same
wall). Dead-path prune: if a path can't extend, drop it.

Validation target: does beam COMPLETE all of `comp_size` where greedy
stranded, and at what makespan? Smoke on a small comp (known completable)
first via SMOKE=1. Read-only; banks NOTHING.

Usage: python ch2_e594_comp0_beam.py [beam_B] [topK]   (env SMOKE=1 for small)
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ = "/tmp/ch2_e533_large_adj.npz"
WIN = float(os.environ.get("E594_WIN", "8.0"))
STEPS = int(os.environ.get("E594_STEPS", "120"))
SMOKE = os.environ.get("SMOKE", "0") == "1"


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


class Path:
    __slots__ = ("order", "visited", "cur", "t", "mk")

    def __init__(self, order, visited, cur, t):
        self.order = order
        self.visited = visited
        self.cur = cur
        self.t = t
        self.mk = t


WARN = os.environ.get("E594_WARN", "1") == "1"


def top_hops(kt, neigh_in, path, cset, topK):
    """Return up to topK (tof, j) feasible hops from path.cur. With Warnsdorff
    (WARN=1), rank by (onward unvisited-degree, tof) so constrained low-degree
    nodes are visited EARLY (they are what strands the tail); else by tof."""
    feas = []
    for j in neigh_in[path.cur]:
        if path.visited[j]:
            continue
        tof, dv = find_earliest_transfer(kt, path.cur, int(j), path.t,
                                         kt.dv_thr, WIN, STEPS)
        if tof is None:
            continue
        if WARN:
            onward = sum(1 for k in neigh_in[j]
                         if not path.visited[k] and k != path.cur)
            feas.append((onward, tof, int(j)))
        else:
            feas.append((0, tof, int(j)))
    feas.sort()
    return [(tof, j) for _onw, tof, j in feas[:topK]]


PEN = float(os.environ.get("E594_PEN", "0.0"))   # stranding-penalty weight
LOWDEG = int(os.environ.get("E594_LOWDEG", "20"))  # "scarce" static degree
DIV = os.environ.get("E594_DIV", "0") == "1"     # diversity-blend beam halves


def beam_build(kt, neigh_in, nodes, start, B, topK, deadline):
    cset = set(int(x) for x in nodes)
    target = len(cset)
    # scarce low-static-degree nodes are what greedy/beam orphans last; a soft
    # score penalty for leaving them UNvisited pulls them earlier without the
    # makespan blow-up of forcing low-degree hops in generation (WARN regressed).
    lowdeg = [int(i) for i in nodes if len(neigh_in[int(i)]) <= LOWDEG]
    lowdeg_arr = np.array(lowdeg, dtype=int) if lowdeg else None
    v0 = np.zeros(kt.n, dtype=bool)
    v0[start] = True
    beam = [Path([start], v0, start, 0.0)]
    best_complete = None
    while beam:
        if time.time() > deadline:
            break
        # all complete?
        for p in beam:
            if len(p.order) == target:
                if best_complete is None or p.mk < best_complete.mk:
                    best_complete = p
        if best_complete is not None:
            break
        children = []
        for p in beam:
            hops = top_hops(kt, neigh_in, p, cset, topK)
            for tof, j in hops:
                nv = p.visited.copy()
                nv[j] = True
                children.append(Path(p.order + [j], nv, j, p.t + tof))
        if not children:
            break
        # onward-degree stranding penalty: scarce low-degree nodes left
        # unvisited inflate score -> beams that consume them early survive.
        if PEN > 0.0 and lowdeg_arr is not None:
            def score(c):
                n_strand = int((~c.visited[lowdeg_arr]).sum())
                return c.mk + PEN * n_strand
        else:
            def score(c):
                return c.mk
        children.sort(key=score)
        # keep best B with DISTINCT current nodes (diversity vs collapse)
        beam = []
        seen_cur = set()
        if DIV and lowdeg_arr is not None:
            # DIVERSITY-BLEND: half the slots go to pure-makespan core-threaders,
            # half to lineages that have visited the MOST scarce nodes (so a
            # scarce-conscious branch survives alongside fast greedy WITHOUT
            # forcing every beam to chase scarce nodes -> corner-paints, killed
            # WARN/PEN). This keeps both failure-avoiding lineages alive.
            half = max(1, B // 2)
            for c in children:  # makespan half
                if c.cur in seen_cur:
                    continue
                seen_cur.add(c.cur)
                beam.append(c)
                if len(beam) >= half:
                    break
            rest = sorted(children, key=lambda c: (
                -int(c.visited[lowdeg_arr].sum()), c.mk))
            for c in rest:  # scarce-visiting half
                if c.cur in seen_cur:
                    continue
                seen_cur.add(c.cur)
                beam.append(c)
                if len(beam) >= B:
                    break
        else:
            for c in children:
                if c.cur in seen_cur:
                    continue
                seen_cur.add(c.cur)
                beam.append(c)
                if len(beam) >= B:
                    break
        if not beam:  # all collided -> fall back to plain top-B
            beam = children[:B]
    # final sweep
    for p in beam:
        if len(p.order) == target and (best_complete is None
                                       or p.mk < best_complete.mk):
            best_complete = p
    if best_complete is not None:
        return best_complete.order, best_complete.mk, None
    # report deepest partial
    deepest = max(beam, key=lambda p: len(p.order)) if beam else None
    if deepest is None:
        return [start], 0.0, start
    return deepest.order, deepest.mk, deepest.cur


def main():
    B = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    topK = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    kt = KTTSP(INST)
    n = kt.n
    cheap = np.load(ADJ)["cheap"]
    neigh = [list(np.where(cheap[i])[0]) for i in range(n)]
    comp = components(cheap, n)
    sizes = np.bincount(comp)
    if SMOKE:
        target_comp = int(np.argmin(np.where(sizes >= 5, sizes, 10**9)))
        budget = int(os.environ.get("E594_BUDGET", "300"))
    else:
        target_comp = int(np.argmax(sizes))  # comp0=601
        budget = int(os.environ.get("E594_BUDGET", "1200"))
    nodes = np.where(comp == target_comp)[0]
    neigh_in = {int(i): [j for j in neigh[i] if comp[j] == target_comp]
                for i in nodes}
    deg = np.array([len(neigh_in[int(i)]) for i in nodes])
    print(f"[E-594] comp={target_comp} size={nodes.size} B={B} topK={topK} "
          f"WIN={WIN} STEPS={STEPS} budget={budget}s "
          f"deg(min/med/max)={deg.min()}/{int(np.median(deg))}/{deg.max()}",
          flush=True)

    order_lowdeg = nodes[np.argsort(deg)]
    starts = list(order_lowdeg[:3]) + [int(nodes[np.argmax(deg)])]
    seen = set()
    starts = [int(s) for s in starts
              if not (s in seen or seen.add(s))]
    if SMOKE:
        starts = starts[:1]  # full budget to one start to validate completion
    else:
        starts = starts[:int(os.environ.get("E594_NSTARTS", "2"))]
    best = None
    deepest = None  # (order, mk) of the deepest partial across all starts
    cset_all = set(int(x) for x in nodes)
    for s in starts:
        t0 = time.time()
        order, mk, stuck = beam_build(kt, neigh_in, nodes, s, B, topK,
                                      time.time() + budget / len(starts))
        ok = stuck is None
        tag = ""
        if ok and (best is None or mk < best[1]):
            best = (order, mk)
            tag = " *** BEST"
        if deepest is None or len(order) > len(deepest[0]):
            deepest = (order, mk)
        print(f"  [start={s}] {'COMPLETE' if ok else 'partial'} "
              f"{len(order)}/{nodes.size} mk={mk:.2f}d "
              f"({mk/max(1,len(order)-1):.3f} d/leg) "
              f"({time.time()-t0:.0f}s){tag}", flush=True)

    # Always dump the deepest partial + leftover nodes for insertion-repair,
    # regardless of whether any start COMPLETED (repair material survives strand).
    if deepest is not None:
        dorder, dmk = deepest
        leftover = sorted(cset_all - set(int(x) for x in dorder))
        json.dump({"comp": target_comp,
                   "order": [int(x) for x in dorder], "mk": dmk,
                   "leftover": [int(x) for x in leftover],
                   "target": int(nodes.size)},
                  open(f"/tmp/ch2_e594_comp{target_comp}_partial_B{B}"
                       f"{'_div' if DIV else ''}.json", "w"))
        print(f"[PARTIAL] deepest={len(dorder)}/{nodes.size} mk={dmk:.2f}d "
              f"leftover={len(leftover)} -> "
              f"/tmp/ch2_e594_comp{target_comp}_partial_B{B}"
              f"{'_div' if DIV else ''}.json", flush=True)

    if best is None:
        print("[FINAL] beam did NOT complete the component => need "
              "backtracking / LKH-intra or larger beam.", flush=True)
    else:
        order, mk = best
        json.dump({"comp": target_comp, "order": [int(x) for x in order],
                   "mk": mk}, open(f"/tmp/ch2_e594_comp{target_comp}.json", "w"))
        print(f"[FINAL] beam COMPLETED comp{target_comp}: "
              f"{len(order)} nodes mk={mk:.2f}d ({mk/(len(order)-1):.3f} d/leg)"
              f" -> /tmp/ch2_e594_comp{target_comp}.json. GO assemble.",
              flush=True)


if __name__ == "__main__":
    main()
