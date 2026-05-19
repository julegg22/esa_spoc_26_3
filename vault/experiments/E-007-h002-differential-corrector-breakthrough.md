---
id: E-007
type: experiment
status: done
tags: [ch1, astrodynamics, bcp, numerics]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~24s (Earth0→Moon0, 4 EA starts)
code: src/esa_spoc_26/ch1_trajectory_solve.py (solve_transfer_dc)
commit: (committed with this E)
inputs: "Earth orbit 0 → Moon orbit 0 (official UDP data)"
outputs: none yet (no valid transfer — perilune precision short)
plots: []
seed: "patched-conic DV0/TOF; 4 departure phases; t0=0"
env: spoc26 (cached heyoka BCP integrator tol 1e-12 + official propagate tol 1e-16)
code_dependencies:
  - src/esa_spoc_26/ch1_trajectory_solve.py
  - src/esa_spoc_26/ch1_trajectory.py
compute: {cpu_seconds: 24, peak_memory_mb: 500, cores: 1}
effort_person_hours: 0.7
metrics:
  step3_direct_shooter_E006: {best_dr_moon_m: 1.114e7}
  step3_diff_corrector_E007: {best_dr_moon_m: 8.131e1}
  improvement: "~5 orders of magnitude (1.1e7 → 81 m)"
  loi_band_m: "≈ ±1 (aM·eM + 1 m slack; near-circular eM~1e-7)"
  valid_transfer: false
verdict: inconclusive
---

# E-007 — Differential corrector: 1.1e7 m → 81 m (perilune-precision gap)

## Setup / procedure

`solve_transfer_dc`: cached BCP integrator (tol 1e-12) tracks the
closest lunar approach; `least_squares(method="trf")` on
[DV0(3), TOF] drives that to aM; then an **official-propagate**
(tol 1e-16) Brent refine on T1 for scorer-consistency; DV2 via the
verified `solve_arrival_dv`; multi-start over Earth-departure phase.
Patched-conic seed. Fixes vs E-006: real multi-variable correction
(not a 1-D TOF scan); `lm`→`trf` (underdetermined); official-prop
consistency.

## Results

| stage | best \|Δr_moon\| |
|---|---|
| E-006 direct shooter | 1.114e7 m |
| **E-007 diff corrector** | **8.131e1 m** |

~5-order-of-magnitude improvement in 24 s. Still **no valid
transfer**: the Moon orbits are near-circular (eM ~ 1e-7), so the
feasible arrival-radius band is ≈ ±1 m; 81 m misses it and
`solve_arrival_dv` correctly returns None.

## Verdict + analysis

**verdict: inconclusive** (H-002 strongly de-risked, not closed).
The corrector *works* — it reliably delivers the craft to the
target lunar radius to ~80 m over a multi-day 3-body coast. The
residual gap is **perilune-localization precision**, a small
well-posed numeric problem, *not* trajectory design:

- the DC residual uses a *sampled* min-distance (n discrete steps)
  → quantization noise stalls `least_squares` ~80 m;
- T1-only refine cannot beat the trajectory's true perilune-vs-aM
  gap — that gap must be closed by DV0.

Next (E-008): replace sampled-min with a **precise perilune solve**
(Brent on |r_moon|(t) to sub-metre) inside the DC residual so the
gradient is smooth, and let the corrector drive true perilune
radius → aM within ±1 m. Expect the first valid transfer, then
sweep (e,l) → discounted-mass matrix → MIP-LNS assignment.
Concept: [[concepts/C-005-differential-correction-shooting]].
