---
id: L-009
type: lesson
status: confirmed
tags: [methodology, m-003, m-006, pivot, gotcha]
kind: methodology
scope: research-process/family-inventory
severity: critical
confidence: high
created: 2026-05-22
source: "user pushback 2026-05-22 on Ch2 large 'pipeline doesn't scale' conclusion"
related: ["[[M-003-approach-family-inventory]]", "[[M-006-idle-pivot-on-unmet-targets]]", "[[O-010-m003-family-rethink-after-claimed-exhaustion]]"]
effort_person_hours: 2
---

# L-009 — Pipeline failure ≠ problem impossibility

## The failure (in reasoning)

After Ch2 large greedy_findxfer (with parallel multi-start) ran 2.25h
without completing, I concluded:

> "Ch2 large: pipeline doesn't scale to n=1051. Would need
> hierarchical clustering + supernode decomposition (not built
> tonight)."

…and went to "idle heartbeat" autonomous-loop ticks instead of
launching the hierarchical decomposition I had just identified.

User pushback was correct: **a single-family failure is NOT a
problem-impossibility signal**. It's a SIGNAL that family-inventory
must pivot. Specifically:

- "greedy_findxfer + LNS doesn't scale" is a finding about
  **greedy_findxfer + LNS**.
- The problem itself has known-orthogonal angles (hierarchical,
  bi-directional, spectral, coarse-MILP).
- Per M-003 (and now M-006), the next action is to launch the
  orthogonal family, not idle.

## The lesson

When ONE family of methods fails on a target:

1. **Resist generalization**: "pipeline doesn't scale" is a
   family-specific statement, not a problem-statement.
2. **Re-run M-003 inventory**: list orthogonal families. At least
   one is usually under-explored.
3. **Launch the highest-ROI orthogonal family immediately**, do
   not gate on user direction (per standing "never wait" rule).
4. **Document the family-failure**, not the problem-failure: "X
   family doesn't scale here; trying Y family next."

## What helped me see it

User prodding (essentially: "stop conflating one-family-failure
with problem-impossibility"). The fact that I had ALREADY listed
orthogonal angles in O-010 but failed to launch them is the
specific methodology gap. Codified as M-006.

## Generalization

Applies to any research/engineering loop where:
- One approach has been tried and failed.
- The problem statement is not specifically "X must use approach Y."
- Multiple orthogonal approaches exist.

Examples:
- "OLS regression doesn't converge" → not "regression is
  impossible"; try ridge/lasso/quantile/spline/NN.
- "Greedy heuristic fails at scale" → not "TSP unsolvable at
  scale"; try decomposition/MILP/CP-SAT/RL.
- "Single GPU OOMs" → not "training infeasible"; try
  gradient accumulation/sharded data/multi-GPU.

The conceptual lift = naming the FAMILY of methods correctly.
"Pipeline" is dangerously ambiguous — be specific: "greedy +
LNS family", "MIP family", "barrier IP family". Then pivot to a
named different family.

## Impact / scope

One full session of effort almost lost to premature idle. The
hierarchical decomposition that was the right answer (C-019)
took ~30 min to build. The cost of the methodology violation
= a multi-hour delay + user pushback.
