---
id: E-008
type: experiment
status: done
tags: [ch1, astrodynamics, bcp, numerics]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: "~27s run + instrumented single-pair trace"
code: src/esa_spoc_26/ch1_trajectory_solve.py
commit: (committed with this E)
inputs: "Earth orbit 0 → Moon orbit 0 (official UDP oracle)"
outputs: "geometrically valid transfer; mass negative (rejected)"
plots: []
seed: "patched-conic; 4 EA starts; tol-matched cached integrator (1e-16)"
env: spoc26
code_dependencies:
  - src/esa_spoc_26/ch1_trajectory_solve.py
  - src/esa_spoc_26/ch1_trajectory.py
compute: {cpu_seconds: 27, peak_memory_mb: 500, cores: 1}
effort_person_hours: 0.9
metrics:
  pipeline_validated_end_to_end: true
  tracked_vs_official_perilune_agreement_m: 5e-4
  arrival_radius_miss_m: 2.24
  official_match_tol_check: {da_over_L: 5.83e-9, de: 1.46e-7, di: 9.05e-10}
  loi_dv2_m_s: 21127.5
  delivered_mass_kg: -495
  fitness: "+500 (negative mass → rejected by f<0 gate)"
verdict: inconclusive
---

# E-008 — H-002 pipeline validated; ΔV regime wrong (LOI 21 km/s)

## Setup / procedure

`solve_transfer_dc` with the cached integrator tol matched to the
official 1e-16 (the E-007→fix). Instrumented a single E0→M0 start
through every stage (Earth match → DC → official-propagate refine →
`solve_arrival_dv` → `udp.fitness`).

## Results — the turning point

- **Integrator-tol fix worked**: tracked perilune vs official-propagate
  perilune now agree to 5e-4 m (was diverging > km at tol 1e-12).
- **Geometrically valid transfer achieved**: arrival radius within
  2.24 m of aM; official `_match_orbit` passes with huge margin
  (|Δa|/L=5.8e-9, |Δe|=1.5e-7, |Δi|=9e-10, all ≪ 1e-6); no impact;
  `udp.fitness` evaluates. **The whole validation pipeline is
  proven against the official scorer.**
- **ΔV regime is wrong**: LOI `|DV2|` = **21 127 m/s** ⇒
  mass = e^(−ΔV/311/g₀)·5000−500 ≈ **−495 kg** (negative) ⇒
  fitness `+500` (rejected by the `f<0` positive-mass gate).

## Verdict + analysis

**verdict: inconclusive** — but this is the key milestone: H-002's
*validation* problem is solved; only *trajectory optimisation*
remains. The perilune-only objective finds a **fast hyperbolic
flyby grazing radius aM**, not a slow capture, so circularisation
costs ~21 km/s. Real LLO insertion should be ~0.6–1 km/s.

**Next (E-009):** make the corrector minimise **arrival ΔV**, not
just hit the radius — add an arrival-speed residual (drive Moon-
relative speed → circular speed `√(μ☾/aM)`) and/or seed a proper
apoapsis-matched / low-energy transfer (C-002 / C-005). Target a
*positive*-mass transfer (fitness < 0), then sweep (e,l) →
discounted-mass matrix → reuse the MIP-LNS assignment
([[concepts/C-004-mip-and-mip-lns]]).
