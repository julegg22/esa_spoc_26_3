---
id: C-020
type: concept
status: confirmed
tags: [optimization, lns, computational, primitive]
scope: optimization/local-search + computational
confidence: high
created: 2026-05-21
sources:
  - "[[E-031-ch2-medium-first-feasible]]"
related: ["[[C-013-cluster-bridge-insertion-pattern]]", "[[C-017-subtour-bridge-insertion-large-clusters]]"]
---

# C-020 — Bridge-prefilter (pre-evaluate the bottleneck constraint)

*Primer: when LNS / insertion candidates each cost O(L) to fully
evaluate, pre-check ONE bottleneck constraint that rejects ~95%
of candidates in O(1) — reducing total work by 20×.*

## The pattern

For an LNS / insertion / move that requires:
- a full re-evaluation costing O(L) (e.g., walk_perm_chrono on the
  entire perm),
- with most candidates failing on a SPECIFIC constraint (e.g., the
  in-bridge arc feasibility),

**Pre-check the bottleneck constraint first** and skip full
evaluation for candidates that fail it.

```python
# Naive: full walk for every candidate (slow)
for candidate in candidates:
    times, tofs, ok = full_walk(perm + candidate)   # O(L)
    if not ok: continue
    ...

# Bridge-prefilter: O(1) check per candidate
prewalk = full_walk(partial_perm)                   # O(L), once
for candidate in candidates:
    bridge_ok = check_bridge_arc(prewalk, candidate) # O(1)
    if not bridge_ok: continue
    times, tofs, ok = full_walk(...)                # O(L), only on survivors
    ...
```

## Why it matters

For Ch2 medium sub-tour insertion (C-017):
- 156 candidate insertion positions × 5 sub-tours × 2 directions
  = 1560 candidates.
- Each full walk: ~50ms × 176 legs ≈ 9 s.
- Naive: 1560 × 9 = 14,040 s = ~4 hours.
- Bridge-prefilter: 1560 × 12ms (one bridge check) +
  ~50 survivors × 9 s = 19 + 450 = ~8 minutes. **~30× speedup**.

## Conditions for applicability

- ONE constraint causes the vast majority of failures (a
  "bottleneck" — bridge arc, time-window, capacity at a critical
  step).
- That constraint can be evaluated in O(1) given a prewalk /
  precomputation.
- The full evaluation has high constant overhead (so the prewalk
  cost amortizes).

## The Ch2 medium variant

The "bridge" = first arc of the candidate insertion. Pre-walk the
partial perm once; cache `visit_time[k]` for each position k. For
each insertion position p:
1. Bridge from = partial[p-1], to = sub-tour[0], at time
   `visit_time[p-1] + tof[p-1]`.
2. Call `find_earliest_transfer(from, to, t_bridge, dv_cap, ...)`.
   O(`n_steps`) = ~12 ms.
3. If no feasible tof in [tof_min, tof_window]: skip.
4. Otherwise do full walk.

## Where else this pattern applies

- VRP / TSP with capacity: pre-check capacity at the cut position.
- Scheduling with deadlines: pre-check the tightest deadline.
- Graph routing with edge bottlenecks: pre-check max-flow at the
  critical edge.

## In practice

`src/esa_spoc_26/ch2_subtour_insert_fast.py`:
- `prewalk_partial(kt, partial)` — caches partial visit times.
- `fast_insert_subtour(...)` — implements the bridge-prefilter
  loop.

## References

- E-031 (Ch2 medium first feasible, made tractable by this
  pattern).
- C-017 (the LNS move that uses this prefilter).
