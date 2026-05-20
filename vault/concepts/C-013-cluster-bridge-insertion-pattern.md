---
id: C-013
type: concept
status: confirmed
tags: [optimization, ch2, lns, clustering, pattern]
scope: optimization/routing + algorithm/local-search
confidence: high
created: 2026-05-20
sources:
  - "[[O-007-ch2-small-structure-characterized]]"
  - "[[E-022-ch2-banked-145d-cluster-insertion]]"
  - "Pisinger & Ropke, Large Neighborhood Search"
related: ["[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-011-metaheuristic-local-search-routing]]", "[[C-012-earliest-feasible-tof]]", "[[O-007-ch2-small-structure-characterized]]"]
---

# C-013 — Cluster-bridge insertion (the LNS move that finishes the tour)

*Primer for non-experts: when greedy strands a few far-away nodes,
splice them into the middle of the route via two exception bridges.*

## Definition

A **cluster-bridge insertion** is an LNS move tailored to graphs
with a small *unreachable* (under the cheap threshold) subset
`M = {m_1, ..., m_k}` that is internally well-connected but only
externally reachable via *exception* edges (ΔV in
(Δv_thr, Δv_max_exc]).

Given a partial Hamiltonian path `π = [v_0, v_1, ..., v_{L-1}]`
missing `M`, the move:

1. picks a *cut position* `p ∈ {0, ..., L-1}`,
2. picks an *internal ordering* of `M` (k! permutations),
3. forms `π' = π[:p+1] + ordering(M) + π[p+1:]`,
4. evaluates `π'` chronologically (one in-bridge `π[p] → m_1`,
   *k-1* internal cheap legs, one out-bridge `m_k → π[p+1]`),
5. accepts if feasible and makespan-improving.

Two exception bridges are consumed per insertion (one in, one out).
For a single contiguous chain of length k, total budget = 2 + (legs
elsewhere needing exceptions). Hence `n_exc ≥ 2 + (other exceptions)`.

## Why it matters here

`[[O-007-ch2-small-structure-characterized]]` showed Ch2 small has
4 connected components at ΔV ≤ 100 m/s: a big cluster of 40
tomatoes plus three 3-tomato small clusters at the same low
semi-major axis but different inclinations (≈0, π/2, π). The
**small clusters are mutually unreachable** within the ΔV cap
(min inter-small Δv ≥ 1580 m/s) — they must be bridged through
the big cluster.

Constructive greedy (E-022) traversed the big cluster smoothly
but stranded the equatorial small cluster `{4, 17, 11}` because
from any big-cluster end-node, reaching {4, 17, 11} requires
~540–576 m/s (within the 600 m/s exception cap, *just*). The
greedy never spent an exception on entering them.

The cluster-bridge insertion adds them back as a 3-node chain
between two interior big-cluster positions, paying two ~540 m/s
exceptions and three internal ≤100 m/s cheap legs. Total time
cost ≈ 5 d → first banked Ch2 small at makespan **145.80 d**
(polished to 143.79 d via 2-opt).

## Mechanics

```python
for p in range(len(partial_perm)):
    for chain in itertools.permutations(missing):
        new_perm = partial[:p+1] + list(chain) + partial[p+1:]
        times, tofs, ok = walk_chronological(new_perm)
        if ok and feasible and mk < best_mk:
            best = (new_perm, mk)
```

Complexity: `(L) × (k!)` chronological walks. For k=3 missing on
L=46 partial: 46 × 6 = 276 evaluations (a few minutes). For k=5
it's 60 × 120 = 7200 evaluations (hours) — beyond k=4 it gets
expensive and other heuristics (best-k orderings only, or
fragmented insertion across multiple positions) are preferable.

## Where to use vs avoid

**Use** when:
- a partial constructive solver has stranded a *small connected
  subgraph* that's bridge-reachable but not greedy-reachable;
- the subgraph is well-connected internally (low ΔV internal arcs);
- the exception budget has slack for the in/out bridges.

**Avoid / supplement** when:
- the missing subset is large (`k ≥ 5–6`) — combinatorial blowup;
- the missing subset is *split* across several disconnected
  pieces (need multi-position insertion);
- the partial perm itself is poor and the right move is *re-doing*
  the greedy from a different start.

## In practice

`src/esa_spoc_26/ch2_insert_lns.insert_lns` implements this for
k ≤ 4. The top-K variant `ch2_insert_lns_topk` re-derives
partials per start to enumerate multiple seed paths. Combined
with `[[C-012-earliest-feasible-tof|find_earliest_transfer]]` for
the chronological walk, and `[[C-011-metaheuristic-local-search-routing|
2-opt + Or-opt]]` for downstream polish, it produced the full
Ch2 small banked pipeline (E-022, 143.79 d).

## References

- E-022 banked solution.
- O-007 (cluster structure).
- C-011 (broader LNS context).
