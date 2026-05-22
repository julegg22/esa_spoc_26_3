---
id: M-006
type: methodology
status: hard-rule
tags: [methodology, autonomous-loop, m-003, family-inventory]
created: 2026-05-22
source: "user pushback 2026-05-22: '(according to our methodology)'"
related: ["[[M-003-approach-family-inventory]]", "[[M-002-stuck-triggers-ultrathink-reframe]]"]
---

# M-006 — No idle while rank-3 targets are unmet

*Hard rule. Refinement of M-003 for autonomous-loop mode.*

## The rule

In autonomous-loop / `<<autonomous-loop-dynamic>>` mode, before
scheduling an "idle heartbeat" tick:

1. **Check banked state vs rank-3 targets** (latest
   `vault/observations/O-NNN-leaderboard-*.md`).
2. **For every unmet target**: ask "have I tried ≥ 2 ORTHOGONAL
   method families on it?"
3. **If no**: launch the next orthogonal family. Do NOT idle.
4. **Only idle when**: every unmet target has ≥ 2 orthogonal
   families with no remaining angles.

## Why this exists

S-2026-05-21 / S-2026-05-22 violation: after 3 consecutive
autonomous-loop ticks idle with Ch2 large (rank-3 = 2072.84 d)
unbanked, user prodded ("if you were idle before, why didnt you
start an orthogonal ultrathink exploration"). The greedy_findxfer
pipeline failure on Ch2 large was within **one family**
(perm-search heuristics). Family-inventory required pivoting to a
different family (hierarchical decomposition, bi-directional,
spectral clustering, coarse-MILP).

## What counts as "orthogonal"

A different problem-solving primitive, not a parameter sweep:

| same family | orthogonal family |
|---|---|
| greedy + 2-opt | hierarchical decomposition |
| greedy + Or-opt | bi-directional greedy |
| CMA-ES + warm-start | spectral clustering + meta-TSP |
| 2-opt + restart | RL pointer network |
| different starts of greedy | reverse-time greedy |
| different ILS kicks | coarse time-discretized MILP |

## What violates the rule

- Going idle when Ch3 is unattempted "because Ch3 is a new domain"
  (it's on the rank-3 path).
- Going idle when Ch2 large is unbanked "because greedy doesn't
  scale" (only ONE family tried).
- Going idle "to wait for user direction" on work the user has
  already authorized via standing directives ("never wait for
  choices, always continue").

## How to apply

Concrete autonomous-loop tick checklist:

```
1. Read latest leaderboard snapshot.
2. List unmet rank-3 targets.
3. For each target, list tried families (from session logs).
4. Pick the highest-ROI untried orthogonal family.
5. Launch it as a background task.
6. Schedule next loop tick to monitor.
```

If step 4 finds no untried family across all unmet targets, THEN
idle is appropriate.

## References

- M-003 (approach-family inventory).
- M-002 (stuck triggers ultrathink reframe).
- O-010 (the original Ch2-small ultrathink that revealed family
  inventory).
- `memory/idle-with-rank3-targets-unmet.md` (feedback memory of
  this rule).
