---
id: C-036
type: concept
status: validated
tags: [optimization, routing, time-dependent, pitfall, ch2, technique]
scope: optimization/time-dependent-routing
confidence: high
created: 2026-06-28
sources:
  - "Internal: E-587 (static-optimal tour inflates on chrono-walk), E-744 (LKH-on-static-cost strands at leg 0)"
  - "Gendreau et al. — time-dependent vehicle routing (cost is a function of departure time)"
related: ["[[C-035-time-expanded-gtsp]]", "[[C-026-dp-on-time-expanded-graph]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-032-kttsp-problem]]", "[[C-031-grid-quantization-mismatch]]", "[[C-030-lkh3-tsp-solver]]"]
---

# C-036 — The epoch-shift trap (why static cost lies in TD routing)

*In a time-dependent routing problem you cannot first pick an order on a
single-cost-per-edge matrix and then time it. The matrix you optimized
no longer describes the tour you built — the moment the order (and thus
each visit's epoch) changes, every downstream edge's real cost changes
with it. Optimizing the static surrogate produces an order that inflates
or outright strands when walked on a real clock.*

## The mechanism

A static cost matrix assigns each edge (i,j) one number — almost always
its **best-over-all-epochs** cost. A solver (LKH/Concorde) then finds a
tour assuming *every* edge is taken at *its own* best epoch. But a single
timeline can't grant that: the epoch at which you reach city i is forced
by everything before it. So the "optimal static tour":

- **inflates** — real per-leg costs exceed the optimistic matrix entries
  (E-587: a static-optimal Ch2 tour balloons when retimed), or
- **strands** — the next cheap window has already closed by the time you
  arrive, and the leg is simply infeasible (E-744: LKH-on-static-cost
  strands at **leg 0** — the very first edge's best epoch is unreachable
  from the start clock).

The deeper point: order and timing are **not separable** in TD routing
(this is the whole reason for [[C-010-constrained-hamiltonian-time-dependent-routing]]).
Any pipeline of the shape "static TSP → retime afterwards" has the trap
baked in.

## How to recognize it (the tells)

- A tour that looks great by matrix cost but **strands / inflates** the
  instant a faithful chrono-walk is applied.
- The strand is **far upstream** of where it manifests — a choice ~100
  cities back closed the window (so local repair near the failure can't
  fix it; cf. E-741 backtracking).
- Aggregate "optimal cost" looks achievable but no real schedule realizes
  it. (A per-instance / per-leg faithful check exposes it; an aggregate
  metric hides it — a recurring methodology trap.)

## The fixes

1. **Time-expand the model**, don't post-process timing. Encode epochs
   *inside* the optimization: [[C-026-dp-on-time-expanded-graph]] for a
   fixed order, [[C-035-time-expanded-gtsp]] for joint order + epoch.
2. **Epoch-aware cost iteration** (cheap, partial): re-walk the tour on a
   real clock, set each edge's matrix cost to its *realized* value at the
   epoch actually reached, re-solve, repeat. Converges toward a
   self-consistent schedule but does not escape a stranding order.
3. **Faithful evaluation in the loop** ([[C-033-fast-faithful-oracle]]):
   never accept a static-matrix tour without chrono-validating it.

## Why it matters beyond Ch2

This is the generic failure mode of "borrow an off-the-shelf TSP solver
for a time-dependent problem." The solver isn't wrong; the *model handed
to it* (one cost per edge) discards the time dependence. Related to
[[C-031-grid-quantization-mismatch]] (another way a surrogate's
resolution silently misrepresents feasibility). The lesson: in TD
routing, the cost function is `c(i, j, t)` — collapse the `t` and you are
optimizing a different problem than the one you have.
