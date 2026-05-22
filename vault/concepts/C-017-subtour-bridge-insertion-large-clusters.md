---
id: C-017
type: concept
status: confirmed
tags: [optimization, ch2, lns, clustering, pattern, scale]
scope: optimization/routing + algorithm/local-search
confidence: high
created: 2026-05-21
sources:
  - "[[E-031-ch2-medium-first-feasible]]"
  - "[[C-013-cluster-bridge-insertion-pattern]]"
related: ["[[C-013-cluster-bridge-insertion-pattern]]", "[[C-018-reserved-budget-construction]]", "[[C-012-earliest-feasible-tof]]"]
---

# C-017 — Sub-tour bridge insertion (extends C-013 for k > 5)

*Primer: when the missing cluster is too big to enumerate orderings,
build a feasible sub-tour through it first, then graft it into the
partial perm via two bridge arcs.*

## Why a new concept

C-013 (cluster-bridge insertion) enumerates `k!` orderings of the
missing cluster — feasible up to k ≈ 5. For Ch2 medium (n=181)
the missing cluster has **k=20** → 20! ≈ 2.4×10¹⁸ orderings. Pure
enumeration is impossible.

## The pattern

Given partial perm `π = [v_0, ..., v_{L-1}]` and a missing cluster
`C = {c_1, ..., c_k}` with k > 5:

1. **Build a sub-tour through C only.** Use a small TSP solver
   restricted to cluster nodes (greedy from each as start; pick
   shortest feasible). Each cluster node tried as start; the
   greedy uses cheap intra-cluster arcs (typically all internal
   transfers are cheap since cluster members are co-orbital, per
   `[[O-007-ch2-small-structure-characterized]]`). Cluster
   internally consumes ≤ 1 exception arc.
2. **Bridge-prefilter** (see C-020): for each insertion position p,
   check the in-bridge `partial[p-1] → subtour[0]` at the visit
   time of partial[p-1]. Skip if infeasible. Run the full
   chronological walk only for positions that pass.
3. **Try both directions**: forward and reverse subtour orderings.
   Bridge feasibility varies with direction.
4. **Pick best feasible**: lowest makespan + within total n_exc
   budget.

## Why it works

The sub-tour assumption: cluster members ARE co-orbital (low Δv
within), so a feasible sub-tour exists. The bridges into/out of
the cluster are the expensive part — they typically need exception
arcs. Budget = 2 excs per cluster (in + out).

For multiple big clusters, iterate: insert cluster 1, then re-walk
partial; insert cluster 2 into the larger partial; etc.

## Multiple-cluster total budget

If a partial perm uses some exceptions (e.g., 1 used during the
base greedy), the budget for cluster bridges = n_exc − base_used.
For each cluster: 2 excs. So **max cluster insertions = floor((n_exc
− base_used) / 2)**. To enable more cluster insertions, REDUCE the
base greedy's exception usage (see C-018 reserved-budget construction).

## When to use vs C-013

| | C-013 | C-017 |
|---|---|---|
| missing k | ≤ 5 | > 5 |
| evaluation cost | k! orderings × L positions | k_starts × L positions |
| typical wall | minutes | minutes-hours |
| internal exc budget | 0 | 0–1 |

## In practice

`src/esa_spoc_26/ch2_subtour_insert_fast.py` implements both the
sub-tour build (`find_all_subtours`) and the bridge-prefilter
insertion (`fast_insert_subtour`). The medium pipeline iterates
over big clusters, then falls back to C-013-style insertion for
small (k ≤ 5) clusters. Banked Ch2 medium **274.74 d → 274.52 d
(per-leg + joint NLP polish)** in ~75 min wall.

## References

- E-031 (Ch2 medium first feasible).
- C-013 (small-k cluster-bridge insertion).
- C-018 (reserved-budget construction).
- C-020 (bridge-prefilter).
