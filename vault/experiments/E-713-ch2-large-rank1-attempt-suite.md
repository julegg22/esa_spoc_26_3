---
id: E-713
type: experiment
tags: [ch2, large, rank-1, time-dependent-tsp, beam, lkh, insertion, clustering, negative-result]
date: 2026-06-24
status: tractable-levers-exhausted
---

# E-713 — Ch2-large rank-1 attempt suite (E-711/712/713): tractable levers exhausted

**Goal (user):** target Ch2-large rank-1 (424.62 d) for a multi-hour window after the E-710 beam broke the
367 wall (540–558/601 @ ~260 d, strands the rest).

## What was tried, and the result

| approach | result | why it fails |
|---|---|---|
| plain fine-tof beam (E-710) | 540–558/601 @ ~260 d | makespan-greedy prune strands the low-degree periphery |
| rarity-weighted beam (E-711) | **198/601** (worse) | biasing toward periphery pulls the beam out of the connected core → strands early |
| insertion repair (E-711) | **584/601 @ 816 d** | weaving periphery into a fixed order costs 8.9 d/leg; 17 cities have no feasible cheap slot |
| orbital-element clustering (E-712) | periphery = **62/120 singletons** | clustering densifies the core (0.39 vs 0.127) but does NOT absorb the orbitally-isolated periphery |
| static-LKH (elkai) + fine-tof retime, iterated (E-713) | **2481 d/144 strands → 2847 d/183 strands (DIVERGES)** | LKH optimizes a STATIC cycle ignoring chronology → order is time-infeasible; fine-tof can't fix a bad order |

## The precise diagnosis (gap decomposition)

The rank-1 gap is **entirely periphery-weaving efficiency**: core (540 cities) is already competitive at
0.48 d/leg; the 61 periphery cities cost us **8.9 d/leg** (insertion) vs the competitor's **2.7 d/leg**.
The periphery *is* includable (competitor proves 601 @ 424), but only via a **chronologically-feasible
global ordering** — which:
- the **forward beam** produces but strands the tail (can't reach low-degree cities late);
- **LKH** can't produce (static cycle → 144+ strands when time-walked);
- **insertion** produces only partially (584/601) and expensively.

Correction to an earlier over-pessimistic read: the 17 insertion-stranded cities are **mostly high-degree
core** (11 of 17 have in/out ~150) that greedy mis-placed — so a global solver *does* have headroom; the
blocker is specifically **chronological feasibility**, not raw connectivity.

## Verdict

**Large rank-1 requires a TIME-EXPANDED global solver** — GTSP on (city, epoch) nodes (the only construct
that yields chronologically-feasible global orderings), i.e. the competitor's inferred multi-day cluster +
time-expanded LKH/GLKH build. Every *tractable* tool (beam, rare-beam, insertion, cluster, static-LKH) is
exhausted and precisely characterized. **EV for the hours window: low.** Recommend holding large at the
secure **rank-2 (932.53, +211 cushion)** and redirecting compute to the closer **trajectory rank-5**
(+16,179, the extended-tof sweep is banking), unless the user wants to commit to the multi-day GTSP build.

Refines [[ch2-large-time-ordering-wall]], [[E-710-ch2-large-time-aware-decomp]],
[[M-general-architecture-change-on-large-gaps]]; this is the [[M-general-basin-overarching-search]] case
where the basin gap needs a different *formulation* (time-expanded), not a better local search.
