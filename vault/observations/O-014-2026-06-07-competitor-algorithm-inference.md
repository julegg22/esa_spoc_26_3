---
date: 2026-06-07
tags: [observation, leaderboard, competitor-inference, submission-patterns, methodology]
status: inference from public submission data via api.optimize.esa.int GraphQL
---
# O-014 — Inferring competitor algorithms from public submission patterns

All data here is from the public leaderboard. No private/proprietary
information used. The inference is what a careful observer would
deduce from timestamps, score patterns, and submission cadence.

## Top-team patterns

### Team HRI (colleagues, db54c27...) — rank 1 small

```
Small:   154.99 → 124.56 (1d, -30) → 111.76 (7d, -13) → 101.65 (8d, -10)
                                     [stable 6+ weeks since 2026-04-25]
Medium:  379.67 → 320.17 (8d, -59) → 216.95 (42d, -103)  [June 3 burst]
Large:   2072.84 → 1238.52 (50d, -834)                    [June 3 burst]
```

**Inference**:
- **April push, then silence**: 4 small submissions in 16 days, then
  nothing for 6+ weeks. Their small at 101.65 d appears to be the
  natural floor of their algorithm.
- **June 3 medium+large submissions at 14:30:41 and 14:31:54 — 73
  seconds apart** — strongly suggests an automated pipeline that
  ran their (possibly upgraded) solver on both instances and submitted
  back-to-back.
- **No re-submission of small in June** — they didn't bother re-
  running their newer algorithm on small (where they were already at
  101.65). Suggests either: (i) the newer algorithm wouldn't improve
  small, or (ii) small is below their algorithm's noise floor.
- **Algorithmic signature**: Generic time-coupled solver. The
  ~10 d/submission gains on small suggest a metaheuristic with
  occasional breakthroughs (not deterministic exact).

### TGMA (5af55cab...) — rank 1 medium + large

```
Small:   162.84 → 122.80 (4.3d, -40)  [only 2 submissions, May, rank 5]

Large (June 5 burst!):
  2026-06-05 12:20:18  1206.75
  2026-06-05 12:21:11  1186.65    -20 d in 53 seconds
  2026-06-05 19:45:31  1143.56    -43 d in 7h
  2026-06-05 20:50:26   424.62    -719 d in 1h !!!  ← STRUCTURAL BREAK

Medium (June 5 burst!):
  2026-06-05 21:01:30  207.39
  2026-06-05 21:07:19  200.60     -7 d in 6 min
  2026-06-05 21:47:54  199.74     -1 d in 40 min
```

**Inference**:
- **The 1143 → 424 single-hour jump on large is the most remarkable
  event in the entire leaderboard history.** From 2.7× rank 2 to
  rank-1 territory in 1 hour. This is not incremental tuning — it's a
  structural insight or major algorithm switch.
- **Likely candidate**: cluster-decomposition. The 4-component
  [601, 150, 150, 150] structure of large means solving each
  component as an independent TSP (LKH-3 or Concorde scale) + smart
  exception bridging would give exactly this kind of jump. The
  pre-jump 1143 d ≈ "ignoring cluster structure" baseline; the
  post-jump 424 d ≈ "exploiting cluster structure".
- **Medium follow-up**: ran the same algorithm on medium right after
  → got 199.74 d. Smaller relative gain (medium is less component-
  structured at n=181).
- **Small (rank 5 at 122.80)**: their algorithm doesn't gain much
  on small. Likely because for n=49 the cluster decomposition has
  fewer per-cluster TSP wins.
- **Algorithmic signature**: Cluster-aware decomposition + per-
  cluster TSP solver (likely LKH-3 or Concorde) + exception-bridge
  optimization. Scales BETTER as n grows (counter-intuitive).

### fcmaes (dietmarwo, 867404f7...) — rank 3 small

```
Small:   126.29 → 122.66 → ... → 110.88 (rank 3, stable since 2026-05-28)
Medium:  340.65 → 298.56 → 281.88 → 255.38 (rank 4, 2026-06-04)
Large:   2072.85 → ... → 1562.17 (rank 4, 2026-06-04)
```

