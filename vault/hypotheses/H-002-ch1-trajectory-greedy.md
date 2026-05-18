---
id: H-002
type: hypothesis
status: draft
tags: [ch1, astrodynamics, bcp, improvement]

parent: "[[Q-001-rank3-each-regular-instance]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: []
children_hypotheses: []
concurrent_with: ["[[H-001-ch1-matching-mip]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]

created: 2026-05-18
tested_start:
tested_end:
duration_testing:

effort_person_hours:
expected_points: 14          # rank-3 on A_3 ×(4/3)² ≈ 8 × 1.78
estimated_effort_h: 12
priority: 2
mode: full

claim: >
  Computing ≤3-impulse Earth-orbit→Moon-orbit transfer masses in the
  BCP, then a greedy (or ILP) 3-D assignment on the capacity-
  discounted delivered mass, reaches rank-3 on `trajectory-matching`.
falsifiable_prediction: >
  Sketch (refine on promotion): total delivered mass ≥ 452819.87
  (= rank-3 cutoff, [[observations/O-002-leaderboard-2026-05-18|O-002]]
  2026-05-18) from a valid 8400-dim decision vector, within a
  compute budget to be set at promotion.
modification_rationale:      # null — rooted directly on Q-001

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-002 — Ch1 trajectory-matching via greedy on computed BCP transfers

## Why this alternative was considered

[[observations/O-002-leaderboard-2026-05-18|O-002]]: Team HRI's
rank-3 `trajectory-matching` submission is literally named "Greedy
solution" (mass −452819.87). That is direct evidence a non-exotic
pipeline — compute BCP ≤3-impulse transfers, then greedy 3-D
assignment on discounted mass `m_d=min(m_l,(200−ΔT)c_ld)` — clears
rank-3. ×(4/3)² weight makes it high-value. The user's physics
strength (BCP, [[user]]) fits the hard part: per-pair trajectory
optimisation.

## Falsifiable prediction (sketch)

See frontmatter; sharpen the compute budget and the transfer-model
fidelity threshold when promoted from draft to open (META.md §16).

## Next steps

Promote after H-001 closes (or in parallel if a second compute
stream opens — concurrent_with H-001/H-003).
