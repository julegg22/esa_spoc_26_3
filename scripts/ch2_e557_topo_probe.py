"""E-557b — Ch2 large STAR-TOPOLOGY probe (fast, structural).

DECISIVE finding from /tmp/ch2_e533_large_adj.npz:
  Inter-component exc edges:
    comp0 <-> comp1/comp2/comp3 : ~8000 each (bridges EXIST)
    comp1 <-> comp2/comp3, etc. : ZERO (smalls mutually disconnected)
  => The component graph is a STAR centered on comp0. comp1/2/3 can ONLY
     be reached through comp0. A linear chain [c0->c1->c2->c3] is
     IMPOSSIBLE (c1->c2 has no edge, not even exc).

  E-556 died because it forced the bridge to leave comp0's GREEDY TAIL
  node (which has ~0 exc edges to smalls) into comp1's first node.
  493/601 comp0 nodes DO have small-comp exc edges; the greedy tail
  happened to be bridge-dead.

Viable topology (min exc bridges): anchor comp0, split into 3 segments,
interleave the 3 small comps, END inside the last small comp:
    comp0_segA -> comp1 -> comp0_segB -> comp2 -> comp0_segC -> comp3[END]
  Bridges: c0->c1, c1->c0, c0->c2, c2->c0, c0->c3  = 5 exc. Budget = 5. OK
  (requires ZERO internal exc in all four components, since 5/5 is used
   by the structural star bridges).

This probe (FAST, matrix-only + a few Lambert checks) establishes:
  1. Can each component be fully covered by a PURE-CHEAP greedy sub-tour
     (max_exc=0)?  [if not, we have no spare exc for internal needs]
  2. For each needed bridge type (c0<->small), confirm a concrete
     feasible (exit,entry,time) exists via Lambert at a realistic time,
     restricting candidates to nodes that HAVE a matrix exc edge.

Run: python scripts/ch2_e557_topo_probe.py 2>&1 | tee runs/ch2_e557_topo_probe.log
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
from esa_spoc_26.ch2_hierarchical_large import greedy_subtour_only
from esa_spoc_26.ch2_kttsp import KTTSP

sys.stdout.reconfigure(line_buffering=True)

ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
ADJ_FILE = "/tmp/ch2_e533_large_adj.npz"


def load_comps():
    d = np.load(ADJ_FILE)
    labels = d['labels']
    ncomp = int(labels.max()) + 1
    comps = [[] for _ in range(ncomp)]
    for i, c in enumerate(labels):
        comps[int(c)].append(int(i))
    comps.sort(key=len, reverse=True)
    return comps, d


def main():
    t_all = time.time()
    kt = KTTSP(INST)
    comps, d = load_comps()
    exc = d['exc']
    node2comp = {}
    for ci, c in enumerate(comps):
        for nd in c:
            node2comp[nd] = ci
    lab2 = np.array([node2comp[i] for i in range(kt.n)])
    print(f"n={kt.n} comps={[len(c) for c in comps]} n_exc={kt.n_exc}",
          flush=True)

    # ── 1. PURE-CHEAP coverage per component (max_exc=0) ──
    print("\n[1] PURE-CHEAP (max_exc=0) coverage per component, best of a "
          "few starts:", flush=True)
    pure_cov = {}
    for ci, comp in enumerate(comps):
        n_starts = 1 if ci == 0 else 4
        best = 0
        best_start = None
        t0 = time.time()
        for s in comp[:n_starts]:
            perm, _t, _dv, ok = greedy_subtour_only(
                kt, comp, s, max_exc=0, t_start=0.0)
            if len(perm) > best:
                best = len(perm)
                best_start = s
        pure_cov[ci] = (best, len(comp), best_start)
        print(f"  comp{ci}: pure-cheap covered {best}/{len(comp)} "
              f"(start={best_start}, {time.time()-t0:.0f}s)", flush=True)

    # ── 2. Concrete bridge feasibility c0<->small at realistic times ──
    # Restrict to nodes that HAVE a matrix exc edge to the target.
    print("\n[2] Concrete Lambert bridge checks (matrix-edge candidates "
          "only), over a time grid:", flush=True)
    c0 = np.where(lab2 == 0)[0]
    smalls = {t: np.where(lab2 == t)[0] for t in (1, 2, 3)}
    t_grid = [10.0, 50.0, 120.0, 250.0, 500.0, 1000.0]

    def first_feasible(src_nodes, dst_nodes, exc_mat, label):
        """Find any feasible exc bridge src->dst over t_grid. exc_mat is
        the boolean adjacency restricting to matrix-edge candidates."""
        t0 = time.time()
        # candidate src = nodes with >=1 exc edge to dst set
        src_has = src_nodes[exc_mat.sum(axis=1) > 0]
        dst_has = dst_nodes[exc_mat.sum(axis=0) > 0]
        # sample to keep Lambert count bounded
        rng = np.random.default_rng(0)
        src_s = rng.choice(src_has, size=min(8, len(src_has)), replace=False)
        dst_s = rng.choice(dst_has, size=min(8, len(dst_has)), replace=False)
        found = None
        n = 0
        for tt in t_grid:
            for s in src_s:
                for dd in dst_s:
                    n += 1
                    tof, dv = find_earliest_transfer(
                        kt, int(s), int(dd), tt, kt.dv_exc, 20.0, 160)
                    if tof is not None:
                        found = (int(s), int(dd), tt, round(tof, 2),
                                 round(dv, 1))
                        break
                if found:
                    break
            if found:
                break
        print(f"  {label}: probed<= {n} Lambert, feasible={found} "
              f"({time.time()-t0:.0f}s)", flush=True)
        return found

    bridges = {}
    for tgt in (1, 2, 3):
        m_out = exc[np.ix_(c0, smalls[tgt])]   # c0 -> small
        bridges[f"c0->c{tgt}"] = first_feasible(c0, smalls[tgt], m_out,
                                                f"c0->c{tgt}")
    for src in (1, 2):  # need small->c0 for the first two (return bridges)
        m_in = exc[np.ix_(smalls[src], c0)]    # small -> c0
        bridges[f"c{src}->c0"] = first_feasible(smalls[src], c0, m_in,
                                                f"c{src}->c0")

    # ── Verdict ──
    print("\n===== TOPOLOGY VERDICT =====", flush=True)
    all_pure = all(pure_cov[ci][0] == pure_cov[ci][1] for ci in range(4))
    print(f"All comps pure-cheap fully covered: {all_pure}", flush=True)
    needed = ["c0->c1", "c1->c0", "c0->c2", "c2->c0", "c0->c3"]
    all_bridges = all(bridges.get(b) is not None for b in needed)
    print(f"All 5 star bridges feasible: {all_bridges}  ({needed})",
          flush=True)
    print(f"Star topology total exc bridges = 5 (= budget {kt.n_exc}). "
          f"Requires 0 internal exc -> pure-cheap coverage MANDATORY.",
          flush=True)
    if all_pure and all_bridges:
        print("=> FIXABLE via STAR topology with exactly 5 exc bridges.",
              flush=True)
    elif all_bridges and not all_pure:
        deficit = sum(pure_cov[ci][1] - pure_cov[ci][0] for ci in range(4))
        print(f"=> Bridges OK but pure-cheap leaves {deficit} nodes "
              f"uncovered; those need internal exc -> exceeds 5 budget "
              f"unless coverage improved with more starts.", flush=True)
    else:
        print("=> Some star bridge infeasible at sampled times; needs "
              "wider time/candidate search.", flush=True)

    Path("/tmp/ch2_e557_topo_summary.json").write_text(json.dumps({
        "pure_cov": {str(k): v for k, v in pure_cov.items()},
        "bridges": bridges, "all_pure": all_pure,
        "all_bridges": all_bridges,
    }, indent=2))
    print(f"\nTotal wall {time.time()-t_all:.0f}s", flush=True)


if __name__ == "__main__":
    main()
