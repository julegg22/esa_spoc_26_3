---
id: C-001
type: concept
status: confirmed
tags: [astrodynamics, cr3bp, bcp, ch1, ch3]
scope: astrodynamics/three-body
confidence: high
created: 2026-05-19
sources:
  - "Szebehely, Theory of Orbits (1967) — CR3BP"
  - "Simó et al., 'The bicircular model near the triangular libration points of the RTBP', From Newton to Chaos (1995)"
  - "reference/spoc4_udp/trajectory-matching.py (the campaign's authoritative BCP)"
related: ["[[H-002-ch1-trajectory-greedy]]", "[[O-004-ch1-udp-via-api-correction]]", "[[C-002-delta-v-rocket-equation-loi]]"]
---

# C-001 — The CR3BP and the Bicircular Problem (BCP)

*Primer for non-experts. Why a "tomato transfer" needs more than
high-school physics.*

## Definition

A **two-body problem** (one small craft around one planet) has a
clean closed-form solution: ellipses (Kepler). Add a *third* massive
body and there is **no general closed-form solution** — you must
integrate the motion numerically.

- **CR3BP** (Circular Restricted 3-Body Problem): two big bodies
  (Earth, Moon) circle their common centre of mass on fixed circular
  orbits; a third *massless* body (our spacecraft) moves in their
  combined gravity. "Restricted" = the craft is too light to affect
  the big bodies.
- **BCP** (BiCircular Problem): the CR3BP **plus the Sun**, modelled
  as a third gravity source on its own circular orbit. It is the
  CR3BP with a time-periodic solar perturbation switched on
  (Simó 1995). SpOC4 Ch1-advanced and Ch3 use the BCP.

## Why it matters here

Ch1 *advanced* ("trajectory-matching", `[[H-002-ch1-trajectory-greedy]]`)
scores the *real* Earth-orbit→Moon-orbit transfer mass, and the
transfer must be flown in the **BCP**. There is no analytic shortcut:
we numerically integrate the spacecraft for days of flight. The
official competition UDP (`[[O-004-ch1-udp-via-api-correction]]`)
*defines* the exact BCP; our propagation must reproduce it bit-for-bit
or the server scores the trajectory 0.

## Mechanics

Work in the **synodic (rotating) frame** that turns with the
Earth–Moon line. The huge payoff of this frame:

> In synodic coordinates the **Earth and Moon do not move** — Earth
> sits at (−μ, 0, 0), the Moon at (1−μ, 0, 0), forever. Only the Sun
> sweeps around (angle ω_s·t).

`μ = M_moon /(M_earth+M_moon) ≈ 0.0122` is the mass ratio. Distances
are scaled so Earth–Moon = 1, time so the Moon's period = 2π. The
equations of motion add three effects: gravity of Earth, gravity of
Moon, and **rotating-frame terms** (centrifugal + Coriolis,
the `+x`, `2ẏ` terms). The BCP adds the Sun's pull and a small
"indirect" term. There are five equilibrium points (**Lagrange
points** L1…L5); transfers can ride the low-energy tubes near them
(see "low-energy transfers" in `[[H-002-ch1-trajectory-greedy]]`).

## In practice

We integrate with **heyoka** (adaptive Taylor series, very high
order — the UDP uses tolerance 1e-16). The dynamics are
*non-integrable* and mildly chaotic: tiny changes in the departure
burn or timing can swing the arrival point by thousands of km, which
is exactly why targeting a precise lunar orbit is hard
(`[[C-002-delta-v-rocket-equation-loi]]`). Gotcha learned: the
challenge README's BCP constants were **wrong**; only the official
UDP's constants are valid (`[[L-002-udp-served-via-graphql-not-git]]`).

## References

Szebehely 1967; Simó et al. 1995; the campaign's mirror in
`src/esa_spoc_26/ch1_trajectory.py`.
