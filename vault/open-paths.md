---
id: OPEN-PATHS
type: frontier
updated: 2026-05-18
tags: [frontier]
---

# Frontier — the single list of "what we could do next"

> [!important] Single frontier (META.md §2)
> This is the **only** list of candidate next moves. Ideas living in
> chat do not exist. Selection policy: pick the open H maximizing
> `ROI = expected_points / max(estimated_effort_h, 0.25)`; tie-break
> on time-to-first-signal, then diversity, then unblocking (META.md §5).
> Reprice after every experiment and log the re-pricing below.

## Live view

![[frontier.base]]

## Selection (2026-05-18)

Bootstrapped under [[questions/Q-001-rank3-each-regular-instance|Q-001]].
ROI = expected_points / max(estimated_effort_h, 0.25).

### Open (status: open) — at most one active per compute stream (§2)

*(none — H-001 closed refuted; awaiting user choice of child, discuss-before-commit)*

### Closed

| H | verdict | result |
|---|---|---|
| [[hypotheses/H-001-ch1-matching-mip\|H-001]] | **refuted** | cheap MIP/greedy/LNS ~11–13 % short of Ch1 rank-3 ([[takeaways/T-001-ch1-matching-needs-strong-search\|T-001]], [[experiments/E-001-ch1-matching-first-attempts\|E-001]]) |

### Drafts (priced siblings, §16) — conservative repricing (T-001)

| H | instance | expected | est. h | ROI | note |
|---|---|---|---|---|---|
| H-001 child C-A | Ch1 matching | 6 | 6 | 1.0 | **parallel MIP-based LNS** (destroy → exact sub-solve) |
| H-001 child C-B | Ch1 matching | 5 | 6 | 0.8 | parallel multi-start SA/Tabu + long ejection chains |
| H-001 child C-C | Ch1 matching | 5 | 3 | 1.7 | long tuned warm-started exact (± Gurobi) |
| [[hypotheses/H-002-ch1-trajectory-greedy\|H-002]] | Ch1 trajectory-matching | 14 | 12 | 1.2 | greedy on BCP transfers (Team HRI proved R3) |
| [[hypotheses/H-003-ch2-small-lambert-metaheuristic\|H-003]] | Ch2 small | 8 | 8 | 1.0 | Lambert precompute + LNS/GA |

*Children C-A/C-B/C-C are candidates (not yet H-files) — committed
after the user picks (META.md §6). Expectations cut per [[user]]
*Conservative expectations*.*

## Narrative log — the frontier has history (§5)

- **2026-05-18 (H-001 closed: refuted)** — E-001: default HiGHS
  (79 % R3, 122 % gap), greedy (89 %/88 %), naive+ejection LNS
  (0 improvement — greedy is a provable hard local optimum,
  [[lessons/L-001-greedy-localopt-and-suppressed-solver-log|L-001]]).
  Cheap methods do not clear Ch1 rank-3. User directive: parallelise,
  expect hard, be conservative (→ [[user]], [[takeaways/T-001-ch1-matching-needs-strong-search|T-001]]).
  Valid greedy baselines banked (`solutions/upload/`). Frontier
  repriced down. **Strategic fork to user**: child C-A/C-B/C-C
  (parallel MIP-LNS / parallel metaheuristic / long tuned exact) —
  none committed pending user choice (discuss-before-commit).
- **2026-05-18 (kickoff)** — Grounding committed
  ([[observations/O-001-spoc4-problem-grounding|O-001]],
  [[observations/O-002-leaderboard-2026-05-18|O-002]]). GOALS.md §1
  reframed to per-instance rank-3 (user directive). Frontier
  bootstrapped under [[questions/Q-001-rank3-each-regular-instance|Q-001]]:
  **H-001 (Ch1 matching MIP) promoted to open** — ROI 8.0, exact,
  fastest signal, "establish baseline early" (META.md §2).
  H-002 (Ch1 trajectory greedy) + H-003 (Ch2 small) committed as
  priced draft siblings (§16). Next: run E-001 (HiGHS MIP).
- **2026-05-18** — Repo instance `esa_spoc_26_3`. Methodology
  scaffold (`CLAUDE.md`/`GOALS.md`/`META.md`) and tier-1 docs were
  inherited from a prior mature campaign whose vault nodes
  (H/E/T/C/M/L/O, templates, scripts, frontier) were absent. User
  directed a **fresh-start scaffold rebuild**: created `_templates/`
  (10 node templates), node directories, `open-paths.md`,
  `frontier.base`, `scripts/`, `solutions/upload/`, draft
  `environment.yml`. Frontier is empty; next step is the
  bootstrap discussion (no `H-NNN` committed without it).
