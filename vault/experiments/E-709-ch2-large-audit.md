# E-709 — Ch2-large deep audit: the wall is a genuine time-dependent TSP (no easy flaw)

**Date:** 2026-06-23
**Trigger:** user — "rank-1 (424.62) is far off our 932 bank; for such a pattern there was ALWAYS a
straightforward reason: missing architecture, a bug/wrong assumption, or a more-global basin. Find the
flaw in our reasoning or the exploration we are missing."

## Hypotheses tested (all refuted with measurements)

| # | Hypothesis | Experiment | Result |
|---|---|---|---|
| 0 | 8-probe cheap adjacency under-sampled → graph wrong, wall artificial | `ch2_large_adj_recheck.py` dense re-scan of 300 e533-"non-cheap" pairs | **0/300** actually cheap → adjacency CORRECT |
| 0b | bank order just needs dense short-tof re-timing | `ch2_large_shorttof_walk.py` | 931.4 d, no collapse, 61 strands → ORDER is the gap, not timing |
| 1 | degree was wrong urgency proxy; window-DEADLINE ordering threads the wall | `ch2_large_deadline_greedy.py` (EDF / EDF-reachable / min-arrival) | EDF **160**, EDF-reach **207**, min-arrival **367** — deadline metrics WORSE than min-arrival; wall is global |
| 2 | is rank-1 even near-optimal? assignment-relaxation LB | `ch2_large_lb_route.py` #2 | LB **14.8 d** (0.025 d/leg), all 601 cheap-assignable, 0 forced-exc → cost-floor negligible, makespan is 100% time-coupling |
| 3 | a strong GLOBAL static-cost solver beats greedy's strand | `ch2_large_lb_route.py` #3: OR-Tools GLS TSP on min-window-tof → faithful walk | static-optimal order **strands at 10/601** (burns all 5 exc in first 10 legs) → static cost PROVABLY insufficient |

## Threading ladder (how far each construction gets, faithfully walked)

```
static-TSP optimal (OR-Tools GLS)   10/601   <- WORST (optimizing wrong objective)
degree-greedy (E-666)              ~350/601
min-arrival greedy                  367/601   <- best simple
rank-1 competitor                   601/601 @ 424 d
```

## Conclusion

The giant (n=601) is a genuine **time-dependent TSP**: cheap edges are short (median min-tof 0.1 d) but
narrow-windowed (~32 d, 1.1% of horizon). #2 shows the entire makespan is window-alignment (edge-cost
floor is negligible, 14.8 d). #3 shows any solver blind to *when* windows open strands almost immediately
— **time-dependence is essential, not optional**. So the gap to rank-1 is NOT a missing architecture, a
bug, or a different static basin. The only paradigm that works is **time-aware decomposition** (cluster by
window-compatibility → LKH within), i.e. the competitor's (TGMA June-5 1143→424) cluster+LKH pipeline.

Unlike Ch1-trajectory (real eccentric-departure bug → +93k banked) and Ch2-small (mis-scoped cap term),
**Ch2-large's audit found no straightforward flaw — the wall IS the problem.** The user's "there was
ALWAYS a straightforward reason" premise does not hold here, and that is itself the rigorous finding.

## EV

All-or-nothing: no intermediate rank between our 932 (rank 2, +211 cushion) and 424 (rank 1). Only payoff
is rank 2→1 ≈ **+1.78 weighted pts**, requiring a >2× makespan cut via a multi-hour time-expanded build.
**Recommendation: hold large at rank-2; the time-aware-decomposition build is a low-EV moonshot vs the
trajectory rank-5 push and submitting the strong unrealized banks.**

Refines [[E-710-ch2-large-time-aware-decomp]], [[E-034-ch2-large-epoch-aware-reorder]], [[M-general-architecture-change-on-large-gaps]].
