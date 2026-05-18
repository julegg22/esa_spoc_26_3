---
id: O-001
type: observation
status: confirmed
tags: [baseline, ch1, ch2, ch3]
source: "reference/SpOC4/ (README.md + per-challenge README.md, commit-pinned shallow clone) + api.optimize.esa.int/graphql introspection 2026-05-18"
created: 2026-05-18
referenced_by: []
supersedes:
superseded_by:
---

# O-001 — SpOC4 problem grounding (Ch1/Ch2/Ch3)

## Observation

**Competition shape.** Two mandatory challenges (Ch1 Luna Tomato
Logistics, Ch2 Keplerian Tomato TSP); global score = Ch1 local +
Ch2 local. Ties broken by Ch3 (Luna Tomato Advertising, tie-breaker).
Per-problem leaderboard: top-10 get points; easy ×1 (10..1),
medium ×4/3, hard ×(4/3)². Deadline 30 Jun 2026 EoD AoE; portal
stays open after but late entries don't count.

**Actual instances (GraphQL `challenge.problems`, ids are submission
`<problem>`):**

| challenge | problem id | name | difficulty | decisionDim | notes |
|---|---|---|---|---|---|
| spoc-4-luna-tomato-logistics | `matching-i` | Matching I | A_1 (easy ×1) | 25000 | binary vector len \|T\| |
| spoc-4-luna-tomato-logistics | `matching-ii` | Matching II | A_1 (easy ×1) | 92103 | binary vector len \|T\| |
| spoc-4-luna-tomato-logistics | `trajectory-matching` | Trajectory Matching | A_3 (hard ×(4/3)²) | 8400 | 400×21, BCP trajectories |
| spoc-4-keplerian-tomato-traveling-salesperson | `small` | Small | A_1 (easy ×1) | 145 | N=49 tomatoes (3N−2) |
| spoc-4-keplerian-tomato-traveling-salesperson | `medium` | Medium | A_2 (med ×4/3) | 541 | N=181 |
| spoc-4-keplerian-tomato-traveling-salesperson | `large` | Large | A_3 (hard ×(4/3)²) | 3151 | N=1051 |
| spoc-4-luna-tomato-advertising | `tie-breaker` | Tie-breaker | A_0 | 4674 | Ch3, deferred |

(GOALS.md §2's "1.beginner.easy/medium / 1.advanced" and
"2.easy/medium/hard" labels are superseded by these real ids.)

### Ch1 — Luna Tomato Logistics

- **Matching I/II (beginner, A_1).** Weighted 3-dimensional
  matching: transfers `(e,l,d)` with mass weight `w`; pick
  `S⊆T` so no `e`, `l`, or `d` repeats; **maximize Σw**. Solution
  = binary array length |T|. Invalid → score 0. Score is **negated**
  on the board (PyGMO minimization): more negative = better.
  → an exact binary set-packing / 3-D assignment ILP.
- **Trajectory Matching (advanced, A_3).** Compute impulsive
  (≤3-impulse) Earth-orbit→Moon-orbit transfers in the **BCP**
  (Simó 1995; Earth+Moon+Sun), mass via Tsiolkovsky
  (m_w=5000, m_dry=500, Isp=311, g0=9.80665), delivered mass
  `m_d=min(m_l,(200−ΔT)·c_ld)` within 200 days. Decision vector
  400×21 = `[e,l,d,t0,r0(3),v0(3),DV0(3),DV1(3),DV2(3),T1,T2]`;
  unused entry → `e_id=−1`. Validation tol 1e-6 on (a,e,i),
  non-dim semi-major axis. Negated on board.

### Ch2 — Keplerian Tomato TSP

Time-dependent ATSP: visit all N tomato orbits (Keplerian about
Moon); per-leg cost = Lambert ΔV depending on departure time AND
tof; per-leg ΔV ≤ ΔV_max with up to E "exception" legs ≤
ΔV_max^exc; min tof, max total time, waiting allowed.
Chromosome `x=[t_1..t_{N-1}, tof_1..tof_{N-1}, π_1..π_N]`,
len 3N−2, π a permutation. **Objective = makespan
`f=t_{N-1}+tof_{N-1}` (minimize, days)**, positive on board.
Provided: `TomatoProblem` class + `compute_transfer(i_from,i_to,
t_start,tof)` Lambert (needs **pykep 2.x**, not 3.x).

### Ch3 — Luna Tomato Advertising (tie-breaker, deferred)

Morse-code occultation reconstruction; minimize #spacecraft s.t.
MSE ≤ 0.05. `celestial_morse_code` UDP. Out of scope until Ch1/Ch2
rank-3 secured (user directive 2026-05-18).

### Submission format (agent never submits — GOALS.md §4)

```json
[ { "decisionVector": [ ... ], "problem": "<problem id>",
    "challenge": "<challenge slug>" } ]
```
Artefact → `solutions/upload/<problem>.json`; user uploads manually
via https://optimize.esa.int/submit.

## Source

`reference/SpOC4` shallow clone (gitignored) + read-only GraphQL
introspection/queries against `https://api.optimize.esa.int/graphql/`
on 2026-05-18.

## Why it matters

Grounds every Ch1/Ch2 hypothesis. Ch1 beginner is an exact-solvable
ILP (HiGHS, GOALS.md §5); Ch1 advanced + all Ch2 are
astrodynamics-coupled. Instance ids here are the submission
`<problem>` strings. Leaderboard standings + cutoffs:
[[O-002-leaderboard-2026-05-18]].
