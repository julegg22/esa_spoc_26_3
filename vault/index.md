---
id: ROOT
type: root
created: 2026-04-24T00:00:00+02:00
goal: "Maximize total SpOC4 points (Σ (11−rank)×weight over the 6 mandatory instances) by 2026-06-30 AoE"
deadline: 2026-06-30

# Live campaign dashboard. Refresh leaderboard cutoffs via script from challenge Homepage.
---

# SpOC4 campaign — root

**Goal (revised 2026-06-11).** **Maximize total SpOC4 points** by
2026-06-30 AoE — *not* a top-3-on-every-instance gate. Points =
Σ over the 6 mandatory instances of **(11 − rank) × weight**, every
top-10 rank counts. See [[sessions/S-2026-06-12-points-strategy-and-loop-operating-model|S-2026-06-12]]
for the full reframe and the loop operating model.

**Scoring recap.** Challenges 1 and 2 are mandatory; each has
easy/medium/hard sub-instances with escalating point weights
(×1, ×4/3, ×(4/3)²≈1.778). Top 10 per instance score points. Challenge 3
is the tie-breaker. **Unsubmitted banks score ZERO — submission (still
user-gated) is now a first-class, time-sensitive decision.** See
`observations/` for the grounding notes.

**Submission discipline.** The agent never writes to the internet.
Solutions are produced as JSON artefacts under `solutions/upload/` and
the user uploads them manually via the Optimise web UI.

## Challenges

- Challenge 1 — Luna Tomato Logistics (mandatory) #ch1
- Challenge 2 — Keplerian Tomato TSP (mandatory) #ch2
- Challenge 3 — Luna Tomato Advertising (tie-breaker) #ch3

## Status — 2026-06-12

Banks (all valid in `solutions/upload/`, **all currently UNSUBMITTED =
0 pts**; ranks vs live board). Detail + the strategy reframe in
[[sessions/S-2026-06-12-points-strategy-and-loop-operating-model|S-2026-06-12]].

| Instance | Bank | Rank | Pts |
|---|---|---|---|
| Ch2 large (H) | 1048.98 d | 2 | 16.00 |
| Ch2 medium (M) | **192.90 d** | **1** | **13.33** |
| Ch1 trajectory (H) | 236,420 kg | 6 | 8.89 |
| Ch1 matching-ii (E ×1) | 72,204 | 7 | 4.00 |
| Ch2 small (E) | 116.37 d | 6 | 5.00 |
| Ch1 matching-i (E) | 33,338 | 9 | 2.00 |
| **TOTAL if submitted** | | | **≈49.2** |

_(ranks vs live board O-016 2026-06-12; medium banked to rank 1 via E-040 ultrafine re-time. matching-ii confirmed A_1 easy ×1 per O-001.)_

**Dominant action:** submit the 6 banks (user-gated) — ~46.55 pts that
read as 0 until uploaded. **Cheap-improver queue is empty** across all
instances; remaining levers are multi-hour new-code builds (now
authorized under full compute discretion). **In flight:** E-563 medium
epoch-aware cluster-decomposition build (transfers the large
2225→1049d method to medium), candidate-to-/tmp, guard-bank if feasibly
< 228.97d.

## Concepts banked this campaign

- [[concepts/C-017-subtour-bridge-insertion-large-clusters|C-017]]:
  sub-tour bridge insertion for k > 5 missing clusters.
- [[concepts/C-018-reserved-budget-construction|C-018]]: reserved-
  budget greedy (cap construction's resource use to preserve
  budget for repair).
- [[concepts/C-019-hierarchical-orbital-element-decomposition|C-019]]:
  hierarchical orbital-element decomposition for very-large TSP.
- [[concepts/C-020-bridge-prefilter|C-020]]: bridge-prefilter
  for fast LNS candidate evaluation.
- [[methodology/M-006-idle-pivot-on-unmet-targets|M-006]]: no
  idle in autonomous-loop while rank-3 targets are unmet (hard
  rule, refinement of M-003).
- [[methodology/M-general-deep-single-prompt-audit|M-general-deep-single-prompt-audit]]:
  one structured prompt to break a false "exhausted/ceiling" verdict —
  name the shared assumption, reconcile the gap to an exact number,
  find the skipped paradigm, propose 3 assumption-violating probes
  (Ch1-traj E-602, Ch2-small E-603, Ch2-large E-591).

## Campaign tree

*Update manually as hypotheses land — replace leaf nodes with concrete
`[[H-NNN-slug]]` wikilinks. For the live frontier, see
[[frontier.base]].*

## Entry points

- Frontier: [[open-paths]]
- Abbreviations: [[abbreviations]]
- User profile: [[user]]
- Sessions: `sessions/` (episodic narrative memory)
- Observations: `observations/`
- Hypotheses: `hypotheses/`
- Experiments: `experiments/`
- Takeaways: `takeaways/`
- Lessons (engineering): `lessons/`
- Concepts (prior knowledge): `concepts/`
- Methodology (research process, publication-bound): `methodology/`
- Package docs: `package/`
- Latest review: (none yet)

## Discipline

All work follows `../META.md`. Templates in `_templates/`.
