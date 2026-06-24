---
id: C-018
type: concept
status: confirmed
tags: [optimization, meta-heuristic, construction, primitive]
scope: optimization/construction + meta-heuristic
confidence: high
created: 2026-05-21
sources:
  - "E-031-ch2-medium-first-feasible"
related: ["[[C-013-cluster-bridge-insertion-pattern]]", "[[C-017-subtour-bridge-insertion-large-clusters]]", "[[C-011-metaheuristic-local-search-routing]]"]
---

# C-018 — Reserved-budget construction

*Primer: when a problem has a limited "expensive resource" budget
(e.g., exception arcs, fuel reserves, time slack), cap construction
heuristics below the budget so resource remains for downstream
repair.*

## The pattern

A constructive heuristic (e.g., greedy_findxfer) that greedily uses
all available expensive resources at construction time will leave
ZERO BUDGET for downstream local search / repair / LNS to insert
missing pieces.

**Solution**: artificially CAP the resource at construction time,
reserving a portion for repair.

```python
# Default greedy uses all budget
kt.n_exc = 5
perm, ... = greedy(kt, start)   # exhausts all 5 excs → no repair budget

# Reserved-budget greedy
kt.n_exc = 1                    # cap at 1, reserves 4 for repair
perm, ... = greedy(kt, start)   # uses ≤ 1 exc; 4 left for bridges
kt.n_exc = 5                    # restore for final feasibility check
# now insert missing clusters via C-017, each using 2 excs
```

## Why it matters

For Ch2 medium (n=181):
- Default `n_exc=5` greedy from start=3 hybrid: 156/180 covered, 5/5
  excs used. Can NOT bridge the 25-node missing cluster — budget
  exhausted.
- Cap `n_exc=1`: 134/180 covered, 1/5 excs used. **4 excs available**
  for two 20-node cluster bridges (2 excs each) → both bridge,
  feasible.

**Counter-intuitively**: a SHORTER initial perm is BETTER if it
preserves budget for the harder downstream insertions.

## How to set the cap

Estimate: `cap = n_exc − 2 × (expected_num_big_clusters)`. For
medium: 5 − 2×2 = 1. For small: 5 − 2×3 = −1 (infeasible by this
rule — small must use a different decomposition; in fact its
banked solution uses 5/5 excs because small-cluster insertions
share excs (start/end clusters need only 1 bridge each)).

## Where to use

Any constructive-then-repair pipeline where:
- Construction can over-use an expensive resource,
- Repair / LNS needs the same resource,
- The two phases compete for the same budget.

Examples beyond Ch2:
- VRP with limited # vehicles: cap vehicles in construction,
  reserve for split-deliveries
- Container-loading with limited container slots
- Multi-modal scheduling with limited "express mode" tokens

## Caveats

- Too tight a cap: construction stalls too early; repair faces too
  large a residual.
- Too loose: construction uses all budget; repair fails.
- The optimal cap depends on problem structure — sweep is often
  needed (we tried n_exc ∈ {0, 1, 2, 3} for medium).

## In practice

`src/esa_spoc_26/ch2_subtour_insert_fast.main` calls
`kt.n_exc = N_RESERVE` before calling `greedy_variant`, then
restores after. The Ch2 medium banked solution at 274.52 d
required this exact pattern.

## References

- E-031 (Ch2 medium first feasible at 274.52 d, requires reserved
  budget).
- C-013, C-017 (the repair patterns that use the reserved budget).
