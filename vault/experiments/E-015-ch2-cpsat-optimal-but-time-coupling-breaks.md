---
id: E-015
type: experiment
status: done
tags: [ch2, cpsat, dead-end, framing]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~140s (CP-SAT 120s + retime)
code: src/esa_spoc_26/ch2_cpsat.py
commit: (committed with this E)
inputs: "small (N=49), edges_small.npz"
outputs: none feasible
env: spoc26 + ortools 9.15
code_dependencies: [src/esa_spoc_26/ch2_cpsat.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 140, peak_memory_mb: 600, cores: 8}
effort_person_hours: 0.5
metrics:
  cpsat_status: OPTIMAL
  static_path: "valid permutation, ≤5 exceptions on isolated-edge graph"
  after_retiming: {dv_c: -36, exc_c: -2, time_c: 0, makespan_d: 200, retimed_exc: 39}
verdict: refutes
---

# E-015 — CP-SAT optimal on the static graph; time-coupling breaks it

## Result

CP-SAT solved the static feasible-edge Hamiltonian-path to
**OPTIMAL** (valid permutation, ≤5 exceptions using each edge's
*isolated* time-optimal Δv). But chronological re-timing
(t_dep ≥ prev arrival, 14-d window) blew **36 of 48 legs past
600 m/s** → infeasible.

## Verdict + analysis (M-002)

**verdict: refutes** *any* static/decoupled formulation for Ch2.
The crux, now proven, is **time-coupling**: an edge's Δv depends on
the *absolute* departure time; a cheap edge at its own optimal
epoch is wildly infeasible at the chronologically-forced epoch, and
the next cheap window can be far (the relative-phasing/synodic beat
period of a pair ≫ the 14-d retime window). Order and timing must
be optimised **jointly**.

Realistic formulations (the genuine Ch2 difficulty / O-002 OR-team
regime):
1. **Time-expanded graph**: nodes = (tomato, time-bucket), arcs =
   feasible transfers between buckets; path visiting each tomato
   once → CP-SAT / MILP over a discretised timeline (large model).
2. **Co-optimising metaheuristic**: LNS/GA over the permutation
   with full-horizon per-leg timing re-solve, official fitness as
   objective.

Both are substantial. T-006 updated; escalating a campaign-level
ROI/expectations decision (Ch1-adv paused, Ch2 deep, ~11 pts banked).
