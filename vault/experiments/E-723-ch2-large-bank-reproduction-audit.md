---
id: E-723
type: experiment
tags: [ch2, large, rank-1, audit, evaluator-resolution, table-sparse, frame-fix, time-beam]
date: 2026-06-26
status: ACTIVE — frame fix (full-graph time-beam + fine-epoch fallback) validating on the bank order
---

# E-723 — Ch2-large: "can we reproduce our own bank?" audit → the search FRAME was mis-specified

> 🔄 **REFRAMED 2026-06-26 by [[E-726-ch2-large-ultrathink-audit-rank1-reachable|E-726]]** (data valid,
> direction wrong). The findings — horizon truncation, greedy-timing strands valid orders, the table is
> epoch-sparse — stand. The **conclusion** ("rank-1 needs a from-scratch global TD solver = a ~2× compression
> moonshot") was skewed by the premise **P: completeness measures progress / the 932 d makespan is the thing
> to beat down.** Corrected **P′:** we *already* have the fast structure (time-aware beam at rank-1 pace); the
> short-TOF subgraph is strongly connected (601/601). Rank-1 = *complete the fast beam*, reachable. See
> [[M-general-root-objective-and-proxy-skew]].

**User audit (2026-06-26):** "Did 48h make progress toward a complete tour? Why did no experiment give a
closed tour near our banked solution? Can we reproduce the bank with the currently selected graph?" This
forced a stop-and-check that overturned the recent direction.

## What the bank is (verified)

`solutions/upload/large.json` → `udp.fitness = [932.53, 0,0,0,0]` — a **valid complete 1051-city tour**.
Decision vector = `times[n-1] ++ tofs[n-1] ++ order[n]` (3151 long). Giant cities visited across **67–932 d**
(median 498 d), **only 29.6 d total wait** (a tight schedule, not lazy).

## Why no experiment reproduced it — three compounding, quantified reasons

1. **Horizon truncation.** The recent beams searched `ch2_giant_dense1d_aug.npz` (**0–460 d**). **334/601
   giant cities are visited *after* 460 d** in the bank → more than half the banked solution lies outside the
   graph the search used. Reproduction needs the full 0–950 table.
2. **Greedy-earliest timing strands valid orders.** Re-deriving departure times greedily (earliest cheap
   window) on the bank's own giant order strands **111** legs (only 3 from missing edges). Earliest-arrival
   races ahead of the phase; the next leg's cheap window is then unreachable. Our entire search was
   order-only + greedy time — a strictly narrower space than the UDP's joint `(order, times, tofs)`.
3. **Rank-1 needs the giant in <425 d vs the bank's 932 d** — a ~2× makespan compression, no intermediate
   rank. (Consistent with the long-standing "lone-outlier moonshot" read.)

## The deeper finding — the table is SPARSE per-edge (evaluator-resolution wall)

Building the fixed-order **time-beam** (full 0–950 graph, branch over next-K cheap departure windows, keep W
earliest) still stranded the **bank's own order** at leg 166 (300→684), even with a 120 d wait budget. Root
cause, pinned exactly:
- Bank does 300→684 at **depart 247.24 d, tof 6.51 d, dv 99.70** (marginal, just under 100).
- The 1 d-grid table's cheap epochs for 300→684 are `[144, 718, 721, 801, 802, 803]` — **247 d absent**: the
  window is **narrow in epoch (sub-1 d)** and the grid sampled just outside it.
- Across all 598 giant-giant bank legs: table misses **9 (2%)** — 3 absent edges + 6 sub-grid-epoch windows.
  Each missing leg strands a complete retime, so 2% gaps = no reproduction.
- A **fine (0.2 d) epoch scan** of 300→684 finds cheap transfers at depart **210, 212, 217, 219 d** — windows
  the table *and* the bank missed (the bank could have been faster here). So the table is not just 2%-short on
  the bank's path; it is **sparse per-edge**, hiding much real flexibility.

**Conclusion:** the foundation (cheap-edge table) is correct at the pair level (E-721) but **resolution-limited
at the epoch level** — it misses the marginal-dv / narrow-epoch transfers the true optimum exploits. Every
table-based method inherits this blind spot. This is the same evaluator-resolution pattern as Ch2-small
(L-013) and the Ch1 asymmetry bug: an under-resolved foundation made the problem look harder than it is.

## The frame fix (user-chosen: "keep rank-1, fix the frame")

`scripts/ch2_giant_timebeam.py`: fixed-order time-beam on the **full graph** + a **cached fine-epoch (0.2 d)
fallback** (`fine_scan_edge`) that recovers marginal windows when the table yields nothing in the wait budget.
Validating now on the bank order — does it thread (0 strands) and at what makespan (≤932 d confirms the fix;
<932 means the fine evaluator already beats the bank's timing). Next: wrap it in order search to compress
toward <425 d = rank-1. The fine scan is slow (~15 s/edge, cached) → a faster continuous-transfer evaluator
(or a finer precomputed table) is the follow-on engineering need.

## Verdict on the path

48 h gave **methodological** progress (E-721 pair-level graph fix, phase-lock/corner-paint characterization,
insertion/SA ruled out) but **no ranking progress** — and this audit explains why it was structurally
impossible: wrong horizon + wrong (order-only-greedy) frame + resolution-blind table. The corrected frame is
now in place. Rank-1 remains a hard compression problem, but for the first time we are searching the right
space with an evaluator that can see the transfers the optimum uses.

Supersedes the E-722 "next family = better forward construction" plan (construction on the sparse table caps
regardless). Extends [[E-721-ch2-large-foundational-graph-undercount]], [[L-013...]] evaluator-resolution,
[[foundation-then-search-methodology]], [[deep-single-prompt-audit]].
