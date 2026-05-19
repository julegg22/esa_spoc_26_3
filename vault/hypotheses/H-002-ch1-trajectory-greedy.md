---
id: H-002
type: hypothesis
status: open
tags: [ch1, astrodynamics, bcp, improvement]

parent: "[[Q-001-rank3-each-regular-instance]]"
question: "[[Q-001-rank3-each-regular-instance]]"
children_experiments: ["[[E-006-h002-first-direct-transfer-attempt]]"]
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
modification_rationale: >
  Promoted draft→open 2026-05-18 by the pivot decision in
  [[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]]: the Ch1
  *matching* line hit a HiGHS ceiling ~0.4 % short of rank-3 with no
  commercial solver. Trajectory-matching is higher-leverage —
  ×(4/3)² weight and rank-3 *demonstrably reachable by a greedy*
  (Team HRI's R3 sub, O-002). Rooted on Q-001; this field records
  why it became the active branch now.

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

## Progress (open, 2026-05-19)

Foundation on the **official-mirror oracle** (corrected after the
[[lessons/L-002-udp-served-via-graphql-not-git|L-002]] catch).
Verified pieces: Step 1 exact Earth/Moon orbit state generators;
Step 2 arrival-ΔV / LOI solver (`solve_arrival_dv`). Step 3 (direct
2-impulse shooter) first attempt **missed** — lunar closest-approach
~11 000 km vs the tight LOI band
([[experiments/E-006-h002-first-direct-transfer-attempt|E-006]]).

## Next steps

- Implement a proper **cislunar differential corrector**:
  multi-variable shooting (DV0 vector + TOF + departure phase + t0)
  targeting `|r_moon| = aL`; stronger seed (CR3BP transfer / pykep
  Lambert-arc / manifold) than patched-conic.
- On a valid single transfer: sweep (e,l) pairs → discounted-mass
  matrix → reuse the `ch1_matching` MIP-LNS for the 3-D assignment →
  emit `solutions/upload/trajectory-matching.json`; validate vs the
  rank-3 cutoff 452 819.87.
