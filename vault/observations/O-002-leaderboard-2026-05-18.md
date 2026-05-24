---
id: O-002
type: observation
status: confirmed (numbers); reframed (gap interpretation)
tags: [baseline, ch1, ch2]
source: "read-only GraphQL query https://api.optimize.esa.int/graphql/ (problem.solutions{rank score user}) 2026-05-18, best-per-user reduction"
created: 2026-05-18
referenced_by: []
supersedes:
superseded_by:
---

> **⚠️ POST-2026-05-24 NOTE:** The leaderboard numbers here are correct,
> but our interpretation of "30000× gap on Ch1 trajectory" as
> structural / research-grade-needed was wrong. The gap was entirely
> due to a solve_arrival_dv bug rejecting eccentric Moon orbits. See
> [[LESSONS-LEARNED.md]].


# O-002 — Leaderboard snapshot 2026-05-18 (regular instances)

## Observation

Best-per-distinct-team standings (raw `solutions` lists carry many
per-team resubmissions all tagged with the same `rank`; reduced to
each team's best). **Ch1 negated** (more negative = more mass =
better). **Ch2 = makespan days** (smaller = better).

| problem | wt | #teams | R1 (team) | **R3 cutoff (team)** |
|---|---|---|---|---|
| Ch1 Matching I | ×1 | 8 | −33555.62 (Team HRI) | **−33467.83 (DIAG)** |
| Ch1 Matching II | ×1 | 8 | −73714.03 (fcmaes) | **−72101.13 (IBAM)** |
| Ch1 Trajectory Matching | ×(4/3)² | 5 | −473332.65 (TGMA) | **−452819.87 (Team HRI)** |
| Ch2 Small | ×1 | 5 | 101.65 (Team HRI) | **111.76 (fcmaes)** |
| Ch2 Medium | ×4/3 | 4 | 298.56 (TGMA) | **320.17 (Team HRI)** |
| Ch2 Large | ×(4/3)² | 4 | 1251.33 (TGMA) | **2072.84 (fcmaes)** |

Rank-3 target (= worst score still scoring rank-3): Ch1 mass-equiv
**MI ≥ 33467.83, MII ≥ 72101.13, TM ≥ 452819.87**; Ch2 makespan
**Small ≤ 111.76 d, Medium ≤ 320.17 d, Large ≤ 2072.84 d**.

## Competitor roster

- **fcmaes** — the open-source fcmaes lib author's entry (parallel
  BIPOP-CMA-ES / DE + massive retry). R1 Matching II, R2 Traj &
  Matching I. Submission names ("LTL Beginner Solver") imply a
  dedicated solver wrapped, not pure CMA-ES, for the matching.
- **TGMA** ("Marvin and Talha") — R1 Trajectory Matching, R1 Ch2
  Medium & **Large (1251 vs field ~1965+, ~36 % ahead)**. Has a
  structural edge on the hard astrodynamics/TSP.
- **ScholORs_HFUU+Sunway** (Hefei Univ. China + Sunway) — OR team,
  broad, strong Ch2 (R2 all three).
- **Team HRI** (Honda Research Institute Europe) — **separate HRI
  colleagues, NOT the user's `JJ & CC` alias** (user.md). R1
  Matching I, R1 Ch2 Small, R3 Trajectory ("Greedy solution") & Ch2
  Medium. Calibrator only — no intel sharing, independent stealth.
- DIAG (Sapienza), IBAM, JXUFE_CAI, Stellaris — mid-pack.

## Why it matters — realistic competitor methods (user directive)

1. **Small field.** 4–8 teams/instance (Ch2 Large/Medium = 4).
   Top-3-in-all-regular is realistic, not a bloodbath.
2. **Ch1 Matching clusters at a ceiling** (R1→R3 within 0.26 % on
   MI; MII R1 −73714 stands above a −72k pack). Tight top =
   competitors solving (near-)optimally. The instance is a
   set-packing / 3-D-assignment **ILP** → realistic method is a
   MIP solver or strong matching heuristic, *not* a metaheuristic.
   Confirms GOALS.md §5: **HiGHS MIP on Ch1 Matching = highest-ROI,
   exact, fastest-signal first move.** A true optimum lands at/above
   R1. Risk: `matching-ii` = 92 103 binary vars — must confirm
   HiGHS solves it (set-packing LP relaxation is usually tight).
3. **Trajectory Matching: a *greedy* reached R3** (Team HRI "Greedy
   solution" −452819). Realistic path: compute BCP ≤3-impulse
   Earth→Moon transfer masses, then solve the 3-D assignment on
   computed weights (greedy/ILP). Hard part = per-pair BCP
   trajectory optimisation (user's physics strength). R3 reachable
   without exotic methods; R1 (TGMA −473k) needs better transfers.
4. **Ch2 = time-dependent ATSP** (Lambert cost, ΔV cap + E
   exception legs, makespan). Top teams = strong metaheuristics
   over a precomputed feasible time-grid (LNS / GA / beam + Lambert
   refine). TGMA's Large outlier ⇒ a structural insight (likely
   exploiting clustered orbits + waiting to cut ΔV). R3 on Large is
   soft (4 teams, R3=R4 essentially tied at ~2072.84).

This snapshot is the falsifiability anchor for every active H until
re-fetched (GOALS.md §1, §4). Refresh via read-only GraphQL.
