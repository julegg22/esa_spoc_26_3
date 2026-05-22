---
id: L-008
type: lesson
status: confirmed
tags: [workflow, computational, gotcha, planning]
kind: gotcha
scope: workflow/background-runs + estimation
severity: warning
confidence: high
created: 2026-05-21
source: "Or-2-opt + polish 6h estimate; hierarchical greedy_insert × 901 nodes"
related: ["[[L-004-verify-before-background-launch]]"]
effort_person_hours: 4
---

# L-008 — Estimate evaluator-cost × candidate-count BEFORE launching

## The failure (multiple instances)

1. **Or-2-opt + per-candidate polish**: launched with filter
   threshold `walked_mk ≤ walk_baseline + 0.1` admitting ~100
   candidates × ~5 s polish = ~500 s/pass × ~10 passes = ~80 min.
   Reality: ran 33 min before killing, no improvements found.
2. **Hierarchical decomp v1 greedy_insert × 901 missing nodes**:
   each `greedy_insert_node` does a full walk per position. 150
   walks at start, growing → ~540k total walks × 10 s = ~1500
   hours. Killed after a few minutes.
3. **Multi-cluster insert size-3 cluster on n=181 partial**: 6
   orderings × 173 positions × ~2 s walk = ~35 min for just THE
   3-cluster. Total small-cluster phase took ~50 min.
4. **Ch2 large multi-start 6 workers**: each greedy takes ~1.5 h
   on n=1051; 6 in parallel → 1.5 h wall. Ran 2.25 h before
   killing.

## The lesson

Before any background launch, estimate three numbers:

1. **N_cand**: how many candidates / iterations / configurations
   the loop will process.
2. **T_eval**: wall time per candidate evaluation.
3. **Filter ratio f**: fraction of candidates that survive cheap
   filters and reach expensive evaluation.

Then: **expected wall = N_cand × T_eval × f** (or for sequential
expansion: N_eval = N₁ × T₁ + N₂ × T₂ + …).

If the result is > 30 minutes, either:
- Add a cheaper prefilter (see C-020 bridge-prefilter).
- Reduce N_cand by sub-sampling (e.g., top-K candidates only).
- Parallelize (mp.Pool, internal — per L-004).
- Don't launch; redesign the loop.

## The estimation checklist

```
Before launching a background job:
[ ] Wrote down N_cand
[ ] Wrote down T_eval (measure ONE, multiply)
[ ] Wrote down filter ratio (or "assume all pass")
[ ] Computed expected wall = N × T × f
[ ] If > 30 min: redesign with prefilter / sub-sample / parallel
[ ] If > 4 hours: only launch if no shorter path exists
```

## Cheap prefilter ideas

- **Bridge-prefilter (C-020)**: pre-walk once; O(1) check per
  candidate.
- **Distance LP**: a relaxed-cost lower bound; reject if even the
  LB exceeds current best.
- **Constraint sniff**: pre-check the tightest constraint (e.g.,
  exception budget).
- **Symmetry breaking**: if candidates {a, b} = {b, a}, skip half.

## Generalization

Anti-pattern: "let's see how it goes" launches. Pro pattern: budget
before launch, kill on overrun, retry with redesign.

The cost of getting this wrong = wasted wall-time + emotional drain
on the next launch. Cumulative across a campaign, can be a
multi-day loss.

## Impact / scope

Roughly 6-10 hours of wasted compute across 4 instances in this
campaign. Codified now to prevent recurrence.
