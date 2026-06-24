---
id: E-046
type: experiment
tags: [experiment, ch2, large, kttsp, global-reorder, lkh, refutation, pole, time-dependent-tsp]
date: 2026-06-12
status: REFUTED — single-pass global epoch-aware reorder is UNWALKABLE even on the fine grid; the pole (r1=424.62) needs an iterated epoch-robust construction we have not cracked
instance: hard.kttsp (n=1051)
script: scripts/ch2_e584_large_global_finegrid.py (drives scripts/ch2_e572_large_global_epoch_lkh.py)
related: [[E-045-ch2-large-grid-discretization]], [[E-044-ch2-large-ring-sweep]], [[E-034-ch2-large-epoch-aware-reorder]], [[E-019-ch2-edge-compute-marginal-value-zero]], [[O-014-2026-06-07-competitor-algorithm-inference]]
---

# E-046 — Ch2 large pole: global reorder refuted on the fine grid

Decision probe for the user's "scope LKH first, then decide" on the large
pole. E-045 fixed the evaluator (0.005d grid) and banked 1013.29d. The
open question: does a global epoch-aware reorder, now on the corrected
grid, produce a WALKABLE order near r1=424.62?

## Setup

Re-ran E-572's global epoch-aware OR-Tools open-path re-route, but with
the cost matrix on a 0.01d grid (n_steps=1200) and the chronological walk
on a 0.01d grid (window=40, n_steps=4000) instead of the old 0.1d/0.13d.
Seed = the 1013.29 bank order. 4 workers, TL=900s/iter.

## Result (iter 0, single pass) — DECISIVE

- Global cost matrix: forbidden=87.2% (the cheap graph is sparse/4-comp),
  pen=178 cheap-but-not-feasible-at-epoch.
- OR-Tools found a path with **cheap-cost ~340.5d** (BELOW r1=424!),
  big_jumps=4, pen_used=0 — i.e. a near-optimal STATIC order exists in
  the fine-grid cheap graph (even cheaper than E-572's coarse 389d).
- **The chronological walk REJECTED it** (infeasible: needs >5 exc / hits
  an unreachable leg). Kept BASE 1026.67d, no gain over the 1013 bank.
  Nothing banked.

## Verdict

The finer grid did **not** fix the unwalkability — because unwalkability
is not a resolution problem. It is the **time-dependent TSP epoch-shift
trap**: the cost is built at one set of node-epochs, but reordering
shifts every realised arrival epoch, so edges that were cheap at the
seed epochs become infeasible at the new epochs, and the ≤5-exception
budget cannot absorb the gap. This reproduces E-572 (coarse) and E-573
(fixpoint diverged) — three independent refutations of the single-pass /
naive-iterated global reorder.

**Reaching 424.62 requires an iterated EPOCH-ROBUST construction** — one
that converges to an order which stays walkable as its own epochs settle
(edges feasible across an epoch BAND, or chronological insertion that
never commits an unreachable leg). Nobody on our side has cracked this;
it is almost certainly TGMA's recipe for their 1-shot 1143→424 (June 5).

## Decision (the "then decide" half of the user's instruction)

**Do NOT commit multi-day effort to the large pole now.** It is:
- **binary** — 0 marginal points unless the realised walk actually
  crosses 424.62 (large is already rank-2-secure at 1013.29 < r2=1143.56);
- **uncertain** — the core obstruction (walkable global TD-TSP under a
  5-exc budget) is exactly what three of our attacks failed on;
- **multi-day** — epoch-robust construction is a from-scratch solver.

⇒ LOW expected-points/hour. The dominant unrealised campaign value
remains **SUBMISSION of the 6 banks** (medium = RANK 1, all currently
0 points), which is user-gated. Large stays banked at 1013.29d (rank 2,
hard ×16/9 = ~16 pts when submitted).

## Lesson

E-045's evaluator-audit win (−26d) was real but orthogonal to the pole:
fixing discretization tightened the *margin*, not the *feasibility
structure*. A finer grid makes legs cheaper; it does not make an
unwalkable global order walkable. Separate "how accurately we score an
order" from "whether a better order is reachable under the constraints."
