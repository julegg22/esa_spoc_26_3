---
id: E-590
type: experiment
tags: [experiment, ch2, large, kttsp, endgame, local-search, reorder, retime, chrono-walk, null]
date: 2026-06-13
status: NULL — endgame joint reorder+retime does NOT beat the 932.5304 bank. No /tmp candidate written. Endgame order is LOCALLY OPTIMAL under chrono-walk+retime; large now floored for BOTH timing and intra-component endgame reorder under the fixed 5-exc assignment.
instance: ch2-large (hard.kttsp, n=1051)
script: scripts/ch2_e590_endgame_reorder.py (bg agent a4aafdcd)
related: [[E-589-ch2-large-retime-dp-timing-floor]], [[E-587-ch2-large-lkh-trap-and-waiting-lever]], [[ch2-large-first-bank-topology]]
---

# E-590 — Ch2 large: endgame joint reorder+retime is a NULL (bank stays 932.53)

## Setup
Follow-on to [[E-589-ch2-large-retime-dp-timing-floor]]: that retime-DP floored
the TIMING axis for the fixed 1051-perm at 932.5304 d and localized the residual
to the **dense endgame cluster** (the final segment after the last exc bridge at
leg 957: perm positions 958..1050, 93 nodes, heavy 4–7 d tofs on legs ~1034–1049).
Pure global node-reorder is a dead end (LKH hit the TD-TSP epoch-shift trap,
E-587). The only trap-free reorder is to evaluate every candidate ORDER by the
actual chrono walk + retime. This experiment ran a local search (2-opt + or-opt
L1–L3) over the endgame INTERIOR order only, keeping entry node (116) and the
dead-tail terminus (931) fixed and the 5 exc bridges intact, scoring every
candidate by the true chrono walk.

Evaluator architecture (trap-free): hold the upstream tour FIXED at the bank's
epochs (entry node 116 arrives at 818.7824 d, set by the bank's upstream walk +
26.7 d of distributed upstream idle), then chrono-walk the endgame from that epoch.
Inner ranking = fast greedy earliest-departure walk (0.4 s, incremental
suffix-walk with leg cache — exact-matched vs the full walk on 22 random
2-opt/or-opt moves before launch). Each greedy-accepted order is re-scored under a
per-leg min-arrival retime (DELAY_GRID 0–6 d @ 0.25), and the best RETIME order is
the one validated against the 932.53 bank via kt.fitness.

## Result — NULL. Best retimed endgame ≥ 936.36 d > bank 932.53 d
| order | greedy walk (d) | retime walk (d) | true bank |
|---|---|---|---|
| bank endgame order | 943.05 | 936.36 | 932.5304 |
| best reorder found  | 940.17 (and dropping) | **936.36** | — |

The local search DID improve the greedy (zero-idle) walk (943.05 → 940.17 via
or-opt relocations) but the gain **washed out entirely under retime**: every
improved order retimed to ~936.357, essentially identical to the bank order's
retime (936.358). No reorder produced a retimed endgame below 936.36, i.e. **no
order beat the 932.53 bank**. Nothing written to /tmp/ch2_large_endgame_cand.json.

## Two distinct findings

**(1) Isolated-endgame retime cannot reach the bank's tail.** Freezing upstream at
bank epochs and re-deriving endgame timing locally tops out at 936.36 — 3.83 d
ABOVE the bank's 932.53 tail. The bank's 932.53 was a GLOBAL retime: it adjusted
upstream idle (26.7 d over 190 legs, only 2.9 d inside the endgame) to shift the
endgame entry epoch into better launch windows. Holding upstream fixed forfeits
that coordination. So the endgame's makespan is not separable from the upstream
retime — the bank's tail is a global-retime artifact, not an endgame-local optimum.

**(2) The endgame heavy tail is a connectivity property, not a bad order.** The
heaviest-leg tail nodes are near-ISOLATED in the cheap-transfer graph at their bank
epochs: nodes 739 / 343 / 753 each have **0/20 cheap (dv<100) transfers** to random
targets at epoch ~880–920 d. Their only feasible transfers are the expensive 4–7 d
ones, regardless of visiting order. The 6.7 d-tof legs are forced by orbital phasing
of a leftover "scatter" set (~15 high-ID nodes swept into the endgame), so reorder
gains ~0 — confirmed empirically (936.36 invariant across all reorders) and
structurally (zero cheap out-degree).

## Verdict — large floored for timing AND endgame reorder under fixed exc-assignment
Combined with E-589 (timing floored) and E-587 (global reorder trap), the bank
932.5304 d is now a local optimum for the fixed 5-exc-bridge assignment along three
axes: departure timing, global node order (epoch-shift-trap-free attempts), and
intra-component endgame local reorder. The 2.2× gap to **r1 = 424.62** is NOT
reachable by any move that preserves the current exc-bridge placement / component
decomposition. It requires a **from-scratch global time-dependent solver** that
co-optimizes the partition into components, the exc-bridge legs, AND order+timing
jointly — i.e. the scatter nodes (739, 343, 753, …) must be assigned to a DIFFERENT
component / visited at a DIFFERENT epoch where they have cheap connectivity, which
is outside the bank's fixed topology. Point-EV remains 0 (rank-2 secure at
r2=1143.56). large session total unchanged: 932.5304 d.
