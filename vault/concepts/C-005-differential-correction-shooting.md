---
id: C-005
type: concept
status: confirmed
tags: [astrodynamics, numerics, ch1]
scope: numerics/boundary-value-shooting
confidence: high
created: 2026-05-19
sources:
  - "Stoer & Bulirsch, Introduction to Numerical Analysis — shooting methods"
  - "Pernicka/Howell & coworkers — differential correction in the CR3BP"
related: ["[[C-001-cr3bp-and-bicircular-problem]]", "[[H-002-ch1-trajectory-greedy]]", "[[E-006-h002-first-direct-transfer-attempt]]"]
---

# C-005 — Differential correction (the shooting method)

*Primer for non-experts: how you aim a spacecraft when you can only
push it at the start.*

## Definition

A **boundary-value problem (BVP)**: you know where you start (an
Earth orbit) and where you must end (a specific Moon orbit), but the
equations only let you *integrate forward* from a chosen initial
state ("initial-value problem"). **Shooting** turns the BVP into
"guess the launch parameters, fly the trajectory, measure how far
you miss, correct the guess, repeat." **Differential correction** is
the systematic correction step: use the sensitivity of the miss to
each input to compute the adjustment that drives the miss to zero
(Newton's method in several variables).

## Why it matters here

H-002 Step 3 is exactly this: pick the departure burn `DV0`, the
coast time `TOF`, the departure phase, and the Sun phase `t0`;
integrate the BCP (`[[C-001-cr3bp-and-bicircular-problem]]`); the
"miss" is how far the arrival is from the target lunar-orbit radius.
The first naive attempt
(`[[E-006-h002-first-direct-transfer-attempt]]`) varied only `TOF` —
**too few control knobs** — and missed by ~11 000 km. A proper
multi-variable differential corrector is the fix.

## Mechanics

Let `F(p)` = the miss vector as a function of the control parameters
`p` (here `p = [DV0(3), TOF, phase, t0]`). We want `F(p*) = 0`.
Newton iteration: `p ← p − J⁻¹ F(p)`, where `J = ∂F/∂p` is the
**Jacobian** (sensitivities), obtained by finite differences or
variational/state-transition-matrix propagation. Practically we use
`scipy.optimize.least_squares` (robust to more knobs than
constraints and to a poor start). Two failure modes to manage:

- **Sensitivity / chaos**: in the 3-body regime tiny input changes
  blow up downstream (`[[C-001-cr3bp-and-bicircular-problem]]`), so
  the Jacobian is ill-conditioned far from a solution → needs a
  *good seed* and often **continuation** (solve an easy nearby
  problem, then deform it toward the hard one).
- **Discontinuities**: an Earth/Moon impact makes the trajectory
  (and the miss) undefined — handle as an explicit infeasible region.

## In practice

Seeds, best→worst for cislunar: a CR3BP transfer / invariant-manifold
arc, a pykep multi-rev Lambert arc, then plain patched conics (what
E-006 used — weakest). Implementation target:
`src/esa_spoc_26/ch1_trajectory_solve.py` (replace the 1-D TOF scan
with a multi-variable corrector).

## References

Stoer & Bulirsch (shooting); CR3BP differential-correction
literature; campaign nodes H-002 / E-006.
