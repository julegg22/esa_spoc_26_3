---
id: E-740
type: experiment
tags: [ch2, small, deep-audit, order-search, labeling-dp, floor]
date: 2026-06-28
status: ACTIVE — /deepaudit ch2-small; the E-734 faithful labeling-DP order search was never applied to small
reframes: [E-609, E-613, E-618, E-623]
related: ["[[ch2-small-floor-14292]]", "[[E-734-ch2-medium-rank1-reclaimed-182]]", "[[E-735-ch2-large-deepaudit-medium-machinery-untried]]", "[[foundation-then-search-methodology]]"]
---
# E-740 — /deepaudit ch2-small: the medium E-734 order-search machinery was never applied to small

**Y = 112.996d bank** (rank 6, n=49). **X = r1 101.65d** (gap −11.35d, 10%); the rank cluster is dense — r3=110.88
(−2.12d), r4=111.76, r5=111.79. Standing verdict (E-609/E-613/E-616/E-617/E-618/E-623, all LIVE): **112.996 is a
"free-method floor under our architecture"** — three independent search families converge; GRASP 22k restarts
can't reach the basin; epochs are tight (65% legs <0.2d window) ⇒ "search is architecture-bottlenecked."

## Phase 2 — measured on the bank (pos-control: kt.fitness reproduces 112.9960 exactly, feasible)
- makespan 113.00 = **sum_tof 105.71d + idle 7.29d**. 48 legs (43 cheap, 5 exc).
- **flight-only floor for the bank's ORDER = 105.71d > r1 (101.65)** ⇒ retiming the bank order can NEVER reach r1
  (or even close); the lever is a **shorter-FLIGHT ORDER**, not better timing. (This is why E-612/E-613
  continuous-retiming converged — they retimed a *fixed* order whose flight floor is already 105.71.)
- Flight time concentrates in **24 long legs: 14 @ 2-4d (39.84d) + 10 @ >4d (46.91d) = 86.75d (82% of flight)** —
  cheap-but-SLOW transfers a better order could replace with shorter hops at the reached epochs.

## Phase 1 — the load-bearing assumption (shared by E-609/E-613/E-618)
**A-ARCH: "112.996 is the floor of free search because three order-search families converged there."** But those
families were **NOT the E-734 machinery** that broke the byte-for-byte identical Ch2-MEDIUM "189.10 floor" this
session (189.10→182.11, reclaimed rank-1). E-734 = (a) **all cheap-edge windows** as faithful continuous (dep,tof)
suffix-min structures, (b) **or-opt/2-opt restricted to cheap edges**, (c) **exact labeling-DP retime** (min-
arrival per exc level, waiting allowed) — a faithful per-order makespan with no epoch-shift trap. Small's E-609
(422k orders) / E-613 (continuous, 56 orders) used a **fixed cheap-graph + DP inner timing oracle**, NOT the
faithful labeling-DP over the full continuous edge windows, and were ~100× slower (no dense precompute). So the
"converged floor" is conditional on an architecture that — exactly as E-735 found for large — **never included
the E-734 method.** A solution violating A-ARCH = a small order found by the E-734 labeling-DP search below 112.996.

## Phase 3 — paradigm inventory
| paradigm | small touched? | survives scrutiny? |
|---|---|---|
| construction + local moves, fixed graph, DP timing (E-609/613/618) | YES | the "floor" — but on the pre-E-734 architecture |
| **E-734 labeling-DP order search (full cheap-edge windows + cheap-restricted or-opt/2-opt)** | **NO** | the untried lever — proven to break medium's identical floor 6 days ago |
| joint sequence+epoch global LKH (time-expanded) | NO | the memory's named lever; heavier, but the labeling-DP search is the cheaper first test |

## Verdict (pending probe #1)
The "112.996 free-method floor" is almost certainly **conditional on the pre-E-734 architecture** — the exact
faithful labeling-DP order search that broke medium's identical floor was never run on small. flight-only 105.71d
> r1 confirms the lever is reordering (shorter flight), which is precisely what E-734 optimizes. **Probe #1 (the
small port of `ch2_medium_order_search.py`, running) is the decisive test:** beats 112.996 ⇒ floor refuted, lever
real toward r3/r1; reproduces 112.996 ⇒ floor genuine for this method too (then the residual is the heavier
time-expanded-LKH lever).

## Further exploration paths (cheapest info-gain first)
1. **E-734 labeling-DP order search on small** (`scripts/ch2_small_order_search.py`, built; n=49 so very fast) —
   violates A-ARCH. **Binary:** any order <112.996 official-feasible ⇒ floor refuted. Reproduces 112.996 ⇒ genuine.
2. **Fast-batched-evaluator beam (E-739 `batch_earliest`) global construction on small** — violates "construction
   converged"; a from-scratch faithful beam with the new fast evaluator, diverse starts. **Binary:** a complete
   49-tour <112.996 ⇒ construction basin was architecture-limited.
3. **Time-expanded LKH / joint sequence+epoch** (the memory's named lever) — violates "order and epoch optimized
   separately". Build the time-expanded graph (n=49 is tiny, tractable for exact LKH) + Concorde/LKH. **Binary:**
   LKH tour <112.996 ⇒ the joint-global pipeline is the missing competitor method.

Diagnostic; bank unchanged, nothing submitted. Per §5b probe #1 is running (the cheapest assumption-falsifier).
