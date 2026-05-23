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

## Update — multi-start meta-route experiment (2026-05-22 PM)

After v2 single-start reached 84 nodes, I tried meta-route from
EACH of 50 clusters as start (`ch2_hierarchical_multistart.py`).
Result: **best 210 / 1051 nodes** (vs v2's 84 — a 2.5× improvement
from cluster-ordering optimization alone).

Across 50 starts, the meta-route distribution:
- Most starts stalled at 3-7 clusters / 40-100 nodes
- A handful of "lucky" starts chained 11-13 clusters / 190-210 nodes
- None reached > 13 clusters before stalling on either budget
  exhaustion or walk failure

**Confirmation of the hard ceiling**: ~210 nodes is the asymptotic
reach of hierarchical with k=50 + 5-exc budget, regardless of
start node. The mathematical bound: with 5 exc bridges admissible,
the meta-route can visit at most ~6 exception-bridged clusters
PLUS the chain of cheap-bridge-connected ones reachable from any
exception entry point. In our cluster graph, "cheap-chains" have
length ~7-8 (per 2-clusters joined by exception arc, ~3 cheap chain
per side).

## 2026-05-23 ultrathink — cheap-arc-graph + OR-tools deep dive

User ultrathink-prompted a fresh exploration. Perspectives:

### P1: Cheap-arc graph (built in 121s + 860s for dense)
- Sparse (k_nn=80, 4×4 grid): 25,493 cheap edges, mean degree 24.3
- Dense (k_nn=200, 6×6 grid): **59,539 cheap edges, mean degree 56.6,
  ZERO isolated nodes**
- **4 strongly-connected components**: sizes [601, 150, 150, 150]
- **ZERO cross-bridges between any pair of small components** at
  dv_exc=600 (verified at 30×30 grid + tof up to 300d; src=902 to
  ALL 150 in comp 1: best dv=2666.4 m/s, 4× exception cap)

### P2: NN-greedy on dense cheap-arc graph
- 50 starts × NN: best **584/1051 nodes** (vs hierarchical 210)
- Plateau at ~580 because budget exhausts before all 4 comps reachable

### P3: Component-aware via OR-tools
- OR-tools 3600s on comp 2 (601 nodes): Hamilton path with **1 INF
  arc** (min achievable)
- OR-tools 600s on small comps 0/1/3: Hamilton **cycles** with 0
  INF arcs

### The math of feasibility
- Arrangement: `[small_a, seg1, small_b, seg2, small_c]`
- 5 elements, 4 inter-comp transitions × 1 exc each = 4 excs
- + 1 internal INF arc in comp 2 = 5 excs total = EXACTLY budget ✓
- **Forced assignment** by bridge topology:
  - small_a=comp 1 (only comp 1 bridges INTO comp2_path[0]=582)
  - small_c=comp 0 (only comp 0 bridges FROM comp2_path[-1]=205)
  - small_b=comp 3 (remaining)

### Why we can't bank yet
- 179/600 cut positions admit valid (entry, exit) cycle-predecessor
  pairs for small_b=comp 3
- 13,000+ candidate assemblies (179 cuts × 75 cycle endpoint
  combinations) but **walk_perm_chrono fails chronologically** for
  ALL: the bridge `(td_pref, tof_pref)` prescribed in the bridge
  table doesn't align with the cumulative time during the
  sequential walk
- Walking with `find_earliest_transfer` greedy at t_ready misses
  the narrow bridge feasibility windows

### What's actually missing
- A **joint NLP optimization** over all 1051 (td, tof) variables
  (similar to small/medium polish but at scale). With 2100 vars
  and ~3000 constraints, scipy SLSQP would take hours.
- OR: an iterative time-aware walker that progressively
  reschedules bridges via constraint satisfaction.
- OR: switching to the canonical Bannach time-expanded MILP with
  Gurobi (rejected).

### Status

Ch2 large structurally cracked open (4-comp topology + forced
assignment identified), but banking the perm requires building the
joint timing optimizer. Pending future session.

## Implication: hierarchical alone CANNOT bank Ch2 large.

Need a fundamentally different machinery:
- **Gurobi MILP on Bannach time-expanded ILP** (user-rejected)
- **Two-level recursive decomposition** with sub-tour insertion
  WITHIN each big cluster (multi-day build, may yield ~600-900
  nodes)
- **RL pointer network** trained on the structure (multi-day)
- **A solver from a competitor team** (out of scope)

Ch2 large remains 0 points for our toolchain. The 210-node hard
ceiling is a confirmed reproducible finding.

## Update — Perspective 1+2 cheap-arc-graph exploration (2026-05-23 AM)

Per user ultrathink prompt for orthogonal angles:

### Sparse cheap-arc graph (k_nn=80, 4×4 grid, 121s build)
- 25,493 cheap edges, mean degree 24.3
- NN-greedy on this graph: **530/1051 nodes** (vs 84 hierarchical)
- 5/5 excs used; plateau at ~530

### Dense cheap-arc graph (k_nn=200, 6×6 grid, 860s build)
- 59,539 cheap edges, mean degree 56.6, **0 isolated nodes**
- NN-greedy: **584/1051 nodes** (slight improvement)

### Component analysis (CRITICAL FINDING)
- The dense cheap-arc graph has exactly **4 strongly-connected
  components**: sizes [601, 150, 150, 150]
- ZERO inter-component cheap arcs (mathematically separable)
- With 5 exc budget: only 3 needed for inter-component bridges
  → 2 spare for intra-component recovery
- The 4-component structure matches the orbital architecture

### Intra-component Hamilton path is hard
- Component 2 (601 nodes, dense): NN-greedy + 200 randomized
  restarts + 20k backtrack budget → best 558/601 (93%)
- Each small component (150 nodes): 128/150–143/150 (85–95%)
- NN-style heuristics ALONE cannot find full Hamilton paths in
  these dense directed graphs (mean degree 91 for 601-node
  component, n/2 = 300, Ghouila-Houri threshold not met)

### What's still needed
- **OR-tools / LKH-3 gold-standard TSP solver** on each
  component's intra-graph. With 56.6 avg degree, almost
  certainly admits a Hamilton path — just needs a stronger
  algorithm than NN+backtrack.
- Once intra-Hamiltons found, the 3-exc-bridge inter-component
  stitching should produce a feasible 1051-node tour.

### Best partial reached: 584/1051 (~56% coverage)
Status: substantially better than hierarchical's 210 but still
no feasible bank.
