---
id: H-003
type: hypothesis
status: open
tags: [ch2, astrodynamics, lambert, metaheuristic]

parent: "[[Q-001-rank3-each-regular-instance]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: ["[[E-012-ch2-greedy-baseline-infeasible]]", "[[E-013-ch2-structure-sparse-cheap-graph]]", "[[E-014-ch2-constructive-routers-refuted]]", "[[E-015-ch2-cpsat-optimal-but-time-coupling-breaks]]", "[[E-016-ch2-lns-infeasible-cluster-structure]]", "[[E-017-ch2-cluster-infeasible-root-cause]]"]
children_hypotheses: []
concurrent_with: ["[[H-001-ch1-matching-mip]]", "[[H-002-ch1-trajectory-greedy]]"]

created: 2026-05-18
tested_start:
tested_end:
duration_testing:

effort_person_hours:
expected_points: 8           # rank-3 on A_1 ×1
estimated_effort_h: 8
priority: 3
mode: full

claim: >
  Precomputing a feasible Lambert transfer time-grid for Ch2 `small`
  (N=49), then LNS/GA over visiting order + departure/tof timing
  with local Lambert refinement, reaches a makespan at the rank-3
  level.
falsifiable_prediction: >
  Sketch (refine on promotion): valid 145-dim chromosome with
  makespan f = t_{N-1}+tof_{N-1} ≤ 111.76 d (= rank-3 cutoff,
  [[observations/O-002-leaderboard-2026-05-18|O-002]] 2026-05-18),
  respecting ΔV_max + ≤E exception legs.
modification_rationale:      # null — rooted directly on Q-001

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-003 — Ch2 small via Lambert-precompute + LNS/GA

## Why this alternative was considered

Cheapest Ch2 entry point (N=49, dim 145). Ch2 is a time-dependent
ATSP with Lambert costs ([[observations/O-001-spoc4-problem-grounding|O-001]]);
[[observations/O-002-leaderboard-2026-05-18|O-002]] shows the top
teams use strong metaheuristics over a precomputed feasible
time-grid. `small` rank-3 = 111.76 d (5 teams). Establishes the Ch2
toolchain (pykep 2.x `compute_transfer`, `TomatoProblem`) reused by
`medium`/`large`.

## Falsifiable prediction (sketch)

See frontmatter; sharpen at promotion — set the time-grid
resolution, neighbourhood operators, and compute budget then.

## Next steps

Promote after H-001; unblocks the Ch2 `medium`/`large` children.
