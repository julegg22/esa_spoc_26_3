---
date: 2026-06-07
tags: [observation, leaderboard, competition-intel, hri, tgma, methodology]
status: confirmed via api.optimize.esa.int GraphQL
---
# O-013 — Competition intel: team identities + own-submission recovery problem

## Team identities (all 8 leaderboard users decoded)

| User ID | Team | Affiliation | Notable rank |
|---|---|---|---|
| db54c27... | **Team HRI** | Honda Research Institute Europe | rank 1 small (101.65, 2026-04-25) — **THIS IS US** |
| 5af55cab... | **TGMA** (Marvin & Talha) | Germany | rank 1 medium (199.74) + rank 1 large (424.62) — both 2026-06-05 |
| dd46ba62... | ScholORs_HFUU+Sunway | Hefei + Sunway U | rank 2 small (108.77) |
| 867404f7... | **fcmaes** (dietmarwo) | Germany | rank 3 small (110.88); author of fast-cma-es library we use |
| f5a760fd... | AC_TUWien | TU Wien, Austria | rank 4 small (111.79), active improver |
| be625c47... | Paulina Heine | U Vienna | rank 6 small |
| 05b3d535... | (no team info) | — | — |
| cd77dc25... | (no team info) | — | — |

## The big finding — our 101.65 d is ours

Team HRI (us) holds rank 1 on small at **101.65 d (submitted 2026-04-25,
unchanged for 6+ weeks).** It is OUR OWN submission.

Our local bank trajectory this project (esa_spoc_26_3) started at 142.92 d
(2026-05-30 bak) and has improved to 116.38 d. **That's still 14.73 d
worse than our April submission.** We have been re-deriving a solution
from a more recent (but worse) starting point.

### Why this happened

The 101.65 d small submission was made before the current project
version existed. Checking older project directories:
- `esa_spoc_26_2` git log has no April 25 commits; latest is May 11.
- Looking for `small.json` history in 26_2: never committed there.
- The submission likely came from a session that was lost in project
  restructuring or made via a script that uploaded directly without
  committing the decision vector locally.

### What this means going forward

1. **Path A — try to recover the 101.65 perm.** The platform stores
   submitted decision vectors. If we authenticate as Team HRI we may be
   able to download our own past submissions via the API or web UI.
2. **Path B — beat 101.65 d from scratch.** Our DP-on-ultrafine
   methodology is likely STRONGER than what produced 101.65 d (which
   pre-dated walk_perm_chrono C6 bug recognition). With sufficient
   compute we should be able to surpass our own previous record.
3. **The "R1 target" in the audit was wrong:** treating 101.65 as an
   external competitor target masked that we already had this solution.
   The real goal for small is sub-100 d (no other team has approached
   this yet).

## TGMA breakthrough is real but unreplicable

- TGMA's public GitHub (tgma-engineering) has no relevant code (drones,
  Kalman filters from 2022-23). Their SpOC algorithm is proprietary.
- They hold rank 1 on medium (199.74 d) and large (424.62 d) — both
  submitted 2026-06-05 within hours of each other, suggesting one
  generic solver they ran on both instances.
- Rank 1 large (424.62) is 2.7× better than rank 2 — massive gap.
  Likely a cluster-aware solver leveraging the [601, 150, 150, 150]
  component structure.
- Path C as "replicate TGMA" → not feasible without their code.

## Updated tactical priorities

| Priority | Target | Path |
|---|---|---|
| 1 | Small sub-100 d (new rank 1 floor) | Continue current DP-ALNS methodology; bring more compute |
| 2 | Medium → match or beat TGMA's 199.74 d | E-531 precompute → E-532 DP eval → DP-ALNS |
| 3 | Recover our own 101.65 d perm | Check platform's "download submission" feature for Team HRI |
| 4 | Large → out of reach without TGMA-class algorithm | Defer; not productive without ~10× more cores |

## What to put in memory

- HRI rank 1 small @ 101.65 d is OUR submission, not external target
- Real R1 floor to beat: 101.65 d (our own)
- TGMA is the rank-1 medium+large holder but algorithm not public
- fcmaes (dietmarwo) is fellow library author at rank 3 small
- Large is fundamentally hard without smart algorithm
