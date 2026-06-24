---
id: O-012
type: observation
status: partial — adjacent bug only
tags: [ch1, trajectory, residual, ultrathink, bug-diagnosis, superseded]
source: "Ultrathink session 2026-05-23 PM after Ch3 banking"
created: 2026-05-23
referenced_by: ["[[H-007-bannach-ddd-targeted-refinement]]"]
---

> **⚠️ POST-2026-05-24 NOTE:** This observation diagnosed a real but
> ADJACENT bug (under-determined residual in solve_transfer_back).
> The *actual* root cause of Ch1 trajectory's poor mass was
> `solve_arrival_dv` rejecting eccentric Moon orbits. See
> LESSONS-LEARNED for the full diagnosis. The 14.82 kg result
> this note explained is technically correct, but the conclusion
> "needs research-grade fix" is wrong post-eccentric-orbit-fix.


# O-012 — Ch1 trajectory's "20km/s monsters" trace to under-determined residual

## The bug

`ch1_trajectory_solve.solve_transfer_back` (the validated backward-
shooting pipeline from T-005) uses this least_squares residual:

```python
return [(np.linalg.norm(r_ef) - aE) / L]
```

**1 equation, 5 unknowns** (nu, t_arr, dv2x, dv2y, dv2z). The
least_squares finds A solution but the resulting (e, i) are
arbitrary, and the SPEED at the radius-matched point is determined
by backward-propagation dynamics — usually MUCH higher than the
Earth orbit's circular velocity.

## Empirical confirmation

Diagnostic on (idE=0, idL=0) — Earth orbit 0 (LEO, aE=6.545 Mm,
e=0, i=0) → Moon orbit 0 (LLO, aL=1.838 Mm, e≈0):

| seed result | r_err (m) | a_back (Mm) | e_back | i_back | dv0 |
|---|---|---|---|---|---|
| best radius match | 0.123 | **213.1** | **0.975** | **3.14 (retro!)** | None (mismatch) |

The point has |r| = a_E (within 12 cm) but the two-body equivalent
orbit has semi-major axis 213 Mm (33× larger), eccentricity 0.975,
and π inclination. The backward state IS at LEO altitude but with
escape-velocity-class speed.

`solve_departure_dv` then computes `v_orb = sqrt(μ/a) ≈ 7.8 km/s`
and `dv0 = v_back - v_orb`. If v_back has magnitude ~30 km/s (escape
class), |dv0| ≈ 20+ km/s — T-005's "monsters".

## Why a 3-equation residual didn't help

Tried `[(r-a_E)/L, e-e_E, i-i_E]` (5 unknowns, 3 equations). Result:
least_squares failed to find points matching all three constraints
simultaneously — residual norm 1.9e8 (190 Mm error). The BCP
backward-propagation manifold from "Moon orbit arrival" doesn't
geometrically intersect "Earth orbit identity" within the search
bounds.

## Physics interpretation

A direct Hohmann-like Earth-to-Moon transfer:
- Apogee at Moon distance, perigee at LEO altitude
- Energy E = -μ/(2a) where a = (r_LEO + r_LLO_with_Moon_pos)/2
- Departure velocity ≈ 10.7 km/s (apogee at Moon, perigee at LEO)
- LEO orbital velocity ≈ 7.8 km/s
- ΔV departure ≈ 10.7 - 7.8 = **2.9 km/s** ✓ POSITIVE MASS

So the transfer EXISTS physically. But finding it via random-seed
backward shooting is impossible because:
- Backward from Moon arrival: spacecraft enters Earth gravity well
  with full kinetic energy of fall (~11 km/s = escape speed at LEO)
- Specific Earth-orbit-matching points are MEASURE-ZERO in this
  6-DOF trajectory family

The correct approach is **forward** Lambert seeding: pick LEO
departure point, solve Lambert to Moon arrival in Earth-centered
inertial frame, then refine in BCP.

## What's needed (multi-day build)

1. **Lambert-seeded forward shooting**: 2-body Lambert gives initial
   guess; differential corrector in BCP refines. Standard
   astrodynamics technique. Build cost: 1-2 days.
2. **3-impulse Sun-assisted (WSB)**: low-energy ballistic capture
   via Sun-Earth L1 region. Build cost: 3-5 days.
3. **Patched-conic mass screen**: analytical Hohmann estimate per
   (idE, idL) → top-K → BCP refinement. Build cost: 1 day.

Out of scope for this session. Documented for future work.

## Code artifact

`src/esa_spoc_26/ch1_traj_v2.py` — attempted 3-equation residual
fix; killed due to slow convergence and no positive-mass results.
Preserved for reference.
