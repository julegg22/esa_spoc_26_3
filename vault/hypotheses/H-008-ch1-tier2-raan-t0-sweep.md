---
id: H-008
type: hypothesis
status: draft
tags: [ch1, trajectory, tier-2, raan, argp, sun-phase, optimization]
parent: "[[lessons/L-012-solver-assumption-audit-before-research-grade-verdict]]"
created: 2026-05-24
priority: 2
mode: design

claim: >
  Sweeping (raan_e, argp_e, t0_sun) — the 3 angular DOF we've held at
  zero throughout the campaign — lets the solver find lower-dv
  trajectories for inclined-orbit pairs by aligning nodes (raan)
  and exploiting Sun-gradient assist (t0).

falsifiable_prediction: >
  For the top 100 banked pairs (post-current-sweep), a 4×4×4 grid
  over (raan_e, argp_e, t0_sun) — applied as additional polish —
  improves median per-pair mass by ≥10% (from ~2000 to ~2200 kg).

estimated_effort_h: 4-8
expected_points: 4-6 (Ch1 trajectory advance toward rank-1)
---

# H-008 — Ch1 Tier 2: sweep (raan_e, argp_e, t0_sun) for additional gains

## Rationale

After the eccentric-orbit-fix sweep (S-2026-05-24), we have a
solver delivering ~2000 kg per pair using:
- `raan_e = 0`, `argp_e = 0` — Earth orbit orientation fixed.
- `t0_sun = 0` — Sun phase fixed at 0 (origin of synodic frame).

These are 3 free DOF the UDP doesn't constrain (the orbit
elements check is only on `(a, e, i)`). Sweeping them should:

1. **raan_e**: rotates the Earth orbit's plane in the synodic
   frame. For inclined moon-orbit targets, choosing raan_e so the
   Earth orbit's ascending node coincides with the line of
   intersection between the two orbital planes minimizes the plane-
   change cost.

2. **argp_e**: rotates the position of perigee within the orbital
   plane. For elliptic Earth orbits (eE > 0), this controls where
   the spacecraft starts its departure — choosing perigee aligned
   with the optimal Hohmann-like departure direction minimizes dv0.

3. **t0_sun**: rotates Sun's gravitational gradient relative to the
   trajectory. For some phases, Sun acts as a free apoapsis kick
   (mini-WSB effect). For others, Sun perturbs the trajectory away
   from feasibility.

## Implementation

Add a polish step after Tier 1A/1B:
- For each banked transfer, run scipy Nelder-Mead on
  `(raan_e, argp_e, t0_sun)` with the inner loop re-solving the
  trajectory (Lambert+3D-DC) for each (raan, argp, t0).
- Initial simplex: small perturbations around current values.
- Per-pair cost: ~30 Nelder-Mead evals × ~10s inner = 5 min.
- For 200 banked pairs: 200×5/8 workers = 2 hours.

## Risk

- Per-pair gains may be marginal (5-10%) if the (eccentricity, low
  inclination) of most banked pairs already gives near-optimal
  trajectories.
- Compute cost is ~2-4 hours for 200 pairs; lower priority than
  Tier 1B (3-impulse) which has higher expected gain.

## Decision criteria

Apply this hypothesis AFTER Tier 1A + 1B + 1C are exhausted. If
bank is still below rank-1 (473k kg), this provides additional
incremental gains.
