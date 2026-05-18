---
id: Q-001
type: question
status: open
tags: [ch1, ch2, framing]
parent: ROOT
created: 2026-05-18
candidate_hypotheses: ["[[H-001-ch1-matching-mip]]", "[[H-002-ch1-trajectory-greedy]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]
answered_by:
---

# Q-001 — How do we reach rank-3 on each regular SpOC4 instance?

## The ambiguity

The root goal (GOALS.md §1) is rank-3 on each of the six regular
instances. Each instance has a different structure and a different
realistic winning method ([[observations/O-002-leaderboard-2026-05-18|O-002]]).
The question this branches: *per instance, what method most cheaply
clears the rank-3 cutoff?*

## Why it matters to the goal

This is the campaign's root branching point. Selecting the
highest-ROI method per instance (META.md §5) and ordering by
time-to-first-signal determines whether we bank points early.

## Candidate hypotheses

- **[[H-001-ch1-matching-mip]]** — Ch1 `matching-i`/`matching-ii`
  is an exact ILP; HiGHS MIP clears rank-3 (likely rank-1). *Chosen
  first (open) — highest ROI, fastest signal, exact.*
- **[[H-002-ch1-trajectory-greedy]]** — Ch1 `trajectory-matching`:
  compute BCP transfers + greedy 3-D assignment (Team HRI proved
  greedy → R3). *Draft sibling.*
- **[[H-003-ch2-small-lambert-metaheuristic]]** — Ch2 `small`:
  Lambert-precompute + LNS/GA over order & timing. *Draft sibling.*
- *(later)* Ch2 `medium`/`large`; Ch1 trajectory rank-1 push.
