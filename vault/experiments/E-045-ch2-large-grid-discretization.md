---
id: E-045
type: experiment
tags: [experiment, ch2, large, kttsp, evaluator-audit, discretization, banked, methodology-win]
date: 2026-06-12
status: BANKED — tof-grid was a hidden bottleneck; bank 1041.33→1015.17d (−26.16d) by re-walking on a finer grid, NO reordering
instance: hard.kttsp (n=1051)
script: scripts/ch2_e582_large_grid_audit.py, scripts/ch2_e583_large_finegrid_rewalk.py
related: [[E-044-ch2-large-ring-sweep]], [[E-043-ch2-large-legslack-phasemiss]], [[M-general-foundation-then-search]], [[ch2-large-bank]], [[M-applying-methodology-triggers]]
---

# E-045 — Ch2 large: the tof grid was the bottleneck (evaluator audit)

User chose "scope LKH first" for the large pole. Before building an
epoch-aware LKH cost matrix, I applied the **audit-the-evaluator** trigger
(r1=424.62d ⇒ 0.404 d/node is below E-044's coarse-grid chainable floor
of 0.857d — the cheapest explanation for a 2.5× gap is a coarse grid).

## E-582 — grid-resolution audit (decisive)

`find_earliest_transfer` defaults: tof_window=12, **n_steps=120 ⇒ 0.100 d
grid**. The whole bank, E-579 phase-miss, and E-044's 0.857d floor were
computed on it. Sampling 300 cheap-adjacent (i,j) at the node's bank
epoch, comparing min cheap-tof at 0.100d vs 0.010d vs 0.005d:

- coarse mean cheap-tof **1.987d**, fine (0.01d) **1.872d** → **0.116 d/leg
  mean shorter**, **156/300 legs** improve >0.05d, max single-leg gain
  **1.94d**. Feasibility set unchanged (coarse missed 0).

The 0.1d grid was systematically over-stating tof. ~1050 legs × 0.12 d ⇒
~120d of *static* headroom — far more than E-044 v1's 7.6d.

## E-583 — re-walk the SAME bank order on a finer grid → BANKED

No reordering. Same perm, same 5-exc placement (legs k∈{149,416,566,807,
957}, recovered from the bank's realised dv>dv_thr). Re-walk chronologically,
exc allowed only on those exact legs:

| n_steps | grid | realised mk | feas |
|--------:|-----:|------------:|:----:|
| 120 | 0.100d | REJECT @leg 662 | — |
| 600 | 0.020d | REJECT @leg 662 | — |
| 1200 | 0.010d | **1018.061** | ✓ |
| 2400 | 0.005d | **1015.173** | ✓ |
| 3600 | 0.0033d | 1017.064 | ✓ |

**Banked 1015.173d (−26.16d vs 1041.33).** Backups large.json.bak.e583,
.e583b; both round-trips verified on disk, viol=[0,0,0,0], exc=5, perm
valid. Coarser grids REJECT where finer succeed: realised epochs shift,
and a leg un-bridgeable at the coarse epoch becomes bridgeable at the
fine epoch — a sensitive cascade (3600 > 2400: non-monotone/chaotic, so
n_steps has a sweet spot, not "more is better").

## Why this matters (reframes E-044's verdict)

E-044 concluded "no greedy/sweep heuristic reaches r1" using the coarse
grid. But **the coarse grid inflated every floor we measured**: the
0.857d phase-adjacent floor and the 0.69 d/node "near-optimal" claim were
both ~0.12d/leg too high. The true chainable floor is lower than we
thought. r1 (0.404 d/node) is still 2.4× below 1015's ~0.97 d/node, so
reordering is still needed — but the gap is smaller than E-044 claimed,
and the LKH cost matrix MUST be built on the fine grid.

## Go-forward

1. (done) bank 1015.17 — large stays rank-2-secure with more margin.
2. Epoch-aware LKH cost matrix **on the 0.005d grid**, single pass,
   re-walk chronologically (the original option-3 probe, now with the
   correct evaluator). Test whether reorder+fine-grid trends toward 424.
3. The cascade is chaotic → a cheap search over n_steps / tiny epoch
   perturbations on the fixed bank order may recover a few more days.

## Lesson

Classic [[M-general-foundation-then-search]] payoff: when a result
looks like an algorithm gap, audit the EVALUATOR's discretization first.
Weeks of "large needs a fundamentally different solver" partly masked a
0.1d tof grid that was silently taxing every one of 1050 legs. One audit
+ a re-walk = −26d, zero new search.
