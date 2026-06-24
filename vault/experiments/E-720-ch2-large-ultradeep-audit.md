---
id: E-720
type: experiment
tags: [ch2, large, rank-1, audit, assumptions, representation, deep-audit]
date: 2026-06-24
status: ACTIVE — assumption audit; reframes rank-1 as a search/sequencing gap; beam sweep running
---

# E-720 — Ch2-large rank-1: ultradeep assumption audit (find the flaw, not the optimum)

**Mandate (user):** treat as ground truth that solutions ≤424.62 (X) exist; our best Y is incomplete
(566/601 @ 298d) or rank-2 (932.53). So "no further gains" is FALSE — find the flaw in our reasoning. Four
parallel investigation agents + direct UDP audit. This **partly overturns** the E-719 "rank-1 not reachable"
verdict: it is **exhausted-within-architecture, not exhausted-of-problem**.

## The real UDP (ground truth, `src/esa_spoc_26/ch2_kttsp.py` fitness)

n=1051; decision vector = **free continuous `times[]` (n−1), `tofs[]` (n−1), and a permutation `order`**.
Objective = `times[-1]+tofs[-1]` (makespan). Constraints: all legs Δv≤600; **≤5 legs in (100,600]**, rest
≤100; chronological `times[i]+tofs[i] ≤ times[i+1]` (waiting allowed). **`max_time = 3000`.**
→ Single chain, one spacecraft (multi-vehicle hypothesis REFUTED). A6 validated: `kt.fitness(bank)=932.53`,
feasible — our oracle == official scorer.

## What the audit RULED OUT as the blocker

| suspected cause | finding | by |
|---|---|---|
| Exception budget (5) | NOT binding — all 35 stranded cities cheap-reachable from core (0 exc needed) | exc-agent |
| Table under-counting | table truthful; stranded cities have cheap in-edges (4–148), every epoch | exc-agent |
| Topology/structure | confirmed 601-giant + 3×150 (star); giant dominates; sats +19d | struct-agent |
| High-inc physics | hard-32 are high-inc (2.41 vs 1.57 rad)/low-degree, but **individually insertable** | char + ins-agent |
| **Timing optimization** | **0% gain** — multi-arrival retime of bank order = greedy (P1); windows ~FIFO at resolution | P1 |

## The two real flaws found

1. **Representation truncation (A1).** `max_time=3000` but the dense1d table covers **epochs 0–950 (31.7%)**.
   The exact "choke" legs Agent-3 found cascade-stranding (62→527, 1025→531, 1007→152) **all have cheap
   windows beyond epoch 950** (first recurrences 968/956/1004) the table simply lacks. The "fundamental
   cascade strand" was a **table artifact**, not physics. (Bites >950 only, so it broke insertion-repair but
   does not gate rank-1, which lives in 0–425.) *Within* 0–425 the cities are richly reachable — city 477
   alone has 1376 cheap arrival-phases — so the table is not the rank-1 gate either.

2. **Order/timing optimized separately + forward-myopic construction (A2/A3) — the surviving flaw.** Every
   branch (beam, GTSP, backward, insertion, the E-668 LNS) optimizes the *order* on a static cheap graph then
   retimes greedily; **none does joint order+timing or a complete-tour metaheuristic with the fine oracle.**

## Gap accounting (Phase 2): the loss is ~95% the giant's ORDER

- Banked giant = **1.52 d/leg** (913d); our beam = **0.527** (566 cities, *below* competitor's 0.674);
  competitor complete = **0.674**. A complete tour at our beam rate ≈ **335d** — X=424.62 is **1.27× above**
  it. **No physics wall.** The entire gap is *finding one coherent 601-order that hits each city at a
  compatible clock* — a time-dependent **sequencing** problem. Exceptions ~0, table ~0, sats ~0 of the gap.

## Why LNS-from-bank is blocked (a hard structural finding)

Greedy *cheap* retiming of the bank's 913 order **strands 410 legs** (clock blows past the 950 horizon).
The bank's 913 relies on *tuned* per-leg timing; under cheap-greedy it's nowhere near feasible. So the
bank-basin and the beam's cheap-feasible-basin are **disjoint** — local search cannot bridge them, and there
is **no cheap-feasible *complete* 601 seed** (the completion is the very thing we lack). Generic
complete-tour LNS is therefore a dead end here.

## Paradigm inventory (Phase 3) — untouched & live

- **Multi-start forward beam over diverse starts/params** — never done systematically (only `cities[:8]`).
  *(running: W=200 big-beam, wide-rare, single hard-start)*
- Joint continuous NLP over times+tofs — **dead** as a lever (P1: timing already optimal).
- Complete-tour LNS with fine retime — **dead** here (no cheap-feasible seed; basin separation).
- Window-compatibility clustering + *time-aware* intra-solve (TGMA's likely method) — partially refuted
  (static-LKH inflates; time-expanded GTSP refuted E-718); the *time-aware* cluster solve is unbuilt.
- CP / scheduling-with-time-windows formulation — untouched.

## Verdict & open frontier

Rank-1 is a **search/sequencing gap** on the 601-giant order, not structure/physics/exceptions/table/timing.
The forward beam caps at **566–579/601** (cheap-feasible, 0.527 d/leg, makespan solved with 126d slack); the
last ~35 are richly reachable but the forward construction strands them by frontier exhaustion. The live
lever is a **better complete-tour constructor** — currently a multi-start beam sweep; if a dozen diverse
starts/params still cap at 566, the beam architecture is confirmed exhausted and the next paradigm is a
time-aware cluster decomposition (the one TGMA-style method never built). Rank-2 (932.53) stays secure.

Refines the E-719 coverage/deadline beam work, [[E-718-ch2-large-glkh-resolution-mismatch]],
[[E-710-ch2-large-time-aware-decomp]]; applies [[M-general-deep-single-prompt-audit]] and
[[M-general-architecture-change-on-large-gaps]].
