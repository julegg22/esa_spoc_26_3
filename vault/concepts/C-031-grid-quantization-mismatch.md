---
id: C-031
type: concept
status: confirmed
tags: [methodology, discretization, precompute, dp, ch2, trap]
scope: methodology/numerical
confidence: high
created: 2026-06-08
sources:
  - "Internal: E-541 medium DP-on-coarse-table 380.93 d vs walk 274.52 d"
  - "Internal: E-519 small DP-on-0.5d-quantum F1 failure mode"
related: ["[[C-026-dp-on-time-expanded-graph]]", "[[E-029-ch2-cpsat-lb-tightening]]", "[[M-general-foundation-then-search]]"]
---

# C-031 — Grid quantization mismatch (the trap)

*The pitfall we hit on medium. A precompute "fine enough by intuition"
can be too coarse for the instance scale, and the DP-on-coarse can give
WORSE results than the broken greedy evaluator it was meant to replace.*

## Definition

For DP on a time-expanded graph (see [[C-026-dp-on-time-expanded-graph]]), the **precomputed
Lambert table** must have:
- Time quantum Δt sufficient to capture optimal departure times.
- Tof grid step Δtof sufficient to capture optimal tofs.

If either is too coarse for the instance scale, **most cells in the
table are marked infeasible**, even when fine-grained continuous-t
Lambert would find them feasible. The DP then can express only highly
suboptimal schedules.

**The trap**: a coarse table's "infeasibility rate" can look acceptable
in aggregate (cheap density 9 %), yet the bank's actual schedule may
land entirely in infeasible cells. DP-on-coarse gives a worse mk than
walk_perm_chrono (which uses continuous t).

## The Ch2 medium case (E-532 vs E-541)

E-531 built a coarse medium table at Δt = 0.5 d × Δtof ≈ 0.245 d:
- Precompute: 25 h on 4 cores
- Cells: 32 580 pairs × 1000 t × 50 tof = 1.6 B
- Cheap density per cell: 9.12 %
- Cheap density on bank-perm cells (where it MATTERS): **catastrophically low**

E-532 DP on coarse table:
- Walk_perm_chrono on bank: 274.52 d
- DP on bank: **380.93 d (+106 d)**
- Verdict: F1 — coarse grid too coarse

E-540 built a per-leg fine table at Δt = 0.1 d × Δtof ≈ 0.075 d:
- Precompute: 13 min on 4 cores (only 180 bank-perm pairs)
- Cells: 180 legs × 5000 t × 160 tof = 144 M
- Cheap density on bank legs: **94.21 %**

E-541 DP on fine per-leg table:
- DP on bank: **228.97 d (−45.54 d vs walk)**
- The methodology works when given proper resolution.

## Why "intuition" fails

The audit (2026-05-30 §4 D4) noted that our tof grid floor (0.025 d
in fine tables) is 25× the spec dt_min (0.001 d). For Ch2 small, this
was OK: the 0.05 d t-quantum and 0.05 d tof step gave 94 % feasible
density on bank-relevant cells.

For Ch2 medium (horizon 500 d, n=181) with the SAME absolute t-quantum
of 0.5 d (= 10× coarser per absolute unit) and a coarser tof step,
the relative resolution is wildly insufficient. **The scaling factor
between small/medium isn't just n²; it's also horizon/n_legs.**

## How to size the precompute

Two heuristics that work:

1. **Per-leg tof distribution**. Compute walk_perm_chrono on bank,
   look at the histogram of bank tofs. If most are < 1 d, the tof
   grid step should be ≤ 0.05 d. If they're 1-5 d, ≤ 0.1 d. If
   they're 5-15 d, ≤ 0.25 d.

2. **Sample 5-10 bank cells against fine Lambert**. Pick random
   (i, j, t, tof) from bank's schedule, query the coarse table.
   If most lookup cells are infeasible (but the actual Lambert at
   continuous t is feasible), the grid is too coarse.

## Mitigations when full fine precompute is intractable

For medium (where full fine table is ~10 days on 4 cores) and large
(months), choose targeted precomputes:

