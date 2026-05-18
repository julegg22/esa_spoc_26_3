---
id: H-004
type: hypothesis
status: open
tags: [ch1, milp, lns, improvement]

parent: "[[H-001-ch1-matching-mip]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: []
children_hypotheses: []
concurrent_with: []

created: 2026-05-18
tested_start: 2026-05-18T17:40:00+02:00
tested_end:
duration_testing:

effort_person_hours: 1.5
expected_points: 10          # conservative: rank-3 matching-i likely, matching-ii upside (both A_1 ×1)
estimated_effort_h: 6
priority: 1
mode: full

claim: >
  MIP-based LNS (drop a random subset of selected transfers, then
  re-optimise the freed region EXACTLY with HiGHS, parallel
  multi-seed) escapes the greedy local optimum that defeated H-001
  and reaches the Ch1 matching rank-3 cutoff.
falsifiable_prediction: >
  Parallel MIP-LNS (4 workers, varied drop_frac) yields delivered
  mass ≥ 33467.83 on `matching-i` within a 600 s campaign, and a
  comparable campaign clears ≥ 72101.13 on `matching-ii`
  (rank-3 cutoffs, [[observations/O-002-leaderboard-2026-05-18|O-002]]).
  Conservative basis, not assumption: a 70 s single-thread probe
  already reached 32958 = 98.5 % of `matching-i` rank-3 (E-001
  follow-up). Refuted if the campaign plateaus below the cutoff.
modification_rationale: >
  Prior ([[hypotheses/H-001-ch1-matching-mip|H-001]]) showed cheap
  exact/greedy/LNS plateau ~11–13 % below rank-3 because greedy is a
  provable hard local optimum and the global LP relaxation is weak
  ([[takeaways/T-001-ch1-matching-needs-strong-search|T-001]]).
  H-001 was insufficient: its neighbourhoods cannot escape that
  optimum. This changes the operator to **exact sub-instance
  re-optimisation over a destroyed region** (small sub-ILPs ARE
  tractable though the full one is not) with parallel seeds —
  directly attacking T-001's "needs strong parallel search" finding
  and the user's parallelise/expect-hard directive ([[user]]).

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-004 — Ch1 matching via parallel MIP-based LNS

## Claim

See frontmatter. Destroy-and-exactly-repair turns the intractable
full 3-D matching ILP into a sequence of tractable sub-ILPs whose
union climbs past the greedy optimum.

## Falsifiable prediction

Conservative, evidence-anchored (probe: 29792 → 32958 in 70 s,
1 thread). Target = the live rank-3 cutoffs; refuted on plateau
below them.

## Rationale / approach

`mip_lns()` / `parallel_mip_lns()` in `src/esa_spoc_26/ch1_matching.py`.
Each round: drop `drop_frac` of selected transfers → free their
nodes → exact HiGHS max-weight matching on the now-free subgraph →
reinsert. Monotone per round (kept-minus-dropped is feasible).
4 parallel workers, varied `drop_frac ∈ {0.15,0.2,0.25,0.3}`, best
wins. L-001 observability fix applied (solver log to file).

## Experiments

- E-002 (matching-i + matching-ii parallel campaigns) — running.

## Analysis (filled at close — §6)

## Next steps / siblings (§16)

- Draft siblings (deferred until H-004 closes): C-B parallel
  metaheuristic (SA/Tabu + long ejection chains),
  [[hypotheses/H-002-ch1-trajectory-greedy|H-002]],
  [[hypotheses/H-003-ch2-small-lambert-metaheuristic|H-003]].
- Focus over diversify chosen: H-004 is at 98.5 % of rank-3 — finish
  the near-win before context-switching (conservative, user breadth Q).
