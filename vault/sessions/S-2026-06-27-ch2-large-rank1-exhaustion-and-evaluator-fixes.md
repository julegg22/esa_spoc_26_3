---
date: 2026-06-27
type: session
tags: [ch2, large, rank-1, audit, evaluator, methodology, exhaustion]
related: ["[[E-723-ch2-large-bank-reproduction-audit]]", "[[E-725-ch2-large-fast-faithful-evaluator]]", "[[E-726-ch2-large-ultrathink-audit-rank1-reachable]]", "[[M-general-root-objective-and-proxy-skew]]"]
---
# Session 2026-06-24..27 — Ch2-large rank-1: evaluator fixes, 3 audits, and the rank-2/rank-1 wall

## Arc (user-driven, three audits, each refuting the prior optimism)

A very long session almost entirely on **Ch2-large rank-1** (424.62d; our bank 932.53=rank-2). The user
repeatedly pushed "we keep concluding it's in reach, then it collapses — find the wrong assumption." Each push
found a real flaw, but the end state is honest:

1. **Process fix (CLAUDE.md §5b):** "exhaustion is a transition, not a stop" — encoded after I named the
   TD-TSP path then pivoted to busywork. [[feedback-exhaustion-is-a-transition]].
2. **Audit #1 (E-723):** the search FRAME was mis-specified — aug graph 0-460 excluded 334/601 bank visits;
   greedy timing strands valid orders; the 1d table is epoch-sparse. Built the **full-graph time-beam +
   fine-epoch fallback**.
3. **Fast evaluator (E-725):** numba multi-rev Izzo Lambert + Kepler eph, validated vs pykep (cheap transfers
   EXACT). **Caught a critical bug — the search EXPLOITED spurious non-converged Lambert roots** (50 official
   over-thr legs); fixed with a residual filter (0 false-positives on 1442 adversarial cheap cases).
4. **Audit #2 (E-726 ultrathink):** reframed rank-1 as REACHABLE (short-tof subgraph strongly-connected
   601/601) — but then SELF-CORRECTED: the "beam already at rank-1 pace (283d)" was a **table-optimism
   artifact**; faithful retime = ~1.8 d/leg + strands. **Methodology: re-verify FAVORABLE numbers faithfully
   too (the MIRROR of proxy-skew).**
5. **Audit #3 (user: "why never a complete solution?"):** two stacked evaluator flaws — the faithful precompute
   was **short-tof-only** (≤1.3d; bank uses up to 6.7d), and the **retimer was long-tof-BLIND** (fine-scan
   med±0.8). Fixed the retimer → **bank order now retimes faithfully to 598/601 (3 strands) = we CAN reproduce
   the bank.**

## The honest verdict (rank-1 = research-grade; rank-2 = secure)

Tested/reasoned through EVERY standard TD-TSP approach; all wall:
- construction (beam/GRASP) caps ~190 (short-tof, rank-1 pace) → ~329 (wait-budget, rank-2 pace), never
  complete; **wait-budget has a sweet spot ~60 (larger = worse, wastes time on long waits)**.
- static LKH (full-tof) = TD-infeasible (163-strand); my epoch-aware iterated LKH DIVERGES (buggy re-cost);
  E-562's analog floored at 932.
- time-expanded GTSP = resolution-vs-tractability walled (~450 dep-epochs/city; coarse=disconnected,
  fine=intractable per E-718).
- **Bank recipe (full-tof OR-Tools + epoch-aware iterate + timing-DP) is the ONLY thing that completes → 932d
  = rank-2 (already banked).**

**Core tension (now fully understood):** short-tof = fast (~0.4 d/leg) but phasing-rare (~6% windows) →
incomplete; full-tof = complete but slow (~1.4 d/leg) → rank-2. **Rank-1 needs BOTH = a globally PHASED
short-tof TD-TSP — the competitor's heavily-invested research-grade solver, not crackable by our toolkit
before the 06-30 deadline.**

## Durable deliverables

- Faithful numba evaluator (E-725) + epoch-dense short-tof window table (E-726d, cache/ch2_giant_faithful_windows.npz)
  + fixed full-tof retimer (E-726). We can now evaluate/reproduce orders honestly.
- Methodology: [[M-general-root-objective-and-proxy-skew]] (proxy-metric skew REFRAMED-not-REFUTED + the
  evaluator-optimism mirror); new triggers in M-applying-methodology-triggers; REFRAMED banners on E-722/723/725.
- The recurring root cause, named: **optimistic/partial evaluators** (table makespan, short-tof windows,
  long-tof-blind retimer) — every false "rank-1 is close" traced to one.

## State at session pause

Holding pattern: 4 GRASP chains exploring cheaply (plateau ~329), per user "keep pushing rank-1, HOLD all
submissions." All banks held/unsubmitted by user choice (Ch2-large 932=rank2, Ch2-med 189.10=rank1,
Ch2-small 112.996, Ch1-traj 361014kg). Ch1 levers (matching-II, E-701 fleet) untouched this session.
