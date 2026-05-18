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
§1). **Frontier bootstrap pending** — see [[open-paths]]. No `H-NNN`
committed yet (discuss-before-commit, META.md §6). Realized points: 0.

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
