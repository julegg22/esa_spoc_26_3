---
id: H-006
type: hypothesis
status: refuted
tags: [ch1, lns, milp, improvement]

parent: "[[H-005-ch1-matching-coop-mip-lns]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: ["[[E-004-ch1-matching-i-exact-polish]]"]
children_hypotheses: []
concurrent_with: []

created: 2026-05-18
tested_start: 2026-05-18T18:30:00+02:00
tested_end: 2026-05-18T18:55:00+02:00
duration_testing: ~25m

effort_person_hours: 0.9
expected_points: 8           # conservative: close the last 0.44% on matching-i; rank-3 = ~8 (A_1 ×1)
estimated_effort_h: 3
priority: 1
mode: full

claim: >
  Warm-starting the strong cooperative incumbent (33 320) into
  *large* exact sub-MIPs (time_per_sub 25 s, escalated destroy)
  closes the last 0.44 % to Ch1 `matching-i` rank-3.
falsifiable_prediction: >
  Polish campaign (4 workers, warm-start 33 320, time_per_sub 25 s,
  1500 s) yields `matching-i` mass ≥ 33 467.83 (rank-3,
  [[observations/O-002-leaderboard-2026-05-18|O-002]]). Conservative
  fallback success: ≥ 33 345 (rank-5). Refuted if it does not exceed
  the 33 320 cooperative plateau.
modification_rationale: >
  [[takeaways/T-003-diminishing-returns-need-exact-polish|T-003]]:
  metaheuristic mechanism upgrades show explicit diminishing returns
  (89 % → 99.0 % → 99.56 %); the last 0.44 % is an exact-search
  regime. H-005 was insufficient because small random sub-MIPs from
  a greedy seed can't reach the near-optimal basin. This changes the
  operator to *large exact sub-MIPs from the strong incumbent* —
  more solver, less heuristic — directly per T-003's diagnosis.

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-006 — Ch1 matching exact-polish (large warm-started sub-MIPs)

## Claim / prediction

See frontmatter. Conservative bar = beat 33 320; target rank-3;
rank-5 documented fallback. If this also plateaus, rank-3 on
`matching-i` likely needs a **commercial solver (Gurobi)** —
escalated to the user (licence availability decisive, not in vault).

## Approach

`parallel_coop_mip_lns(..., warm_artifact=matching-i.json,
time_per_sub=25)`: workers start from the 33 320 incumbent and
re-solve large freed regions exactly with a 25 s HiGHS budget each,
escalating destroy when stuck. Campaign running (harness task
`baqz41aa1`, 1500 s) = E-004.

## Experiments

- E-004 (matching-i exact-polish, 1500 s) — **running**.

## Analysis (filled at close — §6)

**Refuted by [[experiments/E-004-ch1-matching-i-exact-polish|E-004]].**
Warm-started large sub-MIPs added only +18 (33 320 → 33 338) over
1500 s — terminal flattening of the HiGHS family at ~33 340
(99.6 % of rank-3), below even rank-5. No commercial solver
available (user). This **closes the Ch1-matching exact line**: per
[[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]] the stop-rule
fires (clean halving asymptote ≥2 generations short → pivot, don't
tune). matching-i banked ≈ rank-6; `matching-ii` campaign running;
frontier pivots to [[hypotheses/H-002-ch1-trajectory-greedy|H-002]]
(no child H on the matching line — line abandoned by decision).

## Next steps / siblings (§16)

- If rank-3 cleared: replicate on `matching-ii`; bank both; pivot
  frontier to [[hypotheses/H-002-ch1-trajectory-greedy|H-002]].
- If plateau persists AND Gurobi available: exact full/large-MIP
  with Gurobi. If no Gurobi: accept ~rank-6 on `matching-i`,
  **pivot** to higher-ROI H-002 (Ch1 trajectory, Team-HRI-proved
  rank-3 by greedy) per conservative ROI discipline.
