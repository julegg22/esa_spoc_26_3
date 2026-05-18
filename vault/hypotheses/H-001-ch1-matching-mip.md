---
id: H-001
type: hypothesis
status: refuted
tags: [ch1, baseline, milp, optimization]

parent: "[[Q-001-rank3-each-regular-instance]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: ["[[E-001-ch1-matching-first-attempts]]"]
children_hypotheses: []
concurrent_with: ["[[H-002-ch1-trajectory-greedy]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]

created: 2026-05-18
tested_start: 2026-05-18T16:18:00+02:00
tested_end: 2026-05-18T17:05:00+02:00
duration_testing: ~47m

effort_person_hours: 1.8
expected_points: 16          # PREDICTED; realized 0 — refuted, recalibrate (T-001)
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

**Refuted by [[experiments/E-001-ch1-matching-first-attempts|E-001]].**
Default HiGHS MIP plateaued at 79 % of the `matching-i` rank-3 cutoff
(122 % gap, weak LP relaxation); weight-greedy reaches 89 %
(`matching-i`) / 88 % (`matching-ii`) but is a *provable* hard local
optimum, and greedy-seeded LNS/ejection made zero improvement
([[lessons/L-001-greedy-localopt-and-suppressed-solver-log|L-001]]).
No method within the predicted budget cleared rank-3. The claim that
this is a "solve-in-minutes" ILP is false at default settings.
Distilled: [[takeaways/T-001-ch1-matching-needs-strong-search|T-001]].
The refutation is scoped to *cheap/default* methods — a strong
tuned/long exact solver or parallel strong-search metaheuristic is
untested and lives in the child hypotheses.

## Next steps / siblings (§16)

Closure fork (priced **conservatively** per [[user]] *Conservative
expectations* — challenges hard, many local minima; **parallel by
construction**). Candidate children, to commit after the user
chooses (discuss-before-commit, META.md §6):

- **C-A — parallel MIP-based LNS**: destroy a node region, solve the
  sub-instance exactly with HiGHS, repeat; parallel workers/regions.
  est ~6 h, expected ~6 (rank-5→3 reach, not assumed).
- **C-B — parallel multi-start metaheuristic**: SA/Tabu with long
  ejection chains, many parallel seeds (pygmo archipelago / mp).
  est ~6 h, expected ~5.
- **C-C — long tuned warm-started exact**: greedy warm start +
  HiGHS heuristics/cuts/threads, long wall; Gurobi if licensed.
  est ~3 h, expected ~5 (uncertain — LP bound weak).
- Pre-existing draft siblings unaffected: [[H-002-ch1-trajectory-greedy]],
  [[H-003-ch2-small-lambert-metaheuristic]].
