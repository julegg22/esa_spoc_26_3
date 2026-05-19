---
id: E-006
type: experiment
status: done
tags: [ch1, astrodynamics, bcp]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~10s (Earth0→Moon0, 8 phases)
code: src/esa_spoc_26/ch1_trajectory_solve.py
commit: 9297d49
inputs: "Earth orbit 0, Moon orbit 0 (official UDP data)"
outputs: none (no valid transfer produced)
plots: []
seed: "8 departure phases × 11-pt TOF scan + 1-D least_squares"
env: spoc26 (heyoka/pykep, official-mirror oracle)
code_dependencies:
  - src/esa_spoc_26/ch1_trajectory_solve.py
  - src/esa_spoc_26/ch1_trajectory.py
compute: {cpu_seconds: 10, peak_memory_mb: 400, cores: 1}
effort_person_hours: 0.6
metrics:
  step1_earth_moon_state_gen: "verified exact (round-trip passes 1e-6)"
  step2_arrival_dv_solver: "verified (on-orbit |DV2|~0; perturbed→23.4 m/s, match restored)"
  step3_direct_shooter_E0M0:
    valid_transfer: false
    best_lunar_closest_approach_m: 1.114e7
    loi_band_radius_m: 1.838e6
    note: "reaches lunar vicinity (~11000 km) but not the tight LOI radius"
verdict: inconclusive
---

# E-006 — H-002 first direct-transfer attempt (Earth0→Moon0)

## Setup / procedure

Patched-conic-seeded direct 2-impulse: TLI from the Earth orbit
(prograde, apo→Earth–Moon distance), BCP coast, LOI via the verified
`solve_arrival_dv`. Search = 8 departure phases × 11-point TOF scan
+ 1-D `least_squares` on the coast-time scale; scored by the
official-mirror `fitness`.

## Results

- **Step 1** (exact Earth/Moon orbit state generators) and **Step 2**
  (arrival ΔV / LOI solver) — independently **verified** (isolation
  tests pass the official 1e-6 tolerance).
- **Step 3** (direct shooter) — **no valid transfer**. Best lunar
  closest-approach miss ≈ **1.114e7 m (~11 000 km)** vs the required
  LOI band ≈ 1.838e6 m. The trajectory reaches the lunar vicinity
  but a patched-conic seed + 1-D TOF scan cannot hit the tight
  near-circular orbit-insertion radius.

## Verdict + analysis

**verdict: inconclusive** (H-002 not refuted — the *naive direct
seed* is, the hypothesis' approach is not). Diagnosis: the BCP coast
does not naturally arrive at the precise lunar-orbit radius;
controlling only `TOF` is too few degrees of freedom. Need a real
**cislunar differential correction**: multi-variable shooting on the
full DV0 vector + TOF + departure phase + t0 (Sun phase) targeting
`|r_moon| = aL` (1 constraint, ≥3 free), or a stronger seed (a
CR3BP transfer / pykep Lambert-arc / manifold). Pieces 1 & 2 are
solid, so the remaining work is isolated to Step 3 targeting.
Next: implement the differential corrector; re-attempt; on success,
sweep (e,l) pairs → discounted-mass matrix → reuse the
`ch1_matching` MIP-LNS assignment.
