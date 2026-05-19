---
id: E-014
type: experiment
status: done
tags: [ch2, lambert, dead-end]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: "3 router variants"
code: src/esa_spoc_26/ch2_kttsp.py
commit: (committed with this E)
inputs: "small (N=49), edges_small.npz (138 cheap edges, 0 dead-ends)"
outputs: none feasible
seed: "greedy_wait; structure-aware route; corrected route (no truncation, nan-guarded)"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 400, peak_memory_mb: 400, cores: 1}
effort_person_hours: 0.6
metrics:
  greedy_wait: infeasible
  structure_aware_router: infeasible
  corrected_router_no_bug: infeasible
verdict: refutes
---

# E-014 — Constructive Ch2 routers refuted; need a constraint solver

## Result

Three constructive variants — no-wait greedy (E-012), greedy-with-
waiting, and the cheap-graph-guided router with per-leg windowed
re-timing — all fail to produce a feasible tour on `small`, even
after fixing a candidate-truncation bug and nan-guarding the
retime (M-002 "audit own code first"). The feasible structure
*exists* (138 cheap edges, 0 dead-ends, rank-3 = 111.76 d).

## Verdict + analysis

**verdict: refutes** the constructive-heuristic family for Ch2.
Confirmed (M-002): Ch2 is a **constrained Hamiltonian-path with a
≤5-exception budget on a sparse, time-windowed cheap-edge graph** —
constructive/greedy methods strand because feasibility is a *global*
property (the order must keep the remaining graph completable). This
is the regime for an exact **constraint/OR solver** (OR-Tools
CP-SAT circuit/path + exception-count + makespan, on the
precomputed edge graph), which O-002 indicates the strong Ch2 teams
(an OR group) use. Requires an `ortools` env addition + a CP model
build → escalated (tooling + ROI decision). Method takeaway:
[[takeaways/T-006-ch2-method-time-optimal-edges-plus-routing|T-006]].
