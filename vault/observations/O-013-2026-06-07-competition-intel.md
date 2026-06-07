---
date: 2026-06-07
tags: [observation, leaderboard, competition-intel, hri, tgma, methodology, solo-run]
status: confirmed via api.optimize.esa.int GraphQL; corrected 2026-06-07 (Team HRI ≠ us)
---
# O-013 — Competition intel: team identities + solo-run context

## Context — this is a solo run, separate from Team HRI on the leaderboard

**This project is an independent solo exploration: how far can one
person + Claude Code get on the SpOC4 KTTSP?** No submissions have
been made from this project. The "Team HRI" entry on the
leaderboard is a separate group at the Honda Research Institute who
are competing in parallel; the user is deliberately NOT consulting
them for methods, to keep this attempt clean as a measurement of the
solo-with-AI-assistance ceiling.

This means: all leaderboard entries (including Team HRI's 101.65 d
rank 1 small) are **genuine external targets** to beat with our own
methodology.

## Team identities (all 8 leaderboard users decoded)

| User ID | Team | Affiliation | Notable rank |
|---|---|---|---|
| db54c27... | **Team HRI** | Honda Research Institute Europe — colleagues, NOT us | rank 1 small (101.65, 2026-04-25) |
| 5af55cab... | **TGMA** (Marvin & Talha) | Germany | rank 1 medium (199.74) + rank 1 large (424.62) — both 2026-06-05 |
| dd46ba62... | ScholORs_HFUU+Sunway | Hefei + Sunway U | rank 2 small (108.77) |
| 867404f7... | **fcmaes** (dietmarwo) | Germany | rank 3 small (110.88); author of fast-cma-es library we use |
| f5a760fd... | AC_TUWien | TU Wien, Austria | rank 4 small (111.79), active improver |
| be625c47... | Paulina Heine | U Vienna | rank 6 small |
| 05b3d535... | (no team info) | — | — |
| cd77dc25... | (no team info) | — | — |

## The 101.65 d target is held by HRI colleagues

Team HRI (separate group) holds rank 1 on small at **101.65 d (submitted
2026-04-25, unchanged for 6+ weeks).** This is the rank-1 floor to beat.
Per the project constraint (solo + Claude Code only), their methods are
off-limits.

Our local bank trajectory this project (esa_spoc_26_3) started at 142.92 d
(2026-05-30 bak) and has improved to **116.38 d** via the foundation-
then-search methodology (E-519b leg refine → E-527 DP on ultrafine table
→ E-529 DP-ALNS). To beat the leaderboard rank 1 we need a further
14.73 d of improvement.

The legitimate path forward: continue scaling the methodology that's
already working (foundation diagnostic → DP-based search), and submit
our own result once we're competitive.

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
| 1 | Small → beat 101.65 d (current external rank 1) | Continue DP-ALNS methodology; potential follow-up rounds with bigger neighborhoods |
| 2 | Medium → beat 199.74 d (TGMA's rank 1) | E-531 precompute → E-532 DP eval → DP-ALNS |
| 3 | Submit our results to the leaderboard (once we beat 110.88 = current rank 3) | Manual upload to optimise.esa.int as own user |
| 4 | Large → out of reach without smart algorithm | Defer; n=1051 makes precompute intractable on 4 cores |

## What to put in memory

- The 101.65 d small rank 1 is HRI colleagues (independent team) — to be beaten, NOT consulted
- We have not submitted anything yet; the leaderboard does not include us
- TGMA holds rank 1 medium+large; algorithm not public
- fcmaes (dietmarwo) is fellow library author at rank 3 small
- Large is fundamentally hard without smart algorithm
- Solo-run constraint: no consultation with HRI colleagues for methods
