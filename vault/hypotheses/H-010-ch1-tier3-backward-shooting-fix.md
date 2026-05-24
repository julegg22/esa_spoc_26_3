---
id: H-010
type: hypothesis
status: draft
tags: [ch1, trajectory, tier-3, backward-shooting, residual-fix, bug]
parent: "[[O-012-ch1-traj-under-determined-residual]]"
created: 2026-05-24
priority: 3
mode: design

claim: >
  Fixing the under-determined residual in `solve_transfer_back`
  (O-012: 1 equation, 5 unknowns → 3 equations matching
  (aE, eE, iE)) unlocks pairs that forward shooting fails for —
  particularly highly inclined Earth orbits where the Lambert seed
  geometry is degenerate.

falsifiable_prediction: >
  After fixing the residual, backward shooting succeeds for ≥30%
  of pairs with iE > 0.5 rad (highly inclined Earth orbits). These
  pairs were not banked by forward-shooting (Tier 1) and contribute
  +50,000-100,000 kg to the total when added.

estimated_effort_h: 4-6
expected_points: 2-4 (incremental Ch1 trajectory toward rank-1)
---

# H-010 — Fix solve_transfer_back's under-determined residual

## Background

O-012 documented that `ch1_trajectory_solve.solve_transfer_back`
has a residual `[(np.linalg.norm(r_ef) - aE) / L]` — 1 equation,
5 unknowns (nu, t_arr, dv2_x, dv2_y, dv2_z). The least_squares
finds A solution but the resulting (e, i) are arbitrary, and the
two-body equivalent often has e ≈ 0.975 and i ≈ π (retrograde).

## The fix

Replace the residual with full state2earth match:

```python
def resid(p, _OmM=OmM, _tof=tof):
    nu, t_arr = p[0], p[1]
    dv2 = p[2:5]
    ...
    el = state2earth(d_state)
    return [(el[0] - aE) / L, el[1] - eE, el[2] - iE]
```

3 equations, 5 unknowns — under-determined but well-conditioned.
Pick the solution with minimum |dv2|.

## Why this matters post-Tier-1

Forward shooting (Lambert+3D-DC) works well for:
- Pairs where Earth orbit's plane is close to Moon orbit's plane
- LEO/MEO Earth orbits

Forward shooting STRUGGLES with:
- Highly inclined Earth orbits (iE > 0.5)
- Long transit times where BCP propagation has high cumulative error

Backward shooting (which we have in code but with broken residual)
starts from the LLO ARRIVAL state and shoots BACKWARD. The arrival
state is much more deterministic (we control LOI burn exactly).
The forgiving boundary is the Earth side (384m a-tolerance, but
also tolerant to large dv on the post-orbit-match correction).

Combined forward+backward gives complementary coverage of the
160k pair space.

## Implementation

1. Fix the residual in `solve_transfer_back` (~30 lines of code).
2. Build a `solve_pair_back` wrapper similar to `solve_pair_forward`.
3. Add to the production sweep as alternative solver per pair.
4. Rebank with results from BOTH solvers (take max mass per pair).

## Risk

- The backward shooting may STILL fail for hard pairs even with
  3-residual.
- Or it may give SAME masses as forward shooting (redundant).

Mitigation: run on a 10-pair test set first; deploy only if
≥30% give complementary results.

## Decision criteria

Apply AFTER Tier 1 sweep+polish completes AND we know which pairs
are still unsolved. If those unsolved pairs have high inclination,
this hypothesis is the cheap targeted fix (~4-6h).
