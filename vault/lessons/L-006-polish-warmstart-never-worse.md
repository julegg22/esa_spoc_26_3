---
id: L-006
type: lesson
status: confirmed
tags: [optimization, polish, nlp, warmstart, gotcha]
kind: gotcha
scope: optimization/nlp-polish
severity: serious
confidence: high
created: 2026-05-21
source: "per-leg NLP polish v1 made banked mk WORSE (142.99 → 199.8d)"
related: ["[[C-020-bridge-prefilter]]", "[[C-011-metaheuristic-local-search-routing]]"]
effort_person_hours: 1.5
---

# L-006 — Warm-start every polish from the known-feasible baseline

## The failure

First per-leg NLP polish on Ch2 small (banked 142.99 d) used pure
multi-start Nelder-Mead with generic seeds: a linspace of (td_offset,
tof) values. Each leg's NM found feasible solutions, but those
solutions had LATER arrival than the original-banked timings —
because the multi-start chose convenient feasible windows without
knowledge of the existing-best. Sequential composition propagated
the slip: **142.99 → 199.8 d (60d WORSE)**.

The polish had no idea what "currently banked" was. It treated each
leg as an isolated subproblem and picked whichever feasible (td, tof)
its NM landed on.

## The fix

**Always pre-evaluate the existing-banked (td, tof) as a known
baseline; accept the NM result ONLY if it beats this baseline.**

```python
def optimise_leg(kt, i, j, t_ready, dv_cap, ..., original_td, original_tof):
    # Pre-evaluate original (warm-start anchor)
    best = None
    if original_td is not None and original_tof is not None:
        if feasible(original_td, original_tof):
            best = (original_td + original_tof, original_td, original_tof, dv_o)
    # Also seed NM with the original
    seeds = generic_seeds + [(original_td, original_tof)]
    for seed in seeds:
        r = scipy.optimize.minimize(obj, seed, method="Nelder-Mead", ...)
        if r.x feasible and r.fun < best.arrival:
            best = ...
    return best  # never-worse-than-original
```

Two changes:
1. **Anchor at original**: pre-evaluate it as a known-feasible
   baseline.
2. **Seed NM with original**: ensures NM at least re-finds the
   original if no better basin exists.

## The lesson

Any polish / local-search / refinement that operates on a banked
solution MUST be NEVER-WORSE relative to that solution. Two
techniques:

1. **Baseline anchoring**: pre-evaluate the existing solution; only
   accept improvements.
2. **Warm-start seeding**: include the existing solution as one of
   the optimizer's starting seeds.

Always do BOTH. The optimizer may not converge to the seed; the
anchor ensures we don't accept worse.

## Generalization

Applies to:
- NLP polish (this case)
- LNS destroy/repair (the Or-2-opt + polish pattern; if polish
  worsens, reject)
- Genetic crossover (parent must be evaluated; offspring accepted
  only if better)
- Annealing (acceptance criterion: probabilistic for worse, but
  never overwrite the best-known)

## Impact / scope

This bug invalidated a 5-min run. Recovery: 2-line code fix in
`ch2_per_leg_nlp_polish.optimise_leg`. The corrected version
banked 142.92 d (the polish chain win that subsequently led to
the 274.52 d medium breakthrough).
