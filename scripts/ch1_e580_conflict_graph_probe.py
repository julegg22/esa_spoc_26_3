"""E-580 conflict-graph / kernel probe for Ch1 matching (read-only, cheap).

Matching = MWIS on the conflict graph (vertex=transfer, edge=share an
Earth/Moon/dest node, weight=mass). This probe measures whether a GLOBAL
optimizer has tractable structure to exploit:

  (1) connected components of the conflict graph (any isolated component
      is exactly solvable on its own);
  (2) isolated / low-degree vertices (cheap exact reductions: a transfer
      that conflicts with nothing is forced into the optimum);
  (3) bank's selected set vs the reachable forced structure.

No writes, no banking. Usage: python ch1_e580_conflict_graph_probe.py [matching-i|matching-ii|both]
"""
import sys

import numpy as np

from esa_spoc_26.ch1_matching import load_instance

INST = {
    "matching-i": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt",
    "matching-ii": "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-ii.txt",
}


def _find(parent, i):
    root = i
    while parent[root] != root:
        root = parent[root]
    while parent[i] != root:
        parent[i], i = root, parent[i]
    return root


def _union_by_node(parent, node_of_transfer):
    """Union all transfers that share the same node value (one node type)."""
    order = np.argsort(node_of_transfer, kind="stable")
    sorted_nodes = node_of_transfer[order]
    # boundaries between equal-node runs
    change = np.flatnonzero(np.diff(sorted_nodes)) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [len(order)]))
    for s, e in zip(starts, ends):
        if e - s < 2:
            continue
        grp = order[s:e]
        r0 = _find(parent, grp[0])
        for t in grp[1:]:
            rt = _find(parent, t)
            if rt != r0:
                parent[rt] = r0


def probe(problem):
    e, ll, d, w = load_instance(INST[problem])
    n = w.shape[0]
    print(f"\n===== {problem}: {n} transfers (MWIS vertices) =====", flush=True)

    # --- vertex degrees via node-sharing (conflict-graph structure) ---
    # A transfer's conflict-degree is driven by how many OTHER transfers
    # share each of its 3 nodes. count[node] = #transfers using node.
    deg_sum = np.zeros(n, dtype=np.int64)
    n_singleton_node = 0  # nodes used by exactly one transfer (forced-free)
    for arr in (e, ll, d):
        cnt = np.bincount(arr)
        # other transfers sharing each of my nodes (exclude self):
        deg_sum += (cnt[arr] - 1)
        n_singleton_node += int((cnt == 1).sum())
    isolated = int((deg_sum == 0).sum())  # conflicts with nothing => forced IN
    print(f"  conflict-degree: min={deg_sum.min()} median={int(np.median(deg_sum))} "
          f"mean={deg_sum.mean():.1f} max={deg_sum.max()}", flush=True)
    print(f"  ISOLATED vertices (0 conflicts => forced into optimum): {isolated} "
          f"({100*isolated/n:.2f}%)", flush=True)
    print(f"  forced mass from isolated vertices: {w[deg_sum == 0].sum():.3f}", flush=True)
    print(f"  singleton nodes (used by exactly 1 transfer, summed over 3 types): "
          f"{n_singleton_node}", flush=True)

    # --- connected components (union-find over node-sharing) ---
    parent = np.arange(n, dtype=np.int64)
    for arr in (e, ll, d):
        _union_by_node(parent, arr)
    roots = np.array([_find(parent, i) for i in range(n)])
    _, comp_id = np.unique(roots, return_inverse=True)
    sizes = np.bincount(comp_id)
    ncomp = sizes.size
    big = np.sort(sizes)[::-1]
    print(f"  CONNECTED COMPONENTS: {ncomp} "
          f"(largest={big[0]} = {100*big[0]/n:.1f}% of vertices)", flush=True)
    print(f"    top-5 component sizes: {big[:5].tolist()}", flush=True)
    print(f"    singleton components (size 1): {int((sizes == 1).sum())}", flush=True)
    print(f"    components <= 50 vertices (exactly solvable trivially): "
          f"{int((sizes <= 50).sum())} comps / "
          f"{int(sizes[sizes <= 50].sum())} vertices", flush=True)

    # interpretation hook
    if big[0] > 0.5 * n:
        print("  => ONE GIANT COMPONENT: no free decomposition; a global "
              "optimizer must attack the whole graph (KaMIS reductions / "
              "memetic recombination), not piecewise exact.", flush=True)
    else:
        print("  => DECOMPOSES: solve each component exactly & independently "
              "=> provably-global optimum within reach.", flush=True)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "both"
    probs = ["matching-i", "matching-ii"] if arg == "both" else [arg]
    for p in probs:
        probe(p)


if __name__ == "__main__":
    main()
