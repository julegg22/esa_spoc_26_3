---
id: C-009
type: concept
status: confirmed
tags: [optimization, cp-sat, ch2, tool]
scope: optimization/constraint-programming
confidence: high
created: 2026-05-19
sources:
  - "Rossi, van Beek, Walsh — Handbook of Constraint Programming"
  - "Google OR-Tools CP-SAT docs (developers.google.com/optimization)"
related: ["[[C-004-mip-and-mip-lns]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[L-003-ortools-added-for-ch2-cpsat]]", "[[E-015-ch2-cpsat-optimal-but-time-coupling-breaks]]"]
---

# C-009 — Constraint Programming & CP-SAT

*Primer for non-experts: the "declare the rules, let the solver
find a configuration" tool we added for Ch2.*

## Definition

**Constraint Programming (CP)** states a problem as variables +
**constraints** (logical/combinatorial relations) and asks a solver
to find an assignment satisfying them (optionally optimising an
objective). **CP-SAT** is Google OR-Tools' engine: it compiles the
model down to Boolean **SAT** (satisfiability) plus integer
reasoning and searches with conflict-learning — very strong on
*feasibility-heavy combinatorial* problems.

## Why it matters here

Ch2 is a **constrained Hamiltonian path**
(`[[C-010-constrained-hamiltonian-time-dependent-routing]]`):
pick a visiting order using only feasible (≤600 m/s) edges, ≤5 of
them "exceptions", minimise makespan. That is a feasibility-first
combinatorial structure where greedy strands (E-014) and a metric
TSP view is wrong — exactly CP-SAT's wheelhouse. We added
`ortools` (`[[L-003-ortools-added-for-ch2-cpsat]]`) and modelled it
with `AddCircuit` (see Mechanics). *Caveat learned* (E-015):
CP-SAT solved the **static** edge graph to optimality, but Ch2's
edge costs are **time-dependent**, so a static CP model is
necessary-not-sufficient — the timing must be co-optimised.

## Mechanics

- **Variables**: a Boolean per candidate arc (i→j "used").
- **`AddCircuit(arcs)`**: forces the chosen arcs to form one
  circuit covering all nodes. A *path* (not cycle) is modelled by
  adding a virtual **depot** with zero-cost arcs to/from every
  node — the circuit through the depot is a Hamiltonian path over
  the real nodes.
- Side constraints as linear sums of the arc Booleans (e.g.
  `Σ exception_arc ≤ 5`); objective `Σ cost·arc`.
- Search: SAT-style branching + clause learning + LP bounds;
  returns OPTIMAL/FEASIBLE with a proven gap.

## In practice

`src/esa_spoc_26/ch2_cpsat.py`. CP-SAT excels when feasibility is
the hard part and constraints are logical/counting (vs MIP
`[[C-004-mip-and-mip-lns]]`, better for strong LP relaxations).
Gotcha: a model that abstracts away a real coupling (here, time)
can be solved "optimally" yet be useless — validate the decoded
solution on the true scorer.

## References

OR-Tools CP-SAT docs; Rossi-van Beek-Walsh; nodes E-015 / L-003.