- **Per-leg precompute on bank**: 180 pairs × fine grid. Only enables
  DP on bank perm, no ALNS. Used in E-540 (13 min, −45 d gain).
- **Pair-keyed curated subset**: select ~5000 promising pairs (cheap-
  feasible at coarse + top-K exc-promising) and fine-precompute those.
  ALNS restricted to perms using only these pairs. Used in E-542.
- **Hybrid table**: fine for important pairs, coarse for the rest.
  DP marks legs as fine/coarse during reconstruction. Untested.

## Detection / warning signs

- **DP optimum WORSE than walk_perm_chrono** on the same perm.
  Always check this before trusting DP results.
- **Bank cells mostly infeasible** in the precomputed table. Compute
  `np.isfinite(cheap[i, j, round(t_bank/q)])` for each bank leg; if
  many are False, the table is too coarse for bank's schedule.
- **DP cheap density on bank pairs ≪ 50 %**. Healthy fine tables
  show > 80 % on bank pairs.

## In practice

- `scripts/ch2_e526_precompute_ultrafine.py` — small ultrafine
  reference (0.05 × 0.05). Good.
- `scripts/ch2_e531_precompute_medium.py` — coarse medium (0.5 ×
  0.245). **Trap.** Don't use the DP from this table.
- `scripts/ch2_e540_medium_bank_pair_fine.py` — per-leg fix.
- `scripts/ch2_e542_medium_fine_pair_set.py` — curated pair subset.

## The online-evaluator manifestation — the "phantom wall" (E-710, 2026-06-23)

The same root cause (tof step too coarse for the feasible band) bites a
SECOND place — not the DP table, but the **online search/construction
evaluator** — and there its symptom is far more dangerous: it
manufactures a **phantom structural wall** that a whole audit can
mistake for a property of the *problem*.

**Ch2 giant case.** Every faithful construction (greedy, shorttof_walk,
SA retimes) scanned tofs at 0.01–0.05 d. But the giant's cheap-tof bands
are **~0.002 d wide** (E-710 M0b: a 0.01 d scan finds the cheap tof only
**11 %** of the time; the cached 1d table, built fine, is 100 % faithful
and sees them). So the online evaluator was **blind to ~89 % of cheap
edges**. Consequences:

- Greedy stranded at 367/601 and a four-experiment audit (E-709)
  concluded a *genuine* time-dependent wall ("no easy flaw, moonshot").
- The dense-precompute beam's "overfit" (orders looking 0.3 d/leg but
  "retiming" to 1099 d) was substantially a **coarse-tof RETIMING
  artifact**, not a real overfit — the retimer stepped over the band.

Once the evaluator was made fine (sub-band verify, [[C-033-fast-faithful-oracle]]),
a time-aware beam threaded **558/601 @ 283 d**
([[C-034-time-aware-beam-narrow-window-tdtsp]]), overturning the "wall."
See [[L-013-evaluator-resolution-phantom-wall]].

**Detection (add to the warning signs above):**
- Before trusting any "construction strands / saturates / hits a wall"
  verdict, **measure the feasible-band width** in each continuous
  variable and confirm the scan step is ≤ ¼ of it. Take a handful of
  *known-feasible* points (a fine table, the bank) and check the online
  evaluator re-finds them at its working resolution. If it misses most,
  the wall is an artifact, not the problem.
- An aggregate "cheap density looks fine" can coexist with the online
  walk seeing almost none of it — always test at the point level
  ([[M-applying-methodology-triggers]] saturated/plateau trigger).

## Lesson for future challenges

When applying [[M-general-foundation-then-search]] to a new instance:
- The first diagnostic is the DP-on-bank check. If DP > walk, abort
  and refine resolution.
- A "good for small" grid is rarely "good for medium" — scale the
  quantum proportionally to horizon/n_legs.
- A "good for medium" grid is rarely tractable for large. Prepare
  fallback strategies (cluster decomposition, sparse precompute,
  on-demand Lambert).

## References

- E-029 (small DP first pass at 0.5 d, 152 d) — F1 trap on small first.
- E-030 (small with 0.05 d ultrafine) — fixed.
- E-532 — medium F1 trap.
- E-541 — medium fixed.
