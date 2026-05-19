---
id: C-007
type: concept
status: confirmed
tags: [astrodynamics, ch1, transfer]
scope: astrodynamics/transfers
confidence: high
created: 2026-05-19
sources:
  - "Curtis, Orbital Mechanics for Engineering Students — Hohmann transfer"
  - "Battin — two-impulse transfers"
related: ["[[C-002-delta-v-rocket-equation-loi]]", "[[C-008-low-energy-ballistic-capture]]", "[[T-005-ch1-advanced-is-a-global-trajopt-problem]]"]
---

# C-007 — Hohmann-like (direct) transfer

*Primer for non-experts: the textbook "fast and simple" way between
two orbits — and why it's a weak baseline here.*

## Definition

A **Hohmann transfer** is the classic minimum-energy *two-impulse*
move between two coplanar circular orbits: one burn to enter an
elliptical "transfer arc" whose far end just touches the target
orbit, one burn to circularise there. "Hohmann-**like**" =
direct two/three-impulse transfers in the same spirit (short, one
big departure burn, coast, one arrival burn), even when orbits are
non-coplanar or the dynamics aren't pure two-body.

## Why it matters here

For Ch1-advanced (Earth-orbit→Moon-orbit, `[[C-002-delta-v-rocket-equation-loi]]`)
a direct Hohmann-like transfer is the obvious first idea and what we
attempted first (E-006…E-010). It is **fast** (~3–6 days) and
conceptually simple, but it arrives at the Moon **hyperbolically**
(high relative speed) so the lunar-orbit-insertion burn is large.
Total ΔV ≈ 3.9 km/s ⇒ ≈ 892 kg delivered — *positive but weak*
versus the rank-competitive band. The challenge ships the **Sun**
and a 200-day horizon precisely so the better answers are
*not* Hohmann-like but
[[concepts/C-008-low-energy-ballistic-capture|low-energy captures]]
([[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem|T-005]]).

## Mechanics

Transfer ellipse semi-major axis `a_t=(r₁+r₂)/2`; departure burn
`Δv₁=√(μ(2/r₁−1/a_t))−v_circ(r₁)`; arrival burn circularises at
`r₂`. Time of flight ≈ half the ellipse period
`π√(a_t³/μ)`. In a 3-body setting the arrival burn balloons because
the target body's gravity + frame motion make the relative arrival
velocity large unless the geometry is tuned (which Hohmann ignores).

## In practice

Use as a *seed*/baseline only. In Ch1-advanced it is dominated by
low-energy transfers; in Ch2 (Lambert legs, `[[C-006-lambert-problem-and-orbital-tsp]]`)
the analogous "go straight there fast" leg is often Δv-infeasible —
waiting/timing matters.

## References

Curtis; Battin; campaign nodes E-006…E-010, T-005.
