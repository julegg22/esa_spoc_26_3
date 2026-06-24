---
date: 2026-06-07
tags: [observation, ch2, large, components, structure, e533]
status: confirmed via E-533 probe (8 (t,tof) samples per pair)
---
# O-015 — Ch2 large structure confirmed: 4 components [601, 150, 150, 150]

## Data

E-533 probed 1051² = 1.1M directed pairs at 8 (t, tof) sample
points each (8.5 M Lambert calls, 30 min on 1 core).

### Densities
- **Cheap arcs (dv ≤ 100 at any probe)**: 139 828 / 1 103 550 = **12.67 %**
  - Notably DENSER than small (5.9 %) — large is more inter-connected
    per-pair, just has more pairs total.
- **Exc-only arcs (100 < dv ≤ 600)**: 109 358 / 1 103 550 = 9.91 %

### Connected components (undirected, cheap-edge)

**4 components, sizes [601, 150, 150, 150]** — exactly matches prior
memory from `scripts/ch2_component_aware.py` analysis.

### Component internal density

| Comp | Size | Max in-degree | Max out-degree | Density |
|---|---|---|---|---|
| 0 (big) | 601 | 163 | 163 | ~27 % reachable per node |
| 1 (small) | 150 | 149 | 149 | **near-complete** |
| 2 (small) | 150 | 149 | 149 | **near-complete** |
| 3 (small) | 150 | 149 | 149 | **near-complete** |

The three small components are essentially complete subgraphs at the
probe resolution. Every node has cheap arcs to nearly every other
node in the same component.

### Bridge candidate nodes (highest-degree in each comp)

| Comp | Top-out nodes (high out-bridge potential) | Top-in nodes (high in-bridge potential) |
|---|---|---|
| 0 (601 nodes) | 11, 1003, 479, 496, 805 | 642, 288, 583, 791, 809 |
| 1 (150 nodes) | 51, 84, 220, 270, 361 | 15, 36, 41, 81, 151 |
| 2 (150 nodes) | 28, 140, 155, 157, 168 | 44, 121, 140, 155, 157 |
| 3 (150 nodes) | 21, 33, 69, 96, 100 | 33, 69, 87, 96, 112 |

These are candidate "boundary" nodes for inter-component exception
bridges — i.e., the natural endpoint nodes when stitching the cluster
TSPs together.

## Implications

### For replicating TGMA's algorithm on large

The near-complete small components make exact TSPs (Concorde / LKH-3)
trivial: 150-node TSP on a dense graph is solvable in minutes. The
601-node big comp is harder but within LKH-3's typical scale.

**Algorithmic pipeline for cluster-decomposition** (the TGMA-likely
approach):
1. Build cheap-only adjacency per component (intra-comp arcs).
2. For each small comp: solve open TSP path with fixed entry/exit
   nodes (3-9 candidate endpoints from degree analysis above).
3. For comp 0: solve open TSP path with fixed entry/exit on the 601-
   node sparser subgraph.
4. Optimize inter-comp bridge choice across the K-1 = 3 transitions
   (constrained by remaining exception budget of 5).
5. Concatenate, walk chronologically, optimize (times, tofs) with DP
   on a coarse table for the leg cost.

Estimated effort: ~1 week dev + ~1 day compute.

### For our current focus

Large is NOT the immediate priority — medium re-attack is in
progress (E-531), and small still has runway (need −5.5 d for R3,
−14.7 d for R1 against external 101.65). When small/medium are
fed, the structural recipe for large is now documented and ready.

## Memory pointer

The [601, 150, 150, 150] structure is now a confirmed fact at the
probe resolution. Save as part of competitor inference. Reference
this when discussing large strategy or attempting cluster-aware
decomposition.

## Companion docs
- [[O-014-2026-06-07-competitor-algorithm-inference]] — why TGMA's
  algorithm is likely cluster-aware
- [[C-012-earliest-feasible-tof]] — our existing methodology
- [[M-general-foundation-then-search]] — the meta-principle
