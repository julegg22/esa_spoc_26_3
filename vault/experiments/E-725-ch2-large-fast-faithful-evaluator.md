---
id: E-725
type: experiment
tags: [ch2, large, rank-1, evaluator, numba, lambert, correctness, optimizer-exploits-bugs]
date: 2026-06-26
status: ACTIVE — fast+faithful numba evaluator built; order-search running on it
related: ["[[E-723-ch2-large-bank-reproduction-audit]]", "[[E-724...]]", "[[L-013...]]"]
---

# E-725 — Ch2-large rank-1: a fast AND officially-faithful numba transfer evaluator

User decision (2026-06-26): "build the vectorized evaluator" (rank-1 large search was slow ~minutes/iter);
"hold all submissions until ch2-large improves" (incl. the rank-1 medium).

## What was built

A numba reimplementation of `KTTSP.compute_transfer` (`scripts/ch2_fast_transfer.py`):
- **Kepler ephemeris** from `opar=[a,e,i,RAAN,argp,M0]` — validated **exact** vs pykep `eph`.
- **Multi-rev Izzo Lambert** (faithful port of poliastro's Householder-iteration formulation), min-dv over
  revs 0..20 and both transfer directions — matching the official scorer's `max_revs=20`.
- **Batched grid scanner** (`cheap_first_tof`, numba `prange`): 402k transfers in 1.58s (~35x pykep).

Swapped into the E-723 table-seeded time-beam (`CT()` replaces pykep), giving the order-search a ~4x/call
faster, table-fine-resolution-preserving evaluator.

## The decisive lesson — an OPTIMIZER EXPLOITS EVALUATOR BUGS (validate on selected cases, not random)

First validation looked great: random sample of transfers matched pykep, **cheap (<150) cases exact to
0.0000**. But when the greedy search ran on it, the numba schedule reported **938.5d / 0 strands** while the
**official pykep per-leg check found 50 legs OVER threshold (max dv 371)**. The search had actively *selected*
the rare inputs where my Lambert produced **spurious low-dv solutions** (non-converged Householder roots whose
velocities happen to look cheap). Random sampling never hits these; **a minimiser seeks them out.**

**Two-layer fix:**
1. **Residual filter** in `lambert_dv`: after Householder, reject any root with `|tof_eq_y(x)| > 1e-3` (i.e.
   not actually a solution of the time-of-flight equation). This removed the spurious solutions: an
   *adversarial* re-test (30k transfers, keep numba-says-cheap) found **1442 cheap cases, 0 false positives**,
   and the bank order now has **0 official over-threshold legs**.
2. **Official gate at bank time**: any candidate solution is verified by `udp.fitness<=0` (pykep, max_revs=20)
   before guard-banking — numba is trusted in the hot loop, pykep is ground truth at the gate.

**Methodology takeaway (reusable):** when you build a fast surrogate to *optimise against*, validating it on a
random sample is insufficient — the optimiser will find and exploit the surrogate's error modes. Validate on
**optimizer-selected** inputs (run the search, check its chosen solutions against ground truth) and add a
ground-truth gate at the decision boundary. Sibling of [[L-013...]] (evaluator-resolution) and the Ch1
asymmetry bug — all "the evaluator, not the search, was the problem."

## Bonus finding — the old timebeam under-counted feasibility (max_revs=2)

The pre-numba timebeam used `ktf = KTTSP(max_revs=2)` as a speed shortcut, so it missed multi-rev cheap
transfers the official scorer (max_revs=20) accepts. The numba CT uses max_revs=20 → **more faithful** to
official, not just faster. (This is why the bank order strands fewer legs under numba.)

## Status

Order-search (`ch2_giant_order_search_inc.py`, incremental suffix re-time, E-724b) running on the
fast+faithful evaluator from a tight seed (beam-583 + appended) and the bank seed. The full-grid scanner
variant (E-725b `ch2_giant_fast_search.py`) is **shelved**: 0.02d tof grid too coarse, misses narrow windows
(274 strands) — the table-seed + numba-fine-verify path (E-725c/d/e) is the correct one. Rank-1 (<425d) is
still a hard compression problem, but now searched on a correctly-specified problem with a fast, official-
faithful evaluator. Banks secure; nothing submitted.
