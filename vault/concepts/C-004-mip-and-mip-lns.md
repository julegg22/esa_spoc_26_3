---
id: C-004
type: concept
status: confirmed
tags: [optimization, milp, lns, ch1]
scope: optimization/milp
confidence: high
created: 2026-05-19
sources:
  - "Wolsey, Integer Programming"
  - "Pisinger & Ropke, 'Large Neighborhood Search', Handbook of Metaheuristics"
  - "HiGHS solver docs (highs.dev)"
related: ["[[C-003-weighted-3d-matching]]", "[[H-004-ch1-matching-mip-lns]]", "[[T-002-mip-lns-family-validated-but-plateaus]]", "[[L-001-greedy-localopt-and-suppressed-solver-log]]"]
---

# C-004 — MIP and MIP-based LNS

*Primer for non-experts: the method that broke the greedy ceiling
on Ch1.*

## Definition

- **LP — Linear Program**: optimise a linear objective under linear
  constraints with *continuous* variables. Solved efficiently and
  exactly.
- **MIP / MILP — (Mixed-)Integer Linear Program**: an LP where some
  variables must be **whole numbers** (here 0/1: take a triple or
  not). Integrality makes it **NP-hard** in general.
- **LNS — Large Neighborhood Search**: a metaheuristic — repeatedly
  **destroy** part of a solution and **repair** it, keeping
  improvements. "Large" because each step can rearrange a big chunk,
  unlike single-swap local search.
- **MIP-based LNS**: the repair step is itself a *small exact MIP*
  solved over the destroyed region.

## Why it matters here

Ch1 matching (`[[C-003-weighted-3d-matching]]`) is an NP-hard ILP.
Two failures and one success, all observed in this campaign:

1. **Default exact MIP (HiGHS)** on the full 25 000-variable
   problem: stalled at 79 % of rank-3 with a 122 % optimality gap —
   the 3-D-matching LP relaxation is too *weak* to prune the search.
2. **Greedy + plain local search**: stuck at the greedy local
   optimum (89 %) — see `[[L-001-greedy-localopt-and-suppressed-solver-log]]`.
3. **MIP-based LNS** (`[[H-004-ch1-matching-mip-lns]]`): *destroy*
   a random subset of chosen triples, freeing their e/l/d; *repair*
   by solving that **small** sub-problem exactly with HiGHS; repeat.
   The whole problem is intractable but each sub-problem is easy, and
   the exact re-optimisation makes moves greedy can never reach.
   Jumped to **99.0 %**, then 99.6 % with cooperation/polish
   (`[[T-002-mip-lns-family-validated-but-plateaus]]`).

## Mechanics

Exact MIP solvers use **branch & bound**: solve the LP relaxation;
if a variable is fractional, branch (force it to 0, then to 1),
recurse, pruning branches that cannot beat the best solution. This
only works if the relaxation gives **tight bounds**. For weighted
3-D matching it does not, so brute exact solving is hopeless at
scale — hence the LNS decomposition into many *tractable* exact
sub-solves. Cooperation = parallel workers sharing a global best;
adaptive destroy = enlarge the ripped-out region when progress
stalls (jumps to a new basin).

## In practice

`src/esa_spoc_26/ch1_matching.py`: `greedy`, `mip_lns`,
`coop_mip_lns`, `parallel_*`. Solver: **HiGHS** via `highspy`
(open-source; a commercial solver like Gurobi would likely close
the last ~0.4 %, but none is licensed —
`[[T-004-ch1-matching-ceiling-pivot]]`). Practical gotcha: a long
solver run with its log suppressed is unobservable — always capture
the log (`[[L-001-greedy-localopt-and-suppressed-solver-log]]`).

## References

Wolsey, *Integer Programming*; Pisinger & Ropke (LNS); HiGHS docs.
