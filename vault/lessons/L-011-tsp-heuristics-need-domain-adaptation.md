---
id: L-011
type: lesson
status: confirmed
tags: [optimization, tsp, lns, ils, gotcha, domain-knowledge]
kind: gotcha
scope: optimization/local-search + tsp
severity: warning
confidence: high
created: 2026-05-21
source: "ILS double-bridge: ALL 6 kicks infeasible on Ch2 small banked perm"
related: ["[[C-011-metaheuristic-local-search-routing]]", "[[O-007-ch2-small-structure-characterized]]"]
effort_person_hours: 0.5
---

# L-011 — Standard TSP heuristics need domain-specific adaptation

## The failure

To break out of the Ch2 small 142.92 d basin, I implemented Iterated
Local Search with the canonical **double-bridge kick** (Lin-Kernighan
inspired): cut the perm at 4 random points, swap the middle two
segments. This is the standard TSP technique for escaping 2-opt
local optima.

Result: **6/6 kicks infeasible.** The greedy big-cluster segments
[3-24] and [28-45] don't admit 4-cut shuffles — the cluster
geometry (Δv constraints between non-adjacent big-cluster nodes)
is too tight.

Standard TSP double-bridge assumes:
1. Any reordering of nodes is at least feasibly walkable.
2. The objective (tour length) is the only quality metric.

Our problem (time-dependent ATSP with Δv constraints):
1. Most reorderings are infeasible (Δv too high for non-adjacent
   nodes at the specific (td, tof) of the walk).
2. Even feasible walks may violate the n_exc budget.

## The lesson

Standard TSP / LNS / ILS heuristics often assume "any permutation
is at least feasibly walkable." For constrained variants (CVRP,
time-windows, capacity, our Δv-bounded ATSP), this assumption FAILS,
and standard kicks/swaps reject too aggressively.

Adaptations needed:

1. **Constraint-respecting kicks.** Restrict swaps to *nearby* nodes
   in the constraint-distance metric (e.g., within-cluster moves
   only; not cross-cluster).
2. **Soft-feasibility kicks.** Allow temporary infeasibility,
   repair via re-walk with exception fallback.
3. **Domain-specific kicks.** For our problem: the productive kick
   is the C-013/C-017 cluster-bridge insertion, not double-bridge.

## Domain-specific kick taxonomy (Ch2)

| kick | works for | reason |
|---|---|---|
| 2-opt (adjacent swap) | yes | small structural change preserves cluster |
| Or-opt (move 1-3 nodes) | yes | usually preserves cluster |
| Double-bridge (4-cut) | NO | too aggressive for tight Δv |
| Cluster-bridge insertion | YES | domain-aware (C-013) |
| Sub-tour insertion | YES | domain-aware (C-017) |
| Reserved-budget greedy restart | YES | restructures via C-018 |

## When to use TSP textbook heuristics

If the problem is:
- Pure-distance TSP (no constraints) → use textbook
- Add capacity / time windows / exceptions → DOMAIN ADAPTATION

A useful sanity check: implement the textbook version FIRST,
measure the feasibility rate of its moves. If < 10%, the textbook
move is too aggressive for your constraint structure.

## Generalization

Standard heuristics encode assumptions about the problem class.
Read those assumptions; verify they hold in your variant. If not,
the heuristic needs ADAPTATION, not just parameter tuning.

Examples:
- A* heuristic must be admissible — verify before using on a new
  cost function.
- K-means assumes Euclidean; for spherical data, use spherical
  K-means.
- Standard simplex assumes bounded LP; for unbounded, dual or
  big-M is needed.

## Impact / scope

~30 min wasted on the double-bridge ILS attempt. Useful: confirmed
the basin is structurally tight, which informed the medium pipeline
to use sub-tour insertion (C-017) instead of standard LNS kicks.
