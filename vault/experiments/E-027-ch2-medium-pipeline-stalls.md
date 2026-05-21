---
id: E-027
type: experiment
status: done
tags: [ch2, medium, scaling, find-transfer, cluster-insertion]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-21
ran_start: 2026-05-21
ran_end: 2026-05-21
duration_runtime: "~5.5h (181-start greedy + multi-cluster insertion)"
code: src/esa_spoc_26/ch2_findtransfer_greedy.py + ch2_multi_cluster_insert.py
commit: (with this E)
inputs: "medium.kttsp (n=181, max_time=500d)"
outputs: no banked tour (best partial 158/180 + 2-node insert = 161/181)
env: spoc26
code_dependencies: [src/esa_spoc_26/ch2_findtransfer_greedy.py, src/esa_spoc_26/ch2_multi_cluster_insert.py]
compute: {cpu_seconds: 19500, peak_memory_mb: 1200, cores: 4}
effort_person_hours: 1.0
metrics:
  greedy_181_starts_wall_s: 17435  # 4.84h
  greedy_n_full_tours: 0
  greedy_best_partial_legs: 158_of_180  # start=26
  greedy_top10_legs: [158, 158, 157, 157, 157, 157, 157, 157, 153, 153]
  best_partial_missing_nodes: [0, 21, 33, 40, 42, 60, 62, 91, 92, 93, 95, 97, 99, 112, 119, 126, 136, 141, 146, 160, 161, 179]
  multi_cluster_clusters: [20, 2]  # 20-node "big" cluster + 2-node pair
  inserted_pair_62_91_mk: 235.72
  greedy_fill_node_0_21_33: NO_feasible_insertion
verdict: refutes (current pipeline scaling)
---

# E-027 — Medium pipeline stalls: greedy partial + multi-cluster insert insufficient

## Result

Extended the `find_transfer + cluster-insertion` pipeline (proven on
small, E-022) to medium (n=181, max_time=500d). Two-step run:

1. **Parallel greedy from all 181 starts (4.84 h wall, 4 cores)**:
   - 0 full tours
   - Best partial: **158 of 180 legs** from start=26 (22 missing)
   - Top-10 partials all 153–158 legs

2. **Multi-cluster insertion on best partial**:
   - Missing 22 nodes decomposed into 1 big cluster (20 nodes) + 1
     pair (62, 91)
   - 20-node cluster: skipped (k! intractable for k=20)
   - Pair (62, 91) inserted at mk=235.72d (8 min wall)
   - Greedy-fill on remaining 20: **0 feasible insertions** across
     the first 3 attempted (0, 21, 33); pattern indicates the
     161-node perm is already chronologically saturated

## Why it doesn't scale

The pipeline relies on:
- Greedy reaches >90% completion (small: 45/48 = 94 %; medium:
  158/180 = 88 %). ✓
- Missing nodes form a small contiguous cluster (small: 3-node
  cluster). ✗ (medium: 20-node + 2-node = scattered)

For medium, the missing set is structurally different:
- 1 large physical cluster (20 cheap-arc-connected nodes,
  probably analogous to small's big cluster's "neglected" subset)
- 1 isolated pair
- Some isolated singletons (likely have NO cheap arcs to the
  visited nodes at current chronological state)

The multi-cluster insertion approach doesn't directly help — the
20-node cluster is too large to insertion-enumerate (20! = 2.4e18),
and after a 158-leg partial fills most of the 500d horizon, no
chronological slack remains for additional nodes.

## What this implies

Medium is a structurally harder instance than small. Likely needs:

1. **Cluster-FIRST greedy**: start at a small-cluster node, visit
   the entire small cluster early via cheap internal arcs, then
   bridge to big cluster. (Tested on small E-024 cluster_first —
   refuted because small-cluster traversal stalled greedy at 24-27
   legs. For medium, the small cluster might be too big for greedy
   from-cluster too.)
2. **Multi-stage decomposition**: solve cluster sub-tours
   independently, then concatenate via exception bridges.
3. **A proper MILP with Gurobi**: per O-009 Bannach paper,
   |A|=20, |T|=41 in 1540s with Gurobi. Medium at n=181 with
   coarse |T|=10 might be Gurobi-feasible (we'd need licence).

## Position vs goal (Ch2 banked tally)

- **Small: 142.99 d** ✓ (banked, E-022 + 2-opt polish)
- **Medium: no banked** ✗
- **Large: not attempted**

Medium tasks remain on the frontier per task #21. The current
find_transfer pipeline IS suitable for small but does NOT scale
without substantial architectural addition (cluster-first or
proper MILP).
