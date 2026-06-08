---
id: C-028
type: concept
status: confirmed
tags: [optimization, metaheuristic, lns, alns, destroy-repair, ch2]
scope: optimization/metaheuristic
confidence: high
created: 2026-06-07
sources:
  - "Pisinger & Ropke — Large Neighborhood Search, in Handbook of Metaheuristics (Springer, 2010)"
  - "Ropke & Pisinger — An ALNS heuristic for the PDPTW (Transp Sci, 2006)"
related: ["[[C-011-metaheuristic-local-search-routing]]", "[[C-027-simulated-annealing]]", "[[C-026-dp-on-time-expanded-graph]]"]
---

# C-028 — Adaptive Large Neighborhood Search (ALNS)

*Our main metaheuristic. Combines destroy/repair with SA acceptance
and dynamic operator weighting.*

## Definition

**Large Neighborhood Search (LNS)** iteratively destroys part of a
solution and repairs it via a different (usually constructive)
operator. The "large" refers to neighborhood size — many positions
change per iteration, vs single-move LS (2-opt, swap).

**Adaptive LNS (ALNS)** adds:
1. Multiple destroy operators (random-k, worst-leg, cluster-target, …)
2. Multiple repair operators (greedy-insert, regret-k, sequential-best, …)
3. **Acceptance criterion** — typically SA (see [[C-027]]).
4. **Operator weight adaptation** — operators that produce accepted
   moves get higher selection weights. Bad operators are downweighted.

ALNS scales better than LNS-with-single-operator because the algorithm
"discovers" which operators work for which local geometries.

## Why it matters here

We use ALNS as the **search engine on top of the DP evaluator**:
- Destroy: pick a perm mutation (random-k, segment-reverse, swap,
  double-bridge).
- Repair: random insertion (most operators are perm-internal
  rearrangements so no explicit insertion needed).
- Evaluate: DP on time-expanded graph (see [[C-026]]).
- Accept: SA.

This is the architecture of E-529 (the breakthrough that took small
142 → 116 d in 12.5 h) and E-543 (medium analogue, in progress).

## Mechanics for KTTSP

### Destroy operators (perm mutations)
- `random_k`: remove k random nodes, reinsert at random positions.
  k ∈ [3, 7] for small, may scale with n.
- `segment_reverse`: 2-opt — reverse a contiguous segment.
- `double_bridge`: 4-opt classic — three cuts, rearrange the four
  pieces. Resists 2-opt undo.
- `swap`: exchange two non-adjacent positions.
- `worst_leg` (proposed, not implemented): rank legs by current
  tof/min-tof ratio, remove top-k.

### Repair operators
- `random_insert`: shuffle removed nodes, insert at random positions.
  Simplest; DP-eval filters infeasibles fast.
- `regret-k` (proposed): insert nodes in order of "regret" — how
  much worse the 2nd-best position is than the best.
- `LKH-3 sub-tour rebuild` (proposed): for large destroy windows,
  run LKH-3 ([[C-030]]) on the residual subgraph.

### Operator weight adaptation

We do not yet implement adaptive weighting; current ALNS uses fixed
weights chosen by intuition. **Improvement opportunity**: track
operator success rates (per accept) and reweight every K iters.

## In practice

- `scripts/ch2_e529_dp_alns.py` — first productive DP-ALNS on small
  (10 bankings in 12.5 h, plateau at 116.38 d).
- `scripts/ch2_e530_cluster_alns.py` — added larger destroys
  (segment 8-15 nodes) + small-comp shuffle. Didn't escape 116.38
  basin — operators too local for the residual barriers.
- `scripts/ch2_e538b_dp_alns_lkh_seed.py` — dual-seed (bank + LKH-3),
  characterized the basin separation.
- `scripts/ch2_e543_medium_dp_alns.py` — medium DP-ALNS using a
  curated pair-fine table.

## ALNS pitfalls we hit

1. **Bank-adjacent saturation**: after the first ~12 h of productive
   runs, the operator set exhausts bank's basin. Symptom:
   accepted moves keep happening, but no new banks. Fix: bigger
   destroys, or crossover between elite perms.

2. **Diverse seeds don't help if SA can't bridge basins**: E-538b
   showed that even starting from a structurally different perm
   (LKH-3, 125 d) doesn't lead to better outcomes — the chain stays
   stuck near its seed because uphill barriers between bank and LKH-3
   basins exceed SA's acceptance probability.

3. **DP-feasibility rate ~1 %**: most random perms are DP-infeasible
   (the cheap-edge graph is sparse). 99 % of ALNS work is rejected.
   Compute-wise: this is OK because DP rejection is fast (early-exit
   when no sink reached). Wall ~5 ms per rejected vs ~3 s per accepted.

## When ALNS plateaus, the options are:

- Add destroy operators that respect problem structure (e.g.,
  cluster-aware: target one whole small comp of the cheap graph).
- Add **crossover** operators (combine pieces of two elite perms).
- Run **multiple chains with periodic exchange** (island model).
- **Restart hot** from elite pool every N hours.

## References

- E-029 / E-032 — DP-ALNS breakthroughs.
- E-538b — basin-separation diagnostic.
- M-general-foundation-then-search.md — why ALNS only matters after
  evaluator is right.
