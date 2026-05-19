---
id: E-011
type: experiment
status: done
tags: [ch1, astrodynamics, bcp, numerics]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~16s
code: src/esa_spoc_26/ch1_trajectory_solve.py (solve_transfer_back)
commit: (committed with this E)
inputs: "Earth orbit 0 → Moon orbit 0"
outputs: none valid (geometry solved, ΔV uncontrolled)
seed: "backward from exact LLO; LOI ΔV + ν + t_arr free; 3 TOF × 6 seeds"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_trajectory_solve.py]
compute: {cpu_seconds: 16, peak_memory_mb: 500, cores: 1}
effort_person_hours: 0.8
metrics:
  earth_radius_err_m: 0.123
  earth_a_tol_m: 384
  llo_arrival: "exact by construction"
  valid_positive_mass_transfer: false
verdict: inconclusive
---

# E-011 — Backward shooting solves the geometry; ΔV still uncontrolled

## Result

Backward shooting (M-018 pivot, user-chosen): LLO arrival exact by
construction; backward-propagate to Earth. Earth-side radius driven
to **0.123 m** of aE (tolerance 384 m) — geometry now solved on
*both* ends. Still **no positive-mass transfer**.

## Verdict + analysis — the crystallised finding

**verdict: inconclusive** for H-002, but E-006…E-011 now give a
definitive structural conclusion:

- The **validation pipeline is fully solved** (E-008): exact state
  gen both bodies, scorer-matched BCP propagation, `_match_orbit`/
  `fitness`, LOI/Earth solvers.
- **Geometric targeting is solved both ways**: forward shooting hits
  the LLO radius to ~2 m (E-008); backward shooting hits the Earth
  radius to 0.12 m (E-011).
- **The binding difficulty is low-ΔV transfer design.** Pure
  geometric shooting (any direction) finds high-energy solutions
  because ΔV is not constrainable in a stiff single-shot least-
  squares (adding it diverges, E-009). Every geometry-valid transfer
  so far has huge burns → negative delivered mass.

This is a *global trajectory-optimisation* problem, not a targeting
bug — see [[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem|T-005]].
The validated pipeline is a durable asset (reusable as a trajopt
objective). Escalating a re-prioritisation decision to the user
(H-002 effort vs untouched Ch2).
