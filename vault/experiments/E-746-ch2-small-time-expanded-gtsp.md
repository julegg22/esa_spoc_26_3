---
id: E-746
type: experiment
tags: [ch2, small, gtsp, time-expanded, glkh, arc-resolution]
date: 2026-06-28
status: IN-PROGRESS — pipeline runs end-to-end; first run STRANDS (coarse arcs too sparse). Refined fine-arc retry launched. Architecture is small's named missing lever; strand is a tool-resolution artifact, not a wall
related: ["[[E-745-ch2-large-faithful-time-expanded-gtsp]]", "[[C-035-time-expanded-gtsp]]", "[[C-036-epoch-shift-trap]]", "[[ch2-small-floor-14292]]", "[[E-710-ch2-large-time-ordering-wall-overturned]]", "[[foundation-then-search-methodology]]"]
---
# E-746 — Ch2-small time-expanded GTSP: pipeline works, first run strands on coarse-arc sparsity

The Ch2-small floor (112.996, rank 6) is diagnosed ([[ch2-small-floor-14292]]) as a SEARCH-ARCHITECTURE gap whose
named missing lever is **joint sequence+epoch global search** — i.e. the time-expanded GTSP ([[C-035-time-expanded-gtsp]]).
At n=49 this is tractable in GLKH *size* terms (unlike n=1051, [[E-745]]). Built it (`ch2_small_texp_gtsp.py`):
49 cities × K=24 uniform-fine windows = 1176 nodes, full adjacency, faithful arcs via `batch_earliest`, AGTSP
with dummy-depot open path, GLKH, faithful chrono-walk decode.

## First run (K=24, coarse build steps dstep=0.10 / tof=0.04) — STRAND
- Build: 1176 nodes but only **1820 arcs (~1.5/node)** — very sparse.
- GLKH: Value 110071026 ≈ **11 × BIG(10M)** penalty edges — i.e. the optimal "tour" had to cross ~11 non-existent
  edges because no dense feasible path exists in the sparse graph.
- Decode: 49/49 cities decoded but faithful chrono-walk **STRAND@5** (makespan 11.3d at the break) — the
  GTSP order is not chronologically realizable.

## Diagnosis — arc resolution, not architecture (same lesson as E-710)
The cheap feasible bands are **~0.002 d wide** ([[E-710-ch2-large-time-ordering-wall-overturned]]). The coarse
build scan (dep step 0.10 d) **steps over** ~95% of those bands ⇒ most real cheap arcs are never found ⇒ the graph
is starved ⇒ GLKH falls back on BIG edges ⇒ the order strands. The *decode* chrono-walk (step 0.02 d) sees arcs
fine (it threads 5 legs, and the bank tour threads all 49), confirming the misses are a **build-side** artifact.
This is the resolution-vs-tractability tradeoff of [[C-035-time-expanded-gtsp]] reappearing at the **evaluator**
level: coarse=fast-but-sparse, fine=dense-but-slow. The architecture is correct; the arc oracle was under-resolved.

## Fine-arc retry — REFUTED the resolution hypothesis
Rebuilt with dep step 0.02 d (5× finer). **Node-300 arc count was 536 — identical to the coarse build's 536.**
So finer scanning found the *exact same* arcs (6× slower for zero gain): the strand is **not** a resolution
artifact. Killed it. (Anti-oscillation: the measurement overruled the story.)

## Real cause (measured) — the graph was cheap-only, missing the ≤5 exception bridges
The small bank uses **exactly 5 exception legs** (dv 100–600) — the max budget — because the cheap (dv≤100) graph
is **multi-component** (audit: 4-component, 5.9% dense). My time-expanded graph was built with `thr=THR=100`
(cheap arcs only), so it had **no exception-bridge arcs** → GLKH cannot connect the components → it substitutes
11 BIG edges → chrono-walk strands. The strand was a **modeling omission**, not resolution and not architecture.

## Fix (launched) — exception-bridge arcs
Add a second arc pass at `thr=EXC=600` with a penalty `PEN=1e6` (< BIG, ≫ cheap tof) so GLKH bridges components
using as few exception arcs as possible; the decode chrono-walk falls back to EXC at bridges and `kt.fitness`
enforces the ≤5 constraint. This mirrors the large problem's comp0+bridges structure. Coarse build steps (the
resolution refutation means 0.10 d is fine and ~6× faster). If GLKH now threads 49/49 with ≤5 exceptions and
beats 112.996 → rank gain (→ guard-bank + escalate); headroom is 2.12 d to rank-3, 11.35 d to rank-1.

## Exception-arc result (K=30) — bridge fix WORKS, but still strands@22 (window misalignment)
Adding exception arcs densified the graph **13×** (node-600: 11,797 arcs vs 911 cheap-only) — confirming the
sparsity diagnosis. GLKH solved; the decode threaded **22/49 cities** (vs 5 with the cheap-only graph) before
stranding — clear progress from the bridge fix. But GLKH still used ~5 BIG edges (value 51M) and the chrono-walk
strands@22: a pair is adjacent in the GTSP order that has **no feasible transfer at the realized epoch** (even
with EXC fallback). This is the residual **window-discretization vs realized-clock** gap of
[[C-035-time-expanded-gtsp]] — the order is feasible in the K=30 windows but the actual chained clock lands
between windows. Same family as the epoch-shift trap ([[C-036-epoch-shift-trap]], [[E-747]]).

## Next — finer windows (K=50, running)
At n=49, K=50 (2450 nodes) is still trivial for GLKH; finer windows give the order finer epoch choices. If it
threads 49/49 below 112.996 → rank gain. If it still strands, the GTSP's discretized order fundamentally cannot be
realized faithfully, and the proven TD method for small is **DP-on-ultrafine-grid** ([[C-026-dp-on-time-expanded-graph]],
which already solved small) — i.e. carry the exact clock, don't discretize into windows.

## Bank impact
None yet (probe). Ch2-small bank unchanged at 112.996 (rank 6, held). Nothing submitted.
