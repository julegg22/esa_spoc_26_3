---
id: C-010
type: concept
status: confirmed
tags: [optimization, combinatorics, ch2, routing]
scope: optimization/time-dependent-routing
confidence: high
created: 2026-05-19
sources:
  - "Korte & Vygen — Combinatorial Optimization (Hamiltonian path, TSP)"
  - "Gendreau et al. — time-dependent & time-window vehicle routing"
related: ["[[C-006-lambert-problem-and-orbital-tsp]]", "[[C-003-weighted-3d-matching]]", "[[T-006-ch2-method-time-optimal-edges-plus-routing]]", "[[E-015-ch2-cpsat-optimal-but-time-coupling-breaks]]"]
---

# C-010 — Constrained Hamiltonian path & time-dependent routing

*Primer for non-experts: why Ch2 is much harder than "shortest
tour", and why order and timing can't be separated.*

## Definition

- **Hamiltonian path**: a route visiting every node exactly once
  (a path, not a return-to-start cycle). Deciding whether one even
  *exists* on a given graph is **NP-complete**.
- **Constrained** here: only some node-pairs are usable
  ("feasible edges"); a small budget (≤5) of otherwise-forbidden
  "exception" edges is allowed.
- **Time-dependent**: the cost/feasibility of an edge depends on
  *when* you traverse it (and how long) — not a fixed matrix.

## Why it matters here

Ch2 (`[[C-006-lambert-problem-and-orbital-tsp]]`) is precisely a
**time-dependent constrained Hamiltonian path**. Two traps a
non-expert (or a first solver) falls into:

1. **"It's a metric TSP."** No — most edges are infeasible
   (Δv ≫ caps); it is a *feasibility-graph path* problem. A nearest-
   neighbour/greedy builder **strands itself**: it consumes the few
   cheap edges and leaves a remainder with no feasible completion
   (E-012/E-014). Feasibility is a *global* property of the whole
   order.
2. **"Solve the order, then time it."** No — edge cost depends on
   the *absolute departure epoch*; an edge that is cheap at its own
   best time is wildly infeasible at the time the chosen order
   forces (E-015: a CP-SAT-optimal static path had 36/48 legs blow
   past the hard cap after chronological re-timing). **Order and
   timing must be optimised jointly.**

## Mechanics

Standard handles for time-dependent routing:
- **Feasibility graph**: precompute which (i,j) are ever ≤ cap and
  the *windows* (departure-time intervals) where they are — costs
  recur ~periodically (orbital phasing / synodic beat).
- **Time-expanded graph**: duplicate each node per time-bucket;
  arcs only between compatible buckets → a static path search on a
  big graph encodes the timing.
- **Co-optimisation**: search the permutation while re-deriving
  per-leg timing over the *full horizon* (windows recur, so waiting
  for the next cheap window is the key lever).

## In practice

Campaign method (`[[T-006-ch2-method-time-optimal-edges-plus-routing]]`):
time-optimal per-edge precompute, then a joint order+timing
solver — CP-SAT on a time-expanded model
(`[[C-009-constraint-programming-cp-sat]]`) or a metaheuristic
(`[[C-011-metaheuristic-local-search-routing]]`) with full-horizon
per-leg re-timing and the official scorer as objective.

## References

Korte & Vygen; time-dependent VRP literature; nodes E-012/14/15,
T-006.
