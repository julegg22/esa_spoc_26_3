---
id: E-718
type: experiment
tags: [ch2, large, rank-1, gtsp, glkh, time-expanded, resolution-mismatch, negative-result]
date: 2026-06-24
status: rank-1-via-time-expanded-GTSP-REFUTED (fundamental, not search-bound)
---

# E-718 — Ch2-large rank-1 via GLKH: the time-expanded GTSP is resolution-mismatched

**Goal (user):** "Download GLKH, if required." GLKH (Helsgaun's Generalized-TSP solver) is the one tool the
[[E-713-ch2-large-rank1-attempt-suite]] verdict named as missing for the time-expanded GTSP rank-1 path.
Built it, solved the AGTSP directly, and got a **definitive negative with a precise structural reason** —
not "ran out of time" but "the formulation cannot be faithful and tractable at once."

## What was built (reproducible; GLKH itself is gitignored under `reference/`)

- **GLKH-1.1** downloaded + compiled (`reference/GLKH-1.1`, user-authorized):
  `curl -O http://webhotel4.ruc.dk/~keld/research/GLKH/GLKH-1.1.tgz && tar xzf … && make`.
- **`scripts/ch2_giant_glkh.py`** — emits an **AGTSP** (asymmetric generalized TSP) instance from the
  time-expanded graph: one set per city (601) + a 0-cost **depot set** turning the GTSP cycle into an open
  chronological path; FULL_MATRIX with non-arcs = `BIG`; decode → faithful fine-tof retime.
- Two instances (via `scripts/ch2_giant_texp_build.py`, now parameterized `[bucket] [horizon] [keep] [out]`):
  **giant** 12 d / KEEP-5 → 5703 nodes; **mid** 6 d / KEEP-8 → 9450 nodes.

## Two solver-encoding bugs found and fixed (each silently wasted every run)

1. **`BIG` ≥ GLKH's cluster-binding `M`.** GLKH's GTSP→ATSP transform adds `M = INT_MAX/4/Precision ≈ 5.37e8`
   to inter-cluster edges to keep each cluster contiguous (`SolveGTSP.c:56`). With `BIG = 1e9 ≈ 2·M`, the
   solver found it *cheaper to split a cluster* (pay ~M) than to traverse a `BIG` non-edge → **`Illegal
   g-tour: cluster entered more than once`**, no tour ever written. Fix: `BIG = 1e7` — above the worst
   feasible tour (601 × 8000 milli-d ≈ 4.8e6, so one non-edge still dominates any all-real tour → solver
   prefers feasibility) yet ≈ 2 % of M (cluster-binding dominates).
2. **Hardcoded `NAME : ch2giant`** → GLKH derives temp-file prefixes from NAME, so two parallel solves
   collided on `TMP/ch2giant.tour`. Fix: `NAME = TAG`.

## The premise that died on contact with the data

The whole time-expanded line (E-713/715/716/717 and the custom Lagrangian) assumed *"edges go forward in
epoch → DAG → no subtours, the hard part is free."* The build diagnostic refutes it:
**358 265 / 370 838 inter-city edges (96.6 %) are intra-bucket** (`dst_bucket == src_bucket`), 0 strictly
backward. With 12 d buckets nearly every transfer arrives in the bucket it departs → **not a DAG-by-level**;
it is a genuine dense AGTSP. (This is why CP-SAT/elkai/Lagrangian all stalled, and why GLKH — a true AGTSP
solver, no DAG assumption — was the right tool to *test* the formulation.)

## Result — GLKH solved it well; the formulation is the problem

Both ran 1800 s + multi-round GPX2/IPT post-optimization (which escaped the main-search plateau, 20→ a few
bucket-arcs). Valid g-tours written (fix #1 confirmed). Then **faithful fine-tof retime**:

| instance | bucket | GLKH bucket-infeasible arcs | **faithful fine-strands** | makespan |
|---|---|---|---|---|
| giant | 12 d | 4 | **157** | 2584 d |
| mid | 6 d | 10 | **178** | 2782 d |

The **4 → 157** (giant) and **10 → 178** (mid) blow-ups are the entire finding.

## The precise diagnosis: resolution mismatch (fundamental, not search-bound)

[[E-710-ch2-large-time-aware-decomp]] established the cheap-tof **feasible bands are ≈ 0.002 d wide**. The
time-expanded **buckets are 6–12 d** — **1000–6000× coarser**. So a bucket edge asserts "a cheap transfer
exists *somewhere* in this 6–12 d window," but the chronological retime needs the transfer to exist at the
**exact accumulated arrival time** (0.002 d precision). ~150–180 of the "feasible" bucket legs are infeasible
at their real time → strands. The bucket graph is **time-blind at the scale that governs feasibility**.

This is not fixable by more search or a better solver:
- **Faithful buckets** (~0.002 d over 456 d) ⇒ ~230 000 buckets ⇒ astronomically large graph ⇒ intractable.
- **Tractable buckets** (6–12 d) ⇒ too coarse ⇒ ~150–180 strands ⇒ infeasible (≫ the 5-exception budget).

Any time-expanded GTSP is trapped between these. That retires the formulation for rank-1 — across **all**
solvers tried: Noon-Bean+elkai, restricted Gurobi, CP-SAT AddCircuit, the custom Lagrangian (E-717), and now
**SOTA GLKH**. The blocker was never the solver; it was the discretization.

The irony: E-710's own insight (0.002 d bands) is exactly what bucketing discards. The **fine-tof beam**
(E-710, C-034) keeps the **exact clock per state** and threads **558/601 @ ~260 d** with few strands — it is
strictly the higher-fidelity construct; the time-expanded GTSP is a step *backward* on fidelity. The honest
rank-1 lever, if any, is improving the beam's **exact-clock periphery threading** (the E-711/712/714 line),
**not** a global GTSP.

## Verdict & recommendation

**Ch2-large rank-1 via time-expanded GTSP is REFUTED on fundamental (resolution) grounds**, with SOTA GLKH as
the closing evidence. Hold large at the secure **rank-2 (932.53 d, +211 cushion)**. Highest *unrealized*
board value remains **submitting the strong banks** (medium rank-1, large rank-2, trajectory) — all 0 pts
until uploaded as `JE_MemExp`. New lesson candidate: *discretization fidelity must match the evaluator's
feasible-band width before a global solver can help* (extends [[L-013-evaluator-resolution-phantom-wall]]).

Refines [[E-713-ch2-large-rank1-attempt-suite]], [[E-710-ch2-large-time-aware-decomp]];
case for [[M-general-architecture-change-on-large-gaps]] (the gap needs a different *formulation*, and the
time-expanded one is now proven a dead end).
