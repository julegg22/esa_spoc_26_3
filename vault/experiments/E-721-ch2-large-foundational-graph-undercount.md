---
id: E-721
type: experiment
tags: [ch2, large, rank-1, bug, cheap-graph, under-count, foundational, evaluator]
date: 2026-06-25
status: ACTIVE — foundational under-count CONFIRMED + recovered; beam aug-vs-baseline test running
---

# E-721 — Ch2-large: the foundational cheap-edge graph was built by an 8-sample probe (under-count bug)

**User push (correct):** "every challenge we first concluded SOA exhausted, then found a wrong assumption /
implicit constraint / bug. Redo the audit on patterns we left out." This overturned my E-720 "real
algorithmic gap" conclusion — the gap was a **foundational under-counting bug**, the same family as the Ch1
departure/arrival asymmetry and the Ch2-small 0.002d-resolution blindness.

## The bug

The Ch2-large cheap-edge graph `cache/ch2_e533_large_adj.npz` (which **every** branch builds on — dense1d
table, beam, GTSP, LNS, clustering) was built by `ch2_e533_large_structure.py` probing **only 8 fixed
(t,tof) cells per pair** across the 3000d horizon:
`(10,1),(300,3),(800,5),(1500,8),(2000,2),(2500,10),(100,0.5),(1200,4)`.
An edge is "cheap" iff one of those 8 lands dv≤100. Cheap windows are narrow and recur on the synodic beat,
so **8 fixed samples miss most of them** → truly-cheap edges declared non-cheap and lost. The "100% faithful"
dense1d table only ever **refined pairs the 8-probe already accepted** (`np.where(adj[i])[0]`), so it
**inherited every false negative and structurally could not recover a missing edge.**

## Evidence (measured)

- Hard city 103: **28 genuinely-cheap predecessors absent from the graph entirely** (0 lost by dense1d → they
  were never in the adjacency; the 8-probe missed them). Confirmed across stranded cities (short- and
  long-tof misses).
- These are cheap **short-tof** edges (zero makespan cost) — exactly the flexibility the beam lacked.

So "566 cap / 35 hard cities / 4 components / giant-dominates" are all **suspect as artifacts of an
under-sampled graph**, not physics.

## The fix (E-721 recompute)

`ch2_giant_graph_recompute.py`: rescan the 35 stranded cities' in+out edges **properly** — scan ALL 601
partners (not just 8-probe-accepted), dense1d-grade tof resolution (kept fine to avoid re-introducing the
0.002d blindness), COARSE=8 epoch pre-scan over the **0–460d rank-1 window** (rank-1 lives <425d, so the
0–3000 range and its cost are unnecessary). 73 min on 4 cores. `merge_aug` overlays the recovered edges onto
a resampled-original table (0–460/230-epoch grid) → `cache/ch2_giant_dense1d_aug.npz`.

**Recovered: +1059 cheap edges** for the 35 focus cities (~30/city; the low-degree ones ≈ double, e.g.
477: 7→~15 in-deg) that the 8-probe had hidden.

## The decisive test — CONFIRMED (the under-count was the wall)

Two beams, identical 566-params, same 0–460 grid, differing ONLY in edge recovery:

| beam | cities threaded | rare threaded | d/leg |
|---|---|---|---|
| baseline (no recovery) | 554 | 93/120 | 0.568 |
| **aug (35-city recovery)** | **575** | **105/120** | 0.652 |

**Recovering just 35 cities' edges = +21 cities (554→575)**, and 575 beats the original 950-grid wall of
566 by +9 *despite* the coarser grid (which alone cost the baseline −12). The "566 cap" was an artifact of
the 8-probe under-counted graph. **The user's push was right; E-720's "algorithmic gap" verdict is refuted.**

### Graph-wide recovery (E-721b near-miss) + result

Rescanned the 59903 exc-close-but-not-cheap pairs properly: **+5138 cheap edges recovered graph-wide** (96
min). Complete graph 74208 → **79346 edges**; |RARE| 120→113 (7 cities left low-degree); stranded cities'
in-degree rose (e.g. 7→16). 4 beam configs on the complete graph threaded **554 / 562 / 563 / 557** — i.e.
the beam still caps ~554–575 **regardless of graph completeness**. Insertion-repair on the complete graph
(from 557@295d) threads the stranded cheaply (+0–3.5d each) but from a 295d base, +44 cities → ~427d giant →
**rank-2**.

### Verdict (corrected, two-layer)

1. **The 8-probe under-count was REAL and is fixed** — the "566 wall" was substantially an artifact (broke to
   575 on a *narrow* recovery; the graph is now correct, +6200 edges). The user's "there's always a hidden
   misconception" pattern held; E-720's "real algorithmic gap" was wrong.
2. **A second layer remains:** on the *correct* graph the **beam heuristic** still caps ~575 (path-dependent;
   more edges shift its route, not its ceiling), and the **completeness↔efficiency tension** persists — beam
   tours that thread more cities have higher makespan, so no base is both near-complete AND low-makespan
   enough for insertion to finish 601 under 405d. Threading 601@<405d needs a **better global search on the
   now-correct graph** (LNS/metaheuristic seeded from a complete <460d tour, e.g. the 563@342d; or a finer
   non-greedy constructor) — tractable and NOT a research moonshot, but unfinished in this window.

