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

### Graph-wide recovery (E-721b near-miss)

Rescanned the 59903 exc-close-but-not-cheap pairs (the 8-probe near-misses) properly: **+5138 previously-
missing cheap edges recovered graph-wide** (96 min, 4 cores). Complete graph = 74208 → **79346 edges**; the
low-degree count dropped (|RARE| 120→113: 7 cities crossed out of low-degree). 4 beam configs now running on
the complete graph (`cache/ch2_giant_dense1d_aug.npz`); the decisive question is whether they thread toward
601 at < ~405 d (giant) → full < 424.62 → rank-1.

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
