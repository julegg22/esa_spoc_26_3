---
id: T-006
type: takeaway
status: final
tags: [ch2, lambert, framing, decision-rationale]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
supports_verdict: inconclusive
confidence: high
generalizability: subgoal-wide
goal_contribution: "Ch2 = sparse constrained-Hamiltonian-path; method = time-optimal per-edge Δv (global over 200 d) + constrained routing with ≤5 exception bridges."
effort_person_hours: 0.6
superseded_by:
invalidated_by:
invalidated_at:
---

# T-006 — Ch2 method: time-optimal edges + constrained routing

## Summary

Ch2 (`small`, N=49) is a **sparse, time-coupled constrained
Hamiltonian-path** problem, not a metric TSP (E-012/E-013). Only
~4 % of pairs are ≤100 m/s; feasibility needs ≥43 of 48 legs ≤100
plus ≤5 "exception" legs ≤600. Cheap edges live in **narrow,
recurring (t_dep,tof) windows** tied to ~0.2–1.9 d orbital periods
over the **200-day** horizon.

## Implications — the method

Two coupled sub-problems, solved in order:

1. **Time-optimal edge Δv** (the M-002 hurdle): for each ordered
   pair, `min Δv` over `t_dep ∈ [0,200 d]` (multi-window /
   periodicity-aware global search) × `tof` × built-in multi-rev,
   storing the realizing `(t_dep,tof)`. This builds the true
   cheap-edge graph (denser than the 89 a coarse probe found).
2. **Constrained routing**: a Hamiltonian path maximizing ≤100
   legs, ≤5 legs in (100,600], chronological, minimizing makespan.
   Candidates: OR-tools CP-SAT / routing on the precomputed graph,
   or cluster-by-orbital-elements then route-within + exception
   bridges. (CP-SAT is a known fit — cf. `[[C-003-weighted-3d-matching]]`
   combinatorial experience.)

Naive/greedy constructors are refuted (E-012) — they ignore
connectivity and the time-optimal edge cost.

## Position vs goal

- **Contribution:** 0 Ch2 points yet; official scorer mirrored
  (asset), structure mapped. Ch1 matching ~11 pts remains the only
  banked score.
- **Where we stand:** Ch2 `small` rank-3 ≤ 111.76 d; the method is
  substantial (edge precompute + constrained router) but well-posed
  and data-grounded. `medium`/`large` reuse the same machinery.
- **Next move:** build the time-optimal edge precompute, re-probe
  density, then the constrained router; bank `small`.

## Caveats

If even the true cheap graph stays too sparse for a ≤5-exception
Hamiltonian path, the instance may demand exploiting orbital
*clusters* explicitly (sequence within near-co-orbital families).
