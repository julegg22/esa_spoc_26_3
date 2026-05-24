---
id: H-009
type: hypothesis
status: draft
tags: [ch1, trajectory, tier-3, wsb, sun-assisted, ballistic-capture, ambitious]
parent: "[[lessons/L-012-solver-assumption-audit-before-research-grade-verdict]]"
created: 2026-05-24
priority: 3
mode: research

claim: >
  Weak Stability Boundary (WSB / Belbruno) Sun-assisted ballistic-
  capture transfers eliminate the LOI burn (~800 m/s) for select
  (idE, idL) pair geometries where the spacecraft can enter the
  Earth-Moon-Sun L1/L2 region weakly and drift into LLO captured by
  Moon's gravity alone.

falsifiable_prediction: >
  For at least 50 (idE, idL) pairs out of the 400 banked transfers,
  a properly-tuned WSB trajectory delivers ≥3500 kg per pair
  (vs ~2000 kg for forward Hohmann), pushing total bank above
  600,000 kg (well above rank-1 cutoff 473k kg).

estimated_effort_h: 16-32
expected_points: 14+ (Ch1 trajectory rank-1 with margin)
---

# H-009 — Ch1 Tier 3: WSB / Sun-assisted ballistic capture for select pairs

## Rationale

Standard Hohmann + LOI: ~3950 m/s for LEO→LLO. mass = 870 kg.
WSB-style with Sun assist: the spacecraft enters Earth-Moon L2
region weakly, Sun gravity bends trajectory to enter Moon SOI at
near-zero excess velocity, Moon captures ballistically. No LOI
burn needed. Effective dv ~2200-2700 m/s → mass 2500-3500 kg per
pair.

Belbruno's 1991 Hiten rescue used this. Modern lunar missions
(SMART-1, ARTEMIS) leverage it. Standard astrodynamics textbook
content.

## Implementation phases

### Phase 1: WSB feasibility map (~6h)
Compute Sun-gradient gradient maps in BCP synodic frame for various
t0 values. Identify which (idE, idL) pair geometries have feasible
WSB trajectories. Filter to ~50-100 pairs.

### Phase 2: WSB trajectory generation (~10-20h)
For each feasible pair, search:
- Long TOF: 80-120 days (vs Hohmann ~5d).
- t0_sun: optimal Sun phase for assist (~quarter of synodic period).
- ea_dep: aligned with L2 manifold entry.
- Multi-shoot DC for stability in the chaotic L2 region.

### Phase 3: Polish & bank
Standard Tier 1A polish on top of WSB seeds. Hungarian rebank
with both Hohmann and WSB pairs.

## Risk

- WSB requires CAREFUL handling of L1/L2 chaotic dynamics. Sensitive
  to initial conditions. May not converge for many pair geometries.
- 80-120 day TOFs reduce LTL cap factor `(HORIZON - dt) * cld`. For
  some idD with low cld, the cap binds even at low rocket-eq dv.
- Belbruno's original work took years to develop. Even a "simple
  implementation" is 1-2 weeks if done from scratch.

## Recovery if fails

If WSB doesn't work, the 200,000-500,000 kg from Tier 1+2 is still
within rank 3-4. Rank 1 may be unreachable without WSB — but that's
the ambition target, not the required goal.

## Decision criteria

Apply AFTER Tier 1 + Tier 2 are exhausted AND we have time budget
for 16-32h additional work. WSB is the path to rank-1 with margin.

## References

- Belbruno (1987): "Lunar capture orbits, a method of constructing
  Earth-Moon trajectories and the lunar GAS mission."
- Belbruno, E., & Miller, J. (1993): "Sun-perturbed Earth-to-Moon
  transfers with ballistic capture."
- Koon, Lo, Marsden, Ross (2008): "Dynamical Systems, the Three-
  Body Problem and Space Mission Design" — manifold-based design.
