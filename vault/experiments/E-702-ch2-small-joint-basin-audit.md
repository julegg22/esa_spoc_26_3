---
id: E-702
type: experiment
status: AUDIT (no bank change) — applied the Ch1-trajectory lens (evaluator bugs / hostile defaults /
  asymmetries / basin-locks) to Ch2-small. Found two real Ch1-shaped defects (DP +5.5d offset; a 0.05d
  tof floor 50× above the spec min_tof) BUT proved neither is load-bearing: S1 shows the bank order's
  schedule is officially optimal (free retime, zero descent), and a from-scratch joint test shows NO
  small order-neighbor beats 112.996 under a FREE OFFICIAL schedule. Verdict: Ch2-small really is
  basin-isolated at 112.996 — now established on the OFFICIAL objective, not the DP proxy. Unlike Ch1,
  no bug breaks the wall; the lever remains the non-local time-expanded TD-TSP (+ a small open
  exception-reallocation sub-lever).
date: 2026-06-22
tags: [ch2, small, audit, basin-isolation, evaluator-mismatch, hostile-default, foundation-then-search]
related: [[M-general-basin-overarching-search]], [[ch2-small-floor-14292]], [[ch2-small-audit-2026-05-30]],
  [[E-653-ch2-a1-falsified-truncated-edge-tables]], [[E-701-ch1-eccentric-departure-solver-fix]]
---
# E-702 — Ch2-small: joint (order, schedule) basin audit on the official objective

## Mandate
User (2026-06-22, while the Ch1 E-701 fleet sweep runs): deep audit of Ch2-small re **assumptions,
global solution finding, single-basin blockers** — applying the lens that just produced the Ch1
breakthrough (a downstream evaluator asymmetry made every solver converge to one basin and look like a
ceiling).

## Setup
Bank **112.996 d, rank ~6** (R4 111.76, R3 110.88 → +2.1d, R1 101.65 → +11.3d). 49 nodes; cheap-edge
graph **5.9% dense, 4 components {40,3,3,3}**; ≥3 exception bridges structurally required, bank spends
**5/5** (the max). All ~8 historical methods (E-609 SA/LNS, E-529/E-617 DP-ALNS, beam, cluster+LKH,
iter-LKH, greedy bank) are **one architecture**: order search on a fixed cheap-edge graph with
grid-snapped epochs, scored by a DP proxy. "8 methods converged to 112.996" is *common-substrate*
convergence, not independent confirmation.

## Two Ch1-shaped suspects (both REAL defects, both NON-load-bearing)
1. **DP-vs-official +5.5d offset (E-653).** The DP grid scores the bank order at **118.53** vs official
   **112.996**; the offset is **order-dependent** ⇒ it corrupts the ranking the order search descends,
   and explored orders were never officially re-timed. *Suspect: "no order beats 112.996" was measured
   against a crooked ruler.*
2. **Self-imposed tof floor 0.05d (`ch2_findtransfer_greedy.py:38,56`)** — 50× above the spec
   `min_tof=0.001` (the official `fitness` imposes no such floor). The A1 augment added cheap edges at
   **tof≈0.0245d** *below* this floor, so the walk can never realize them — explaining why the
   corrected table didn't break the floor (E-653). *Suspect: a data fix not mirrored in the consumer.*

## What the audit ESTABLISHED
**(S1, verified) The schedule layer is officially optimal for the bank order — both suspects
neutralized there.** `ch2_s1_freeepoch_retime.py` re-times the bank order against the **official
`kt.fitness`** with **tofs free to min_tof=0.001** (below the 0.05 floor) and **continuous waits**:
256k evals, σ→0, **best = 112.9960 exactly, zero descent**. So neither the 0.05 floor nor the wait
quantization leaves makespan on the table *for the bank order*, and the DP offset doesn't touch the
schedule layer.

**(New this session) The order layer is a genuine LOCAL optimum on the OFFICIAL objective.**
`ch2_audit_jointlocal.py` — for each small order move (all 48 adjacent swaps + 28 short or-opt),
warm-start an **official** CMA retime from the bank's real 112.996 schedule vector (essential: the
official schedule landscape is rugged — a cold/greedy seed gives 161 and CMA can't recover, so only a
warm start fairly evaluates a neighbor). Result over 76 neighbors:
- **75/76 INFEASIBLE; the 1 feasible neighbor = 112.9960 (no descent).** → **NO small order move beats
  112.996 under a free official schedule.**
- The dominant reason for infeasibility is **structural, not search-weakness**: the bank **saturates
  the n_exc=5 exception budget**, so most reorderings create a 6th expensive (>100 m/s) leg and violate
  the official `dv_exception_constraint`. The feasible order-neighborhood is therefore **structurally
  tiny**, and within it the bank is optimal.

## Verdict
Unlike Ch1, **there is no hidden bug that breaks the Ch2-small wall.** The two evaluator defects are
real but not load-bearing. The bank is a genuine **local joint (order, schedule) optimum on the true
objective** — the standing "basin-isolated at 112.996" claim is **upgraded from DP-proxy-based to
official-metric-based**, which is the audit's value (it could have been a proxy artifact, as in Ch1; it
is not). Descent to R3/R1 genuinely requires a **non-local re-interleave** — the time-expanded TD-TSP
(nodes=(city,epoch), edges (i,t)→(j,t+tof) where cheap at THAT epoch), the competitor (TGMA) pipeline,
never built. This is consistent with [[ch2-small-floor-14292]] but now rests on the official objective.

## Caveats (honesty)
- The neighbor test is **local** (small moves, warm start) — it proves local optimality, not global. A
  far re-interleave can still beat 112.996; that is exactly the TD-TSP lever, not contradicted here.
- "Infeasible" = "not shown feasible by a 6k-eval warm CMA," not proven infeasible; but the n_exc=5
  saturation gives a structural reason most neighbors are genuinely infeasible.
- No bank change; nothing submitted.

## Open sub-lever (cheap, distinct from the heavy TD-TSP build)
The bank spends **2 of its 5 exceptions WITHIN components** (only 3 are needed to bridge the 4
components). Reallocating those 2 — a bridge-placement / exception-assignment move the DP-ranked search
under-explored — could free feasibility for faster within-component routing. Small, official-scored,
worth a targeted probe before committing to the TD-TSP build. The +2.1d to R3 is small enough that a
modest structural gain could reach rank 3.

## Methodology
A clean [[M-general-basin-overarching-search]] application with the *opposite* outcome to Ch1: there
the basin-lock was a bug (lever real); here the basin is genuine (lever is a different architecture).
The discipline — test the "ceiling" against the TRUE evaluator, not the proxy/substrate that produced
it — is what distinguishes the two, and is the transferable lesson.