**Inference**:
- This is dietmarwo, author of [fast-cma-es](https://github.com/dietmarwo/fast-cma-es).
  Almost certainly using his own library.
- The April 26 outlier (jumped UP from 120 → 176 then back to 114)
  is characteristic of a stochastic optimizer that got a bad random
  seed. Reproducibility issue → submitted a worse run by mistake.
- **Algorithmic signature**: CMA-ES + DP hybrid (his
  `run_ch2_fcmaes_dp.py` pattern). Wide search, parameter-driven.

### ScholORs_HFUU+Sunway (dd46ba62...) — rank 2 small

```
Small:   28 submissions over April 6 — May 17. 162 → 108.77.
         Many oscillations (e.g., 114 → 122 → 114). Heavy iteration.
Large:   9 submissions. Stuck at ~1968 (rank 6).
Medium:  32 submissions. Steady grind to 298.21.
```

**Inference**:
- VERY high submission frequency → likely a stochastic metaheuristic
  with many parameter tunings.
- **Doesn't scale to large**: many large submissions but stuck around
  1968 d. Their method doesn't exploit n=1051's structure.
- **Algorithmic signature**: GA or SA with multi-start. Hand-tuned
  for small (rank 2!) but not generic enough for large.

### AC_TUWien (f5a760fd...) — rank 4 small, active

```
Small:   127.30 → 111.79 (3 days, 5 submissions)
Large:   2167.40 → 1153.90 (2 days, 5 submissions) -- big jump
Medium:  221.45 → 204.35 (3 hours)
```

**Inference**:
- Recent entrant (started June 1) but fast progress.
- The 1477 → 1153.90 large jump (323 d in 1.5h) on June 4 suggests
  an algorithmic improvement, likely LKH or similar.
- **Algorithmic signature**: Modern TSP-derived solver, likely LKH-3
  with time-coupled cost adaptation.

## Aggregated insights

### Who is still active (last 7 days, 2026-05-31 to today)

| Team | Last submit | Pattern |
|---|---|---|
| TGMA | 2026-06-05 | active, just had breakthrough |
| AC_TUWien | 2026-06-04 | active, rapid improvement |
| fcmaes | 2026-06-04 | active, slow improvement |
| Paulina Heine | 2026-06-05 | active but high mks (>140) |
| Team HRI | 2026-06-03 | last small submit April 25 |
| ScholORs | 2026-05-25 | possibly stopped |
| (a) | 2026-06-01 | sporadic |

### Small (n=49) natural floor

Top 3 on small all converge around 100-110 d:
- 101.65 (HRI), 108.77 (ScholORs), 110.88 (fcmaes)

Suggests **all current public algorithms hit a similar floor ~ 100
d on small**. To meaningfully exceed (sub-100 d) requires either:
- More compute applied to the same family of methods
- A genuinely different methodology (foundation-then-search + DP IS
  in this category — none of the observed patterns suggest DP-on-
  ultrafine-grid)

### Large (n=1051) — TGMA's algorithmic moat

TGMA's 424.62 d is 2.7× better than rank 2 (1153.9). The single-
hour 1143 → 424 jump strongly suggests a structural insight (most
likely cluster decomposition + per-cluster TSP solver). Without
adopting a similar architecture, our 4-core hardware can't catch up
on large.

### Where our methodology differs

None of the observed submission patterns suggest DP-on-ultrafine-
Lambert-grid evaluation. The closest is fcmaes's CMA-ES+DP, but his
DP is likely much coarser. **Our methodology lives in unexplored
algorithmic territory for SpOC4 KTTSP.** This is encouraging for the
solo-run premise: a new method + sustained search may eventually
challenge the 100 d floor that current methods plateau against.

## Implications for our strategy

1. **Small target**: 101.65 d is the rank 1 floor. To beat it, our
   DP-ALNS needs to recover the residual schedule slack better than
   HRI's algorithm. Currently at 116.38 d, need −14.73 d.

2. **Medium target**: 199.74 d (TGMA, very recent). Their algorithm
   is cluster-aware; our medium re-attack (E-531) precompute will
   determine if our DP methodology can match it.

3. **Large target**: 424.62 d (TGMA). Their cluster decomposition
   gives them a 2.7× moat. To compete on large, we'd need to either
   implement cluster decomposition or skip large.

4. **Cadence**: 4 active teams, ~3 weeks left in competition. Expect
   continued improvements from TGMA, AC_TUWien, fcmaes especially.
   Re-query leaderboard every 2-3 days.

## Open intel questions

- Has TGMA published anything? Look for SpOC4 papers or post-
  competition analysis (unlikely before deadline).
- Does AC_TUWien have a GitHub or affiliation page? Their U Wien AC
  group page (acg.tuwien.ac.at) might list relevant publications.
- fcmaes's GitHub has TSP-variant examples; any insight into his
  Lambert handling could help.
