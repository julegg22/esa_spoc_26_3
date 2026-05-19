---
id: E-009
type: experiment
status: done
tags: [ch1, astrodynamics, bcp, numerics]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~20s
code: src/esa_spoc_26/ch1_trajectory_solve.py
commit: (committed with this E)
inputs: "Earth orbit 0 → Moon orbit 0"
outputs: none (diverged)
seed: "patched-conic; 2-residual least_squares (radius + arrival speed)"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_trajectory_solve.py]
compute: {cpu_seconds: 20, peak_memory_mb: 500, cores: 1}
effort_person_hours: 0.4
metrics:
  approach: "add arrival-speed residual (→ circular speed) to the DC"
  best_dr_moon_m: 3.45e6
  vs_E008_radius_only_m: 2.24
  outcome: "multi-objective diverged — far worse than radius-only"
verdict: refutes
---

# E-009 — ΔV-aware DC diverges from a patched-conic seed (M-018)

## Result

Adding a "Moon-relative speed → circular speed" residual to the
corrector (to kill the 21 km/s LOI of E-008) made `least_squares`
**diverge**: best radius miss 3.45e6 m vs E-008's 2.24 m. The two
objectives (close radius vs slow arrival) conflict, and from a
patched-conic (fast, direct) seed local correction cannot reach a
slow-arrival transfer.

## Verdict + analysis

**verdict: refutes** the "patch the existing direct shooter to also
minimise ΔV" path. Diagnosis (M-018 step-back): the *seed/transfer
structure* is wrong, not the optimiser. A fast direct transfer
*inherently* arrives hyperbolic; a low-LOI transfer requires the
incoming arc to be apoapsis-matched to the lunar orbit (slow
arrival) by construction — a Lambert-arc or CR3BP/low-energy seed,
not a patched-conic prograde kick + local correction.

**Established (not lost):** the validation pipeline is proven
end-to-end ([[experiments/E-008-h002-pipeline-valid-dv-regime-wrong|E-008]]):
exact Earth/Moon state gen, BCP propagation tol-matched to the
scorer, official `_match_orbit` + `fitness`, and `solve_arrival_dv`
all correct. Only the **transfer-construction seed** is open.

This triggers an M-018 re-ground with the user on transfer strategy
(astrodynamics-domain fork) rather than further solo iteration.
