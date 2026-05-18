---
id: H-005
type: hypothesis
status: open
tags: [ch1, lns, milp, improvement]

parent: "[[H-004-ch1-matching-mip-lns]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: []
children_hypotheses: []
concurrent_with: []

created: 2026-05-18
tested_start: 2026-05-18T18:05:00+02:00
tested_end:
duration_testing:

effort_person_hours: 1.0
expected_points: 8           # conservative: aims to narrow/close the 1% gap on matching-i (+ matching-ii reuse)
estimated_effort_h: 4
priority: 1
mode: full

claim: >
  Cooperative MIP-LNS — workers share a global-best file and
  escalate destroy size adaptively when stuck — narrows or closes
  the ~1 % gap to Ch1 rank-3 that independent parallel MIP-LNS
  plateaued at.
falsifiable_prediction: >
  Cooperative+adaptive campaign (4 workers, shared best, escalating
  drop_frac, 1200 s) yields `matching-i` mass strictly above the
  independent plateau 33134 and ≥ 33467.83 (rank-3 cutoff,
  [[observations/O-002-leaderboard-2026-05-18|O-002]]). Conservative
  fallback success: ≥ 33345 (= leaderboard rank-5) if rank-3 is not
  reached. Refuted if it does not beat 33134 meaningfully.
modification_rationale: >
  [[takeaways/T-002-mip-lns-family-validated-but-plateaus|T-002]]:
  MIP-LNS reaches 99 % of rank-3 but independent parallel workers
  plateau in tight isolated basins (no info sharing, fixed destroy).
  H-004 was insufficient precisely there. This changes the search
  *dynamics* (not the family): a shared global-best so a worker that
  finds a better basin pulls the others in, plus escalating destroy
  to jump basins when stuck — directly targeting T-002's diagnosed
  cause, per [[user]] *parallelise / expect-hard*.

invalidated_by:
superseded_by:
invalidated_at:
backfilled_from:
---

# H-005 — Ch1 matching via cooperative + adaptive MIP-LNS

## Claim / prediction

See frontmatter. Conservative: the explicit success bar is "beat
the 33134 plateau"; rank-3 (33467.83) is the target, rank-5 (33345)
the documented fallback — the tight top-field cluster means the last
1 % may need an exact polish on top (noted as a body variant).

## Rationale / approach

`coop_mip_lns` / `parallel_coop_mip_lns` in
`src/esa_spoc_26/ch1_matching.py`: per-worker MIP-LNS + a shared
`pool_best` npy (atomic replace); every 20 rounds adopt the global
best; `drop_frac` escalates 0.10→0.65 on an 8-round stuck counter,
resets on improvement. Probe (95 s, 4 w) reached the plateau ~6×
faster than independent — speed validated; plateau-breaking is what
the 1200 s campaign tests.

## Experiments

- E-003 (matching-i cooperative campaign, 1200 s) — **running**
  (harness task `bv3i0fo4z`).

## Analysis (filled at close — §6)

## Next steps / siblings (§16)

- If rank-3 cleared: run `matching-ii` with the same operator;
  bank both; revisit frontier (H-002 trajectory next by ROI).
- If plateau persists: add an exact-polish phase (HiGHS on the
  residual free graph at convergence) or node-cluster destroy;
  these are body variants, escalate to a child H only if > 0.5 h.
