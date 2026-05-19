---
id: E-010
type: experiment
status: done
tags: [ch1, astrodynamics, bcp, numerics, dead-end]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~17s
code: src/esa_spoc_26/ch1_trajectory_solve.py
commit: (committed with this E)
inputs: "Earth orbit 0 → Moon orbit 0"
outputs: none (diverged, ~3481 km)
seed: "pykep two-body Lambert (Earth→Moon centre) + 2-residual DC"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_trajectory_solve.py]
compute: {cpu_seconds: 17, peak_memory_mb: 500, cores: 1}
effort_person_hours: 0.5
metrics:
  best_dr_moon_m: 3.481e6
  same_failure_axis_as: E-009
verdict: refutes
---

# E-010 — Lambert seed also diverges; forward single-shooting is the wrong method

## Result

A proper pykep two-body Lambert departure velocity (aimed at the
lunar geometry) feeding the 2-residual (radius + arrival-speed)
BCP corrector still **diverges** to ~3 481 km — essentially the
E-009 outcome. Seed quality is not the issue.

## Verdict + analysis (M-018 step-back)

**verdict: refutes** the whole *forward single-shooting from
departure* family for the low-ΔV transfer (E-006…E-010 cluster on
this shared axis). Single shooting over a multi-day arc in the
non-integrable BCP is ill-conditioned: a generic seed + local
Gauss-Newton cannot satisfy "precise LLO radius AND low arrival
speed" simultaneously — classic shooting stiffness
([[concepts/C-005-differential-correction-shooting|C-005]] caveat).

**Not lost:** the validation pipeline is fully proven
([[experiments/E-008-h002-pipeline-valid-dv-regime-wrong|E-008]]) —
exact state gen, scorer-matched BCP propagation, official
`_match_orbit`/`fitness`, `solve_arrival_dv`. The *method* of
finding the transfer is what must change.

**Re-ground options (user domain):**
1. **Backward shooting from the LLO arrival** — build the exact
   LLO state (free Ω,ω,ν), propagate *backward* in the BCP; the
   hard insertion constraint is then automatic; only the Earth-end
   match remains (also a generous 384 m a-tol, free phasing).
2. **Global/multiple-shooting** — pygmo (MGA-1DSM-style) or a
   multiple-shooting/collocation transcription instead of single
   shooting.
3. **Reframe** — accept the cost and pursue a structured
   low-energy family directly.

Recommendation: (1) backward shooting — makes the binding
constraint exact by construction; standard for orbit-insertion
design. Escalated to the user.
