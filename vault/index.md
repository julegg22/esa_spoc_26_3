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

## Status — 2026-05-24

Ch1 trajectory breakthrough today: solve_arrival_dv eccentric-orbit
bug found and fixed (see [[lessons/L-012-solver-assumption-audit-before-research-grade-verdict|L-012]],
[[sessions/S-2026-05-24-eccentric-orbit-breakthrough|S-2026-05-24]],
top-level `LESSONS-LEARNED.md`). Per-pair masses jumped 50-100× —
(0,0) coplanar: 14.82 → 819 kg; GEO+eL=0.65: FAIL → 2037 kg.
Production sweep with eccentric-aware solver pending (current
implementation too slow at 15× original solver time; needs trimming).

**Realized (banked, valid artifacts in `solutions/upload/`):**
Ch1 `matching-i` ≈ rank-6 (~5 pts), `matching-ii` ≈ rank-5 (~6 pts)
→ **≈ 11 pts**. Ch1-matching line closed at the HiGHS ceiling
([[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]]). Ch1
trajectory bank still at 14.82 kg pending sweep result. **Ch2 small
banked at 142.92 d (vs R3 cutoff 111.76, ratio 1.279); Ch2 medium
banked at 274.52 d — projects R1 on the 2026-05-18 leaderboard
(R1=298.56, 8% lead)**. Ch2 large attempted via hierarchical
decomposition (C-019); Ch3 banked at 50 spacecraft (MSE=0.04982).

**Ch1 trajectory path forward**: optimize eccentric-arrival solver
speed (trim seeds 8→2, max_nfev 50→20), run production sweep on top
2000 Hohmann-theoretical pairs, Hungarian-assign 400, bank. Expected
mass: 200,000-500,000 kg (rank 3-5 territory).

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
