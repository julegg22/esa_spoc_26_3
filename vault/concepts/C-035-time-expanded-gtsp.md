---
id: C-035
type: concept
status: validated
tags: [optimization, routing, gtsp, time-dependent, time-expanded, glkh, ch2, technique]
scope: optimization/time-dependent-routing
confidence: medium
created: 2026-06-28
sources:
  - "Internal: E-718 (GLKH AGTSP on 12-day buckets — stranded), E-744 (LKH-on-static-cost — strand@0), E-745 (faithful adaptive-window arcs)"
  - "Noon & Bean — An efficient transformation of the generalized TSP into the TSP (1993)"
  - "Helsgaun — GLKH: solving the Generalized TSP via the LKH heuristic"
  - "Ahuja, Magnanti, Orlin — Network Flows (time-expanded graphs)"
related: ["[[C-026-dp-on-time-expanded-graph]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-032-kttsp-problem]]", "[[C-030-lkh3-tsp-solver]]", "[[C-033-fast-faithful-oracle]]", "[[C-034-time-aware-beam-narrow-window-tdtsp]]", "[[C-036-epoch-shift-trap]]"]
---

# C-035 — Time-expanded GTSP for joint sequence + epoch routing

*The principled global solver for a time-dependent TSP where order and
timing cannot be decoupled: replicate each city into time-window copies,
make each city a GTSP "cluster", and let a generalized-TSP solver pick
one copy per city — choosing **when** to visit each city and **in what
order** in a single optimization.*

## The problem it targets

A time-dependent TSP / constrained Hamiltonian path (see
[[C-010-constrained-hamiltonian-time-dependent-routing]],
[[C-032-kttsp-problem]]) where an edge (i,j) is cheap/feasible only in
epoch-specific windows and the objective couples order with timing. A
plain TSP on a static cost matrix is wrong here — every edge's cost
depends on *when* you traverse it, and a single fixed cost per edge
forces a lie (see [[C-036-epoch-shift-trap]]). The forward DP on a
time-expanded graph ([[C-026-dp-on-time-expanded-graph]]) solves the
**fixed-order retiming** exactly but not the **joint ordering**.

## The construction

1. **Replicate** each city `c` into `K` time-window copies `(c, w₁..w_K)`.
   Each copy = "visit c with departure in window w". Place windows where
   the city actually has cheap departures, not on a uniform grid.
2. **Cluster = city.** GTSP requires visiting exactly one node per
   cluster ⇒ exactly one epoch chosen per city.
3. **Arcs** `(i,w_a) → (j,w_b)` exist iff a cheap transfer i→j departing
   in window `w_a` arrives in window `w_b`; arc cost = tof (or arrival
   time). Forward-in-time only.
4. **Open path via a dummy depot cluster** with 0-cost arcs to/from every
   node — turns the GTSP *cycle* into an open chronological path.
5. **Solve** with GLKH (handles AGTSP — asymmetric, no Noon-Bean big-M).
   Decode: one node per cluster ⇒ the visiting order **and** each city's
   epoch. Then chrono-validate faithfully and compute the true objective.

## The load-bearing tradeoff (why it is hard, not just heavy)

**Resolution vs tractability.** Nodes = cities × K. The GLKH cost matrix
is (cities·K)². Fine windows (large K) capture the true feasible bands
but blow up the matrix; coarse windows (small K) stay solvable but the
window centers no longer predict the precise arrival epoch, so the
decoded order fails to chrono-validate. This single tension is what
walled the campaign's first attempt (E-718: 12-day uniform buckets vs
~0.002-day feasible bands → arcs that don't chain → strands).

## What makes it finally viable (the Ch2 fix, E-745)

- **Faithful arcs.** Build arcs with the fast faithful evaluator
  ([[C-033-fast-faithful-oracle]] / `batch_earliest`), not an optimistic
  bucketed table — the arc exists only if a real cheap transfer does.
- **Adaptive windows.** Place each city's K windows at *its own* cheap-
  departure regions (quantiles of where it has cheap out-edges), so a few
  windows per city carry real signal instead of uniform-grid noise.
- **Faithful re-timing on decode.** Use the GTSP only for the hard part
  (the order); recover exact epochs by chrono-walking the decoded order
  with the faithful oracle.

## Relationship to neighbors

- **vs C-026 (DP on time-expanded graph):** same graph idea, different
  question. C-026 finds the optimal *single path / fixed order* retiming
  (shortest path / DP). C-035 also decides the *order* (NP-hard set-cover
  over clusters) — GTSP, not shortest path.
- **vs C-034 (time-aware beam):** the beam is a fast *constructive*
  heuristic that threads one good order; the time-expanded GTSP is the
  *global* optimizer over all orders. Use the beam for a strong incumbent;
  the GTSP to try to beat it / prove rank.
- **vs C-030 (LKH/Concorde on static cost):** static TSP is the wrong
  model for TD problems — see [[C-036-epoch-shift-trap]]. The time
  expansion is exactly what repairs the static model.

## Status / caveat

Validated as the *correct formulation*; not yet shown to beat the banked
incumbent on Ch2-large (the resolution-vs-tractability tradeoff is real
and the build is research-grade). Treat as the named rank-pursuing lever,
not a settled win.
