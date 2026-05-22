---
id: ROOT
type: root
created: 2026-04-24T00:00:00+02:00
goal: "Achieve top-3 aggregate standing on SpOC4 by 2026-06-30 AoE"
deadline: 2026-06-30

# Live campaign dashboard. Refresh leaderboard cutoffs via script from challenge Homepage.
---

# SpOC4 campaign — root

**Goal.** Achieve top-3 aggregate standing on SpOC4 by 2026-06-30 AoE.

**Scoring recap.** Challenges 1 and 2 are mandatory; each has
easy/medium/hard sub-instances with escalating point weights
(×1, ×4/3, ×(4/3)²). Top 10 per instance score points. Challenge 3 is
the tie-breaker. See `observations/` for the grounding notes.

**Submission discipline.** The agent never writes to the internet.
Solutions are produced as JSON artefacts under `solutions/upload/` and
the user uploads them manually via the Optimise web UI.

## Challenges

- Challenge 1 — Luna Tomato Logistics (mandatory) #ch1
- Challenge 2 — Keplerian Tomato TSP (mandatory) #ch2
- Challenge 3 — Luna Tomato Advertising (tie-breaker) #ch3

## Status — 2026-05-18

Fresh-start scaffold rebuilt (commit `42820c5`). Grounding done:
[[observations/O-001-spoc4-problem-grounding|O-001]] (problems),
[[observations/O-002-leaderboard-2026-05-18|O-002]] (rank-3 cutoffs +
competitor analysis). Goal = rank-3 on each regular instance (GOALS.md
§1). See [[open-paths]] for the live frontier.

**Realized (banked, valid artifacts in `solutions/upload/`):**
Ch1 `matching-i` ≈ rank-6 (~5 pts), `matching-ii` ≈ rank-5 (~6 pts)
→ **≈ 11 pts**. Ch1-matching line closed at the HiGHS ceiling
([[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]]); active
branch pivoted to [[hypotheses/H-002-ch1-trajectory-greedy|H-002]]
(Ch1 trajectory). **Ch2 small banked at 142.92 d (vs R3 cutoff
111.76, ratio 1.279); Ch2 medium banked at 274.52 d — projects R1
on the 2026-05-18 leaderboard (R1=298.56, 8% lead)**. Ch2 large
attempted via hierarchical decomposition (C-019); Ch3 not yet
started.

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
