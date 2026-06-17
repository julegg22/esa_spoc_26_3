# E-650 — Ch2-small assumption audit (user-driven, 2026-06-17)

**Premise (user):** the large gap to the field (our 112.996 vs r1 101.65, field
108–111, all in-model) means "no further gains" is a FALSE conclusion; find the
flaw in our reasoning, not optimize further. Hypothesis: an architectural change
toward GLOBAL solution search unlocks progress.

## Ground truth

- `easy.kttsp`: n=49, **min_tof=0.001 d**, max_time=200, dv_thr=100, dv_exc=600,
  n_exc=5. Objective = minimise makespan = times[-1]+tofs[-1]. `kt.fitness` is
  **4 ms/eval** (48 Lambert solves).
- Our precompute `ch2_e526` samples edges only at **ToF ∈ [0.025, 8.0] d** — the
  short regime **[0.001, 0.025) is never computed**.
- Every branch (E-038/603/606/607/609/611/618, E-520/521 SLSQP, E-527/614 DP,
  E-529 ALNS) operates on that table, searches ORDERS, and DERIVES epochs (greedy
  forward / DP-on-table / local SLSQP). SLSQP lost to DP-on-grid by ~16 d (the
  discontinuous Lambert landscape defeats gradient methods). **No branch ever ran
  a global continuous optimizer over the joint (epochs, ToFs) on the official
  evaluator.** The DP table also mis-scores the bank by +5.5 d (118.5 vs 112.996).

## The flaw

My prior "near-forced / basin-locked / model-floored" verdict was true only
*conditional on this architecture* and was reported as unconditional. We proved
ORDERS to exhaustion but never globally optimised the SCHEDULE (epochs/ToFs as
free joint variables) and never sampled short ToFs.

## Gap accounting

makespan = first_dep + Σtof + Σwait = ~0 + 105.71 + 7.29 = 112.996. To reach
101.65 (−11.35 d): **~7.29 d is pure idle/wait** (epoch misalignment a joint
schedule optimisation attacks directly) + **~4 d slower legs** (Σtof, partly the
unsampled short-ToF regime). **Loss is concentrated in the SCHEDULE, not the
route** — exactly where the order-then-derived-epochs architecture is blind.
Same shape as Ch1-trajectory (optimised the 5% term, left the 95% term unbuilt).

## Assumptions (violating-solution in italics)

- **A1** table captures all useful transfers. *Uses a ToF<0.025 d leg.*
- **A2/A3** epochs derived from order; order-centric. *Joint (order,epoch,ToF)
  global search; route falls out of schedule.*
- **A4** routing on the cheap graph. *Minimise makespan over all ΔV≤600 transfers;
  exceptions used where FAST, not just where structurally forced.*
- **A5** earliest-arrival ≈ optimal. *Departs late to catch a faster downstream leg.*
- **A6** evaluator faithful enough to rank. *DP table mis-ranks by 5.5 d.*

## Plan (assumption-falsifying, ranked by info gain) — QUEUED behind Ch1 E-649

1. **S1** `/tmp/ch2_s1_freeepoch_retime.py` — CMA-ES over the 96 schedule vars
   (epochs+ToFs) of the FIXED bank order, official `kt.fitness`, wait+ToF encoding
   (monotone by construction). If makespan < 112.996 for the SAME order ⇒ the gap
   is SCHEDULE optimisation, not order search (falsifies A2/A5/A6). Cheap.
2. **S2** `/tmp/ch2_s2_shorttof_probe.py` — scan ToF ∈ [0.001, 0.025) for all (i,j);
   count cheap/fast edges the table misses (falsifies A1). Cheap.
3. **S3** (build) joint (order, epoch) global metaheuristic on the official
   evaluator, not table-restricted (falsifies A3/A4) — the competitor architecture;
   S1/S2 de-risk it.

`cma` installed (pip). Both scripts instrumented per
[[M-general-instrument-experiments-before-launch]]. See [[ch2-small-floor-14292]]
(prior "floor" verdict now flagged as architecture-conditional).
