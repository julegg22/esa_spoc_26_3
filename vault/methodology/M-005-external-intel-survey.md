---
id: M-005
type: methodology
status: active
tags: [methodology, intel, community-signals]
created: 2026-05-20
related: ["[[M-003-approach-family-inventory]]", "[[M-004-convergence-watchdog-across-families]]", "[[L-005-toolchain-audit-at-task-bootstrap]]"]
---

# M-005 — External intel survey at task bootstrap (and watchdog re-fires)

*Trigger*: We grounded on `O-001-spoc4-problem-grounding` and
`O-002-leaderboard-2026-05-18` but stopped at "what's the score
distribution?". We never asked "which teams use which tools? what
do they win with? what's their pattern?". The fcmaes signal was
*publicly visible* through Wolz's GTOC tutorials, the leaderboard
helper name, and the env install — all surfaced *after* the user
caught it by accident.

## Rule

At task bootstrap (and at every M-004 trigger), run an external
intel survey:

1. **Leaderboard teams**: get team names. Search each on GitHub,
   personal sites, ESA ACT publications.
2. **Past winners of similar competitions** (GTOC, SpOC, COCO,
   BBOB-style continuous benchmarks): what toolchains?
3. **Problem-class taxonomy**: what generic name fits this
   problem? ("time-dependent ATSP with Lambert costs"; "orbital
   tour scheduling"). Search the term + GitHub + papers.
4. **Library ecosystem**: list 3–5 actively-maintained libraries
   for this problem class. For each, find a tutorial.
5. **Author/maintainer ecosystem**: who *writes* in this area?
   Their stack is informative (e.g., Wolz → fcmaes; Izzo → pygmo).

## How this is bounded

Time-box: 30–60 minutes at bootstrap; 15 minutes per M-004
re-trigger. Always finite; the goal is *signals*, not exhaustive
literature review.

## Output

A single observation node `O-X-<challenge>-external-intel` with:

- **Pinned signals**: 3–5 strong pointers (libraries, repos, papers)
- **Ranked tools**: top 3 plausible tools for the problem class
- **Cross-validation**: which signals agree?
- **Confidence**: high/medium/low for each pointer

## Companion artefacts

- L-005 (toolchain audit): the *local* version of this
- M-003 (family inventory): receives the ranked tools as priors
- M-004 (watchdog): re-runs this on convergence trigger

## Example: how it would have caught fcmaes (Ch2)

1. Leaderboard team names → some teams have GitHub repos with
   solver code.
2. Search `ESA ACT SpOC winner` → Wolz appears repeatedly.
3. Wolz's GitHub → `fast-cma-es` (fcmaes) repo.
4. Search `fcmaes orbital TSP` → tutorials directly applicable.
5. Cross-validation: leaderboard helper name, env install,
   community.

Cost: ~30 minutes. Would have shaved ~25h of dead-end local search.
