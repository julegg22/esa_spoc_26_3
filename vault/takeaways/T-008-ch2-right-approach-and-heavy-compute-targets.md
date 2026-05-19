---
id: T-008
type: takeaway
status: draft
tags: [ch2, framing, decision-rationale, methodology]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
supports_verdict: inconclusive
confidence: high
generalizability: subgoal-wide
goal_contribution: "The right Ch2 approach is identified; heavy-compute targets are precisely scoped (NOT edge resolution; YES multi-window extraction + time-windowed CP-SAT)."
effort_person_hours: 6
superseded_by:
invalidated_by:
invalidated_at:
---

# T-008 — Ch2: the right approach + where heavy compute pays

*Synthesis of the 6-hour autonomous research window (2026-05-19).
Status: draft — finalised once the TW prototype + Q6 medium/large
land.*

## The right Ch2 approach (data-grounded)

After 7+ method iterations (greedy → greedy-wait → structure-router
→ static CP-SAT → joint-LNS → cluster-decomp → fullhorizon-CP-SAT)
and 6 dedicated characterisation experiments (Q1–Q5 + E-019), the
right Ch2 method is now precisely scoped:

1. **Edge precompute**: keep the *coarse* level (E-019/Q3: 16×
   more compute = zero new cheap edges). The 138 ≤100 / 837 ≤600
   directed edges are essentially complete.
2. **Cluster-structure premise**: 4 orbital families
   [40, 3, 3, 3] separated by altitude + inclination
   ([[observations/O-007-ch2-small-structure-characterized|O-007]]),
   small↔small forbidden within 600 m/s, so any Hamiltonian path
   **splits the big cluster** + uses 4–5 inter-cluster bridges
   within the ≤5-exception budget.
3. **Solver = time-windowed CP-SAT** (not static CP-SAT, not
   constructive heuristics):
   - time variables `T[v]` per tomato + chronology constraints per
     used arc (`T_i ≤ t_dep, T_j = t_dep + tof`);
   - exception count ≤ 5; objective = makespan;
   - **multi-window arcs** if single-window is infeasible (each
     used edge picks among its precomputed cheap windows).

## Where heavy compute pays (the user's question)

The empirically-grounded ranking (high → low marginal value):

| target | marginal value | rationale |
|---|---|---|
| **Multi-window precompute** | **HIGH** | each (i,j) currently stored as ONE window (global TD/TF); time-coupling (E-018) needs the LIST of cheap windows per pair so CP-SAT can pick one consistent with chronology. ~5–15 windows / pair × 2352 pairs (small). Parallel mp.Pool ~hours. |
| **Time-windowed CP-SAT solving** | **HIGH** | The chronology-respecting model. CP-SAT with `OnlyEnforceIf` over arcs+windows. ~10–60 min per instance solve (single solver run; user-tunable via `max_time_in_seconds`). |
| **medium / large** scale-up | **HIGH** (conditional on Q6) | If Q6 confirms same structural class, the same pipeline runs on those instances at ~3–4× cost (medium) and much more (large; N=1051 has 1.1M pairs → multi-window precompute is the cost; CP-SAT itself fine). |
| Edge-search resolution | **ZERO** (E-019) | 16× more compute → zero cheap-edge gain. Stop here. |
| Multi-method retry of constructive/LNS on the existing static edges | LOW (E-014/E-016) | refuted; constructive search can't satisfy global feasibility. |

## Synthesis of the unsolved sub-problem

What we *can* solve fast: edge cost, cluster identification, static
CP-SAT. What we *cannot* yet: a Hamiltonian path whose cheap edges
are reachable in chronological order. The time-windowed model
([[concepts/C-010-constrained-hamiltonian-time-dependent-routing]])
is the principled formulation; the prototype `ch2_cpsat_tw` is built
and ready (single-window first; multi-window if needed). Pending its
result + Q6 (medium/large generalisation).

## Position vs goal

- **Banked: ~11 pts** (Ch1 matching, locked).
- **Methodology-validation deliverable** (`GOALS.md §3`): very
  strong — M-001/M-002 codified, C-001…C-011 cover the domain for
  non-experts, E-006…E-019 + O-001…O-007 + T-001…T-008 form a
  complete scientific trail (incl. multiple M-002 reframes that
  actually reframed the problem usefully).
- **Ch2 endgame**: time-windowed CP-SAT is the principled next
  build; even partial feasibility on small banks points (rank-10
  on small ≈ 1 pt; rank-3 = 8 pt × ×1 = 8 pt; medium/large reuse
  the pipeline).

## Caveats (until finalised)

The TW prototype's outcome is the critical missing data point. If
it returns FEASIBLE on `small`, we have the first banked Ch2 tour.
If INFEASIBLE, multi-window extraction is the unblocking step.
Q6 confirms generalization (or surfaces medium/large idiosyncrasies).
