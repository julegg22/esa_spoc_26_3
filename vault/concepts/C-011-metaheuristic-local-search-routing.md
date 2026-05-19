---
id: C-011
type: concept
status: confirmed
tags: [optimization, metaheuristic, lns, ch2]
scope: optimization/local-search
confidence: high
created: 2026-05-19
sources:
  - "Pisinger & Ropke — Large Neighborhood Search (Handbook of Metaheuristics)"
  - "Croes (2-opt); Or (Or-opt); Lin-Kernighan literature"
related: ["[[C-004-mip-and-mip-lns]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]
---

# C-011 — Metaheuristic local search for routing

*Primer for non-experts: how the Ch2 solver improves a tour by
small smart edits — and how this differs from the MIP-LNS of C-004.*

## Definition

A **metaheuristic local search** keeps a current solution and
repeatedly applies small **moves**, accepting some by a rule, to
escape bad local optima. For tours/permutations the staple moves:

- **2-opt**: reverse a contiguous segment (un-crosses the route).
- **Or-opt**: relocate a short chain (1–3 nodes) elsewhere.
- **Ruin-and-recreate (LNS)**: remove *k* nodes, reinsert them
  cheaply (a "large" neighbourhood — many nodes change at once).
- **Acceptance**: take improving moves always; accept some worse
  ones (probability / simulated-annealing-like) to avoid getting
  stuck.

## Why it matters here

Ch2 needs the **order and timing optimised jointly**
(`[[C-010-constrained-hamiltonian-time-dependent-routing]]`) and
exact methods over the time-expanded space are huge. A metaheuristic
searches the *permutation* directly while a decoder re-derives
full-horizon per-leg timing and the official scorer judges it
(feasibility-dominant cost). Robust to the sparse, rugged feasible
landscape where constructive greedy strands (E-014).

**Distinct from `[[C-004-mip-and-mip-lns]]`:** there, "LNS" repairs
the ruined part with an *exact MIP sub-solve* (Ch1 matching). Here
the repair is *heuristic* (cheap reinsertion / 2-opt), because the
Ch2 sub-problem (timed feasible reinsertion) has no cheap exact
oracle. Same "ruin-and-recreate" idea, different recreate engine.

## Mechanics

Iterate: perturb (2-opt / Or-opt / ruin-recreate) → decode
(per-leg full-horizon timing) → score (official-mirror fitness,
infeasibility ≫ makespan) → accept if ≤ current (rare worse for
diversification) → track best. Good initial order from the
cheap-edge graph seeds the search near feasibility.

## In practice

`src/esa_spoc_26/ch2_lns.py`. Levers: move mix, ruin size *k*,
acceptance temperature, decode caching (the full-horizon timing is
the cost bottleneck — cache per (i,j,quantised t_ready), or
precompute per-pair Δv windows for O(N) decode). Pairs naturally
with CP-SAT (`[[C-009-constraint-programming-cp-sat]]`) as a
warm-start or polish.

## References

Pisinger & Ropke; 2-opt/Or-opt/Lin-Kernighan; node H-003.
