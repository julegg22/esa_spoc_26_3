---
id: C-008
type: concept
status: confirmed
tags: [astrodynamics, ch1, bcp, transfer]
scope: astrodynamics/low-energy-transfers
confidence: high
created: 2026-05-19
sources:
  - "Belbruno & Miller, 'Sun-Perturbed Earth-to-Moon Transfers with Ballistic Capture' (1993)"
  - "Koon, Lo, Marsden, Ross — Dynamical Systems, the Three-Body Problem and Space Mission Design"
related: ["[[C-001-cr3bp-and-bicircular-problem]]", "[[C-007-hohmann-like-direct-transfer]]", "[[T-005-ch1-advanced-is-a-global-trajopt-problem]]"]
---

# C-008 — Long, Sun-perturbed low-energy ballistic capture

*Primer for non-experts: the "slow but almost free" way to the Moon
— and (per T-005) the technique Ch1-advanced is designed around.*

## Definition

A **low-energy transfer** reaches the Moon by exploiting the
gravity of a *third/fourth body* (here the **Sun**, via the
bicircular model `[[C-001-cr3bp-and-bicircular-problem]]`) instead
of brute engine thrust. The spacecraft is flung far out (toward the
Sun-influenced **weak stability boundary**), where a tiny nudge from
solar gravity reshapes the orbit so that, on return, it is
**ballistically captured** by the Moon — arriving so slowly that the
lunar-orbit-insertion burn is *near zero*. Belbruno's 1991
Hiten rescue is the canonical real example.

## Why it matters here

`[[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem|T-005]]`:
Ch1-advanced ships the Sun (bicircular, not plain CR3BP), a
**200-day** horizon, and tight tolerances — exactly the ingredients
that make low-energy capture both *possible* and *necessary*. A
Hohmann-like direct transfer (`[[C-007-hohmann-like-direct-transfer]]`)
spends ~1 km/s on insertion (weak mass); a ballistic capture spends
≈0, so far more tomato mass survives the rocket equation
(`[[C-002-delta-v-rocket-equation-loi]]`). This is the designers'
"analytical-capacity hurdle": recognise you must use the four-body
dynamics, not muscle a direct burn.

## Mechanics

Cost: a moderate trans-lunar injection raises apogee to ~1–1.5 ×
the Earth–Moon distance; the **Sun's tidal perturbation** over a
long arc (tens–hundreds of days) raises perilune / lowers the
Moon-relative energy until the trajectory is temporarily captured
(Jacobi-energy just below the L1/L2 gateway). Hallmarks: **long
TOF** (≈ 60–130 d), exterior excursion, near-tangential lunar
arrival, capture sensitive to Sun phase (epoch `t0`).

## In practice

Found by **global trajectory optimisation** over long TOF with the
Sun phase as a key variable, *not* by local single-shooting (which
finds only fast hyperbolic arrivals — E-006…E-011). The official
`fitness` already rewards low ΔV, so it is the right objective for a
global optimiser exploring the long-TOF, Sun-phased regime
(deferred H-002 revival, T-005).

## References

Belbruno & Miller 1993; Koon-Lo-Marsden-Ross; campaign T-005.
