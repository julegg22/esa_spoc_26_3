---
id: O-011
type: observation
status: confirmed
tags: [ch2, large, hierarchical, scaling, exc-budget]
source: "E-030/E-031 ch2_hierarchical_large.py v1 + v2 on Ch2 large"
created: 2026-05-22
referenced_by: ["[[C-019-hierarchical-orbital-element-decomposition]]"]
---

# O-011 — Ch2 large hierarchical: budget-vs-cluster-count is the binding constraint

## The two-wall finding

Hierarchical orbital-element decomposition (C-019) on Ch2 large
(n=1051, n_exc=5) hits two structural walls:

### Wall 1 — Intra-cluster sub-tour coverage

Phase mismatch at the chosen `t_start` causes greedy cluster
sub-tour to stall partway through cluster members. Even with
phase-rotation (8 time-starts × 4 node-starts in v2) and
`max_exc=1` internal:

| version | k_clusters | fully-covered / k | total covered |
|---|---|---|---|
| v1 (t=0, max_exc=0) | 50 | 11 / 50 (22%) | 150 |
| v2 (8 t × 4 n, max_exc=1) | 50 | 12 / 50 (24%) | 737 (full+partial) |

The phase-rotation gives only +1 fully-covered cluster — the
within-cluster Δv structure is intrinsically tight at most
absolute times.

### Wall 2 — Exception budget vs cluster count

Meta-route at the supernode level: each cluster→cluster bridge
that isn't cheap consumes 1 exception arc from the SAME 5-arc
total budget. For k clusters → k−1 bridges.

v2 meta-route trace:
```
cluster 13 → 19 nodes, n_exc=2, cheap bridge
cluster 35 → +4 nodes, n_exc=3, exc bridge
cluster 37 → +19 nodes, n_exc=4, exc bridge
cluster 8 → +10 nodes, n_exc=4, cheap bridge
cluster 16 → +18 nodes, n_exc=5, cheap bridge (initial cluster had excs?)
walk_fail at cluster 48
```
Budget exhausted after 6 cluster transitions. Reached 84/1051.

## The tradeoff

| k | bridges | feasibility | within-cluster size | sub-tour difficulty |
|---|---|---|---|---|
| 4 | 3 | ALL can be exc | ~260 nodes | very hard |
| 8 | 7 | 5 exc + 2 cheap | ~130 nodes | hard |
| 20 | 19 | 5 exc + 14 cheap | ~50 nodes | moderate |
| 50 | 49 | 5 exc + 44 cheap | ~21 nodes | easy |
| 100 | 99 | 5 exc + 94 cheap | ~10 nodes | trivial |

Small k: bridges all exc-able, but intra-cluster sub-tour is
hard. Large k: intra-cluster easy, but most bridges must be
cheap — requires precise cluster ORDERING.

## Implication for next angle

To bank Ch2 large with our toolchain, need ONE of:
1. **Recursive sub-tour insertion**: treat each big cluster (k=4,
   k=8) as a Ch2-medium-class problem; apply C-017 sub-tour
   bridge insertion WITHIN the cluster. Multi-day build.
2. **Smarter meta-route ordering**: instead of greedy meta-route,
   solve the meta-TSP to minimize total exc usage. Tractable
   (50-node TSP). Could push coverage from 6 to ~10-15 clusters.
3. **Different family entirely**: bi-directional greedy, coarse
   time-discretized MILP via HiGHS, RL pointer network.
4. **Gurobi MILP on canonical Bannach formulation** (user-rejected).

## Practical: meta-route ordering optimization

The cheapest near-term improvement is #2 (smart meta-route). The
meta-graph has ~50 supernodes, ~50 × 50 = 2500 cluster-to-cluster
bridges. Pre-compute the bridge feasibility matrix (cheap vs exc
vs infeasible at typical t_cur). Solve the meta-TSP with the
exception count as a side constraint (≤ 5 exc edges in the tour).
That's a small CP-SAT or TSP-w-constraints problem; solvable in
seconds at meta-scale.

If this works, we'd cover most of the 12 fully-covered clusters
(≈ 250-300 nodes) feasibly. Still ~700 nodes uncovered (the 38
partially-covered clusters), but at least we'd have a partial-
feasibility curve.

## Status

Hierarchical v2 banked: NO feasible 1051-node solution yet. The
14% (v1) and 8% (v2 meta-route) coverage are below leaderboard
threshold. Rank-3 = 2072.84 d but only for FEASIBLE full tours.
Ch2 large remains 0 points.
