---
id: L-013
type: lesson
status: confirmed
tags: [methodology, evaluator, audit, ch2, trajectory, gotcha, fundamental]
kind: methodology
scope: evaluator-design + audit-discipline
severity: critical
confidence: high
created: 2026-06-23
source: "E-709 audit concluded Ch2-large is a 'genuine wall / moonshot'; E-710 overturned it by probing evaluator tof-resolution (cheap bands ~0.002d, scans at 0.01d saw 11% of cheap edges)"
related:
  - "[[C-031-grid-quantization-mismatch]]"
  - "[[C-033-fast-faithful-oracle]]"
  - "[[C-034-time-aware-beam-narrow-window-tdtsp]]"
  - "[[L-012-solver-assumption-audit-before-research-grade-verdict]]"
  - "[[foundation-then-search-methodology]]"
  - "[[M-applying-methodology-triggers]]"
effort_person_hours: 4.0
---

# L-013 — An audit can rule out every named flaw and still miss the evaluator's resolution

## The failure (and the recovery)

Ch2-large's giant stranded every construction at ~367/601. A disciplined
four-experiment audit (E-709) tested the obvious culprits and **refuted
each with measurements**:

1. adjacency under-sampled? → 0/300 false negatives, graph correct.
2. bank-order just needs re-timing? → 931 d, no collapse.
3. wrong urgency proxy (degree vs deadline)? → deadline ordering *worse*.
4. a static global solver would do better? → strands at 10/601.
5. is rank-1 even near-optimal? → assignment LB 14.8 d (loose).

Conclusion drawn: **"no straightforward flaw — the wall IS the problem;
rank-1 is an all-or-nothing moonshot."** That conclusion was *rigorous
about everything it tested* — and still wrong. The next day (E-710),
auditing the **evaluator itself** revealed the cheap-tof feasible bands
are ~0.002 d wide, while every faithful walk scanned tofs at 0.01–0.05 d
→ the evaluator was **blind to ~89 % of cheap edges**. With a fine
evaluator + a time-aware beam, the "wall" gave way at **558/601 @ 283 d**
(under rank-1's per-leg rate). See [[C-031-grid-quantization-mismatch]]
(the "phantom wall" section).

## Why the audit missed it

The audit probed the **search** (adjacency, ordering, global vs greedy)
and the **problem** (LB) — every axis EXCEPT the **resolution of the
evaluator** the experiments themselves ran on. All five experiments
shared the same coarse-tof evaluator, so they were **mutually consistent
and all blind in the same way**. Agreement across experiments felt like
convergence on truth; it was a shared instrument error. (Compare
[[L-012-solver-assumption-audit-before-research-grade-verdict]]: there
too, many failing experiments shared one downstream feasibility bug.)

## The rule

> Before accepting any "saturated / plateau / genuine wall / no-flaw"
> verdict, **audit the resolution of the evaluator the verdict rests
> on.** A wall observed through a coarse instrument may be the
> instrument, not the terrain.

Concretely, add an **evaluator-resolution check** as a first-class step
of any plateau/exhaustion audit (it belongs next to the per-instance
check in [[M-applying-methodology-triggers]]):

1. **Measure the feasible-band width** in every *continuous* search
   variable (here: tof). A cheap way: take known-feasible points (a fine
   reference table, the bank's own legs) and bisect outward until
   infeasible.
2. **Confirm the working scan step ≤ ¼ band width.** If the step is
   coarser, the evaluator silently drops most feasible moves.
3. **Cross-check the online evaluator against an independent fine
   reference.** If a fine table marks an edge cheap and the online walk
   can't re-find it, the walk — not the problem — is the wall.
4. **Distrust cross-experiment agreement when experiments share an
   evaluator.** Vary the instrument, not just the search.

## Why it matters beyond this instance

The reflex on a large competitor gap is to reach for a heavier
*algorithm* ([[basin-overarching-search]], cluster+LKH). Here the gap was
an *evaluator* defect: ~10 lines of resolution, not a new paradigm. The
cheapest high-information probe was the one the audit skipped — auditing
its own measuring stick. This is the [[foundation-then-search-methodology]]
maxim sharpened: *validate the evaluator's RESOLUTION, not just its
correctness, before declaring the search exhausted.*

## Retraction note

The E-709 memory/journal verdict ("genuine wall, moonshot, hold rank-2")
is **superseded** for the resolution claim; the time-ordering structure
it described is real, but it is threadable once the evaluator sees the
edges. Annotated in [[ch2-large-time-ordering-wall]] (memory) per
[[M-general-retraction-annotation]].