Rank-2 (932.53) stays secure. Refutes [[E-720-ch2-large-ultradeep-audit]]'s premature verdict; extends
[[M-general-foundation-then-search]] (audit the graph's COMPLETENESS before declaring search exhausted).

### The CASCADE — why local search (LNS/insertion) can't reach rank-1 (E-721d, structural)

Built the LNS properly on the correct graph: exact-arrival oracle (`fine_arr`, max_revs=2 fast verify, ~0.8s
retime — correct: the 563-tour gives 2 strands, vs `table_arr`'s 428), strand-targeted destroy, incremental
re-timing repair. The seed (563-tour + 38 appended) = 34 strands. **Decisive failure mode:** inserting a
stranded city delays EVERYTHING downstream, and on a tight schedule those downstream legs miss their windows
→ **one insertion cascades 34→220 strands.** This is the completeness↔efficiency tension at the retime level:
in a TIME-DEPENDENT tour, any local move (insert / 2-opt / swap) re-times the whole suffix and cascades. So
**no local-search completion reaches a tight (rank-1, <405d) 601 order** — the schedule has no slack to
absorb the cascade. (Completing 601 at ANY makespan IS doable with a full-horizon 0-3000 table — the cascade
then only inflates makespan, landing rank-2 — but that adds 0 points.)

**Final precise verdict:** rank-1 requires a GLOBALLY TIGHT time-dependent 601-order (no leg-by-leg slack),
which is the competitor's hard-won method; every tractable local constructor we have (beam caps ~575,
insertion/LNS cascade, static-LKH inflates, time-expanded GTSP resolution-fails E-718) cannot produce it.
The foundational graph is now CORRECT (the real win, +6200 edges, broke 566→575); the remaining rank-1 step
is a genuine time-dependent global optimizer, not a quick build. Rank-2 (932.53) secure.

### No FURTHER under-count — the ~576 completion cap is genuine (E-721f)

Applied the user's skepticism to the *second* wall: the near-miss recovery only rescanned exc-close (≤600)
pairs; ~226k pairs the 8-probe rejected as **>600** were never rescanned. Tested the hardest cities: of 120
sampled >600-rejected predecessors each, **0 are actually cheap** — the 8-probe correctly rejected them as
orbitally far. The hard cities' low cheap-in-degree (14-15) is **real physics** (high-inclination → few cheap
transfers), not an artifact. So: the graph under-count was a real bug (fixed, 566→575); the remaining ~576
cap across ALL methods (beam, insertion/LNS cascade, global TD-SA plateau ~25 strands) is a GENUINE
time-dependent completion difficulty, not a hidden misconception. The faithful TD-SA (E-721e, or-opt/2-opt +
strand-targeted relocate, fine makespan) descends 34→~25 strands then plateaus — confirming the hard ~25
high-inc cities resist a rank-1-tight (<405d) ordering. Rank-1 needs the competitor's sophisticated
TD-TSP completion (genuine research problem); a *complete* 601 tour at ~rank-2 (<932) is the realistic TD-SA
outcome and would improve the large bank's robustness.

### The retime obstacle blocking the LNS (E-721c, precise)

Tried an LNS on the recovered graph (complete 601 seed = 563-tour + 38 appended, strand-penalized
objective). It needs a FAST retime to search at scale, so it used the table-lookup `table_arr` (no Lambert).
**That retime fundamentally diverges from the fine oracle over long orders:** the *original* 566-tour on the
*original* table strands **253/566** under `table_arr` (not a resampling artifact — confirmed on the clean
grid). Cause: `table_arr` departs at the GRID epoch with the stored min-tof, but feasibility needs departure
at the EXACT accumulated clock + a verified tof; the grid-quantization error accumulates across hundreds of
legs. So: the fast retime is unusable for global search, and the fine retime (`compute_transfer` per leg) is
too slow for LNS-scale iteration. **This is THE remaining engineering blocker to 601@<405d, and it is
well-defined and solvable** — build an exact-arrival oracle (a vectorized `compute_transfer` retime, or a
table that stores, per (edge, fine-epoch), a *verified* arrival usable by raw lookup) → then LNS / global
re-order on the now-correct graph. Not finished in this window.

## (original test plan)

Two beams, identical params (the 566-config), differing only in the graph:
- `beam_aug` on the recovered graph;
- `beam_base460` on the same 0–460 grid **without** recovery (isolates the grid-resample change from the
  edge recovery).
If aug threads **past 566**, the foundational under-count was (part of) the wall. Whack-a-mole risk: the
recovered beam may thread a new path and strand a *different* set → then broaden the recompute to all ~120
low-degree cities (feasible: ~2.5h at this rate) or the full graph.

## Methodological takeaway (the pattern, made explicit)

**Before concluding "search/algorithm exhausted" on a constructed graph/evaluator, audit the
graph/evaluator's COMPLETENESS first.** Every "exhausted" verdict in this project so far fell to an
under-counting foundation: a faithful-but-incomplete oracle makes the problem look harder than it is. Extends
[[M-general-foundation-then-search]], [[L-013-evaluator-resolution-phantom-wall]],
[[M-general-deep-single-prompt-audit]]; corrects [[E-720-ch2-large-ultradeep-audit]]'s premature
"algorithmic gap" verdict.
