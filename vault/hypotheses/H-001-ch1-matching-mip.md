---
id: H-001
type: hypothesis
status: open
tags: [ch1, baseline, milp, optimization]

parent: "[[Q-001-rank3-each-regular-instance]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: []
children_hypotheses: []
concurrent_with: ["[[H-002-ch1-trajectory-greedy]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]

created: 2026-05-18
tested_start:
tested_end:
duration_testing:

effort_person_hours:
expected_points: 16          # rank-3 on both A_1 ×1 (8+8); upside 20 at rank-1
estimated_effort_h: 2
priority: 1
mode: full                   # >2 pts AND cross-instance method learning

claim: >
  Ch1 `matching-i` (|T|=25000, |E|=|L|=|D|=5000) and `matching-ii`
  (|T|=92103, |E|=|L|=|D|=10000) are weighted 3-dimensional
  matching / set-packing ILPs that HiGHS solves to optimality (or
  within the rank-3 gap) in minutes.
falsifiable_prediction: >
  A binary ILP — maximize Σ wᵢxᵢ s.t. for every e/l/d the incident
  xᵢ sum ≤ 1 — solved with HiGHS MIP yields delivered mass
  ≥ 33467.83 on `matching-i` AND ≥ 72101.13 on `matching-ii`
  (= rank-3 cutoffs, [[observations/O-002-leaderboard-2026-05-18|O-002]]
  2026-05-18), each within 30 min wall, with the HiGHS optimality
  gap recorded. Refuted if either instance fails the cutoff or
  HiGHS does not return a usable incumbent in budget.
modification_rationale:      # null — rooted directly on Q-001 (META.md §7)

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-001 — Ch1 matching-i / matching-ii via HiGHS MIP

## Claim

The Ch1 beginner instances are exact combinatorial problems, not
metaheuristic targets. Weighted 3-D matching with one-use-per-node
constraints is a binary ILP HiGHS can close at these sizes.

## Falsifiable prediction

See frontmatter. Anchored to the 2026-05-18 rank-3 cutoffs in
[[observations/O-002-leaderboard-2026-05-18|O-002]]. The top-cluster
tightness (R1→R3 within 0.26 % on `matching-i`) indicates competitors
are already (near-)optimal — an exact solve should land at or above
rank-1.

## Rationale / approach

`maximize Σ w_i x_i`, `x ∈ {0,1}^|T|`, subject to packing
constraints `Σ_{i: e_i=e} x_i ≤ 1 ∀e`, likewise ∀l, ∀d. 25 000 vars
/ 15 000 constraints and 92 103 / 30 000 — well within HiGHS MIP.
Use `highspy` (validated in `spoc26`, [[O-001-spoc4-problem-grounding|O-001]]).
Emit `solutions/upload/matching-i.json` / `matching-ii.json`
(binary `decisionVector`, `problem`, `challenge`) — agent does not
submit (GOALS.md §4); user uploads.

## Experiments

- [[E-001-ch1-matching-mip-highs]] — HiGHS MIP on both instances.

## Analysis (filled at close — §6)

## Next steps / siblings (§16)

- Drafts on the same fork: [[H-002-ch1-trajectory-greedy]],
  [[H-003-ch2-small-lambert-metaheuristic]].
- < 0.5 h variants (in the chosen sibling's body, not separate H):
  LP-relaxation-then-round fallback if MIP times out; symmetry/
  presolve tuning; warm-start from a greedy matching.
