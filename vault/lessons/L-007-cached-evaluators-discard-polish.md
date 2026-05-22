---
id: L-007
type: lesson
status: confirmed
tags: [optimization, polish, evaluator, gotcha]
kind: gotcha
scope: optimization/local-search + evaluator-design
severity: serious
confidence: high
created: 2026-05-21
source: "big-cluster 2-opt evaluator regression after per-leg polish"
related: ["[[L-006-polish-warmstart-never-worse]]", "[[C-012-earliest-feasible-tof]]"]
effort_person_hours: 1.5
---

# L-007 — Cached evaluators can silently discard local-optimization gains

## The failure

After per-leg NLP polish improved Ch2 small from 142.99 → 142.92 d
(via custom (td, tof) per leg), the big-cluster 2-opt local search
ran on the banked perm and **reported 142.9888 d as its starting
baseline** — not 142.9202 d as expected.

Cause: `walk_perm_chrono(kt, perm)` re-evaluates the perm by
running `find_earliest_transfer` for each leg — i.e., it uses the
default GREEDY (td, tof) per leg, not the polished values. The
polish modified the (td, tof) vector in the banked artifact, but
walk_perm_chrono ignored that and re-greedy-walked from scratch.

Net result:
- 2-opt compared candidates against the WALK-baseline (142.9888),
  not the POLISH-baseline (142.9202).
- All swaps appeared worse than 142.9888 (correctly), so 2-opt
  found "no improvement" — but the actual banked solution was 0.067 d
  BETTER than the baseline 2-opt was using.

## The lesson

If a polish step produces custom (td, tof) that the evaluator
ignores, subsequent search will SILENTLY operate against a degraded
baseline. Two ways the bug appears:

1. **False negatives**: search rejects all improvements (they look
   worse than the polished but better than the walked baseline).
2. **Polish loss**: if structural search then accepts a "best"
   candidate, applying walk_perm_chrono overwrites the polish.

## How to detect

After applying a polish that modifies (td, tof), compute both:
- `mk_walked = walk_perm_chrono(kt, perm)` → uses default greedy timing.
- `mk_polished = polish_eval(kt, perm, custom_times, custom_tofs)`.

If they differ, subsequent local search MUST use `mk_polished` as
baseline — OR you must re-polish after each structural change.

## The fix

Two viable patterns:

**Pattern A — Polish is the FINAL step.** Run structural search
first (combinatorial moves use walked baseline); polish only at the
end on the structural local optimum. No re-polish needed.

**Pattern B — Re-polish after each structural move.** Used by
`ch2_or2_polish.py` for Or-2-opt + post-move polish. Expensive
(~5 s per polish call) but correctly compares against polished
baselines.

For Ch2 small, Pattern A is correct: 2-opt converges first, THEN
per-leg polish.

## Generalization

Applies to any optimizer with a "default" evaluator and a "polish"
that produces non-default state. Examples:
- LP relaxation vs IP solution (polish = IP, default = LP)
- Linear extrapolation vs spline fit (polish = spline coefs)
- Greedy assignment vs Hungarian-matching (polish = matching cost)

In all cases: align the evaluator with the polish, OR sequence
polish strictly after the search.

## Impact / scope

1 hour of confusion debugging "why doesn't 2-opt find improvements
on the banked perm?" Codified as C-017/C-018 by structuring the
medium pipeline as: greedy → cluster insert → per-leg polish (final).
