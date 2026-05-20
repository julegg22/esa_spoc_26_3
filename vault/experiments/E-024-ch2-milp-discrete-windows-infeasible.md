---
id: E-024
type: experiment
status: done
tags: [ch2, milp, highs, time-limit, architectural-finding]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "~30 min wall (MILP Phase 1: 600s + warm-start: 1200s)"
code: src/esa_spoc_26/ch2_milp_pwl.py
commit: (pending)
inputs: "windows2d_small.npz (v3, 18651 windows); solutions/upload/small.json (142.99d) for warm-start"
outputs: TimeLimit, no feasible
env: spoc26 + highspy (HiGHS)
code_dependencies: [src/esa_spoc_26/ch2_milp_pwl.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 1800, peak_memory_mb: 3000, cores: 4}
effort_person_hours: 2.0
metrics:
  model_size_vars: 19814
  model_size_arcs: 966
  model_size_windows: 18651
  phase1_status: TimeLimit_600s_no_feasible
  warmstart_status: TimeLimit_1200s_no_feasible
  warmstart_compatibility: incompatible_grid
verdict: refutes (discrete-window MILP equivalent to CP-SAT for this problem)
---

# E-024 — MILP Phase 1 (discrete windows) also fails; warm-start incompatible

## Result

Built MILP equivalent of v3 multi-window CP-SAT:
- Variables: 19 814 (966 x_{i,j} + 18 651 y_{i,j,k} + 49 T_v + 49 s_v +
  49 e_v + 49 u_v MTZ + 1 mk)
- Constraints: flow, MTZ sub-tour, big-M chronology
  (T_j = td_k + tof_k iff y_{i,j,k}=1), exception ≤5, makespan
- Solver: HiGHS via `highspy`

| run | budget | status | feasible found |
|---|---|---|---|
| Phase 1 (cold) | 600 s | TimeLimit | no |
| Phase 1 (warm-start with 142.99d) | 1200 s | TimeLimit | no |

## Why the warm-start failed (the architectural finding)

The 142.99d solution uses **NLP-refined continuous (td, tof) per leg**.
Round-to-closest-window when constructing the warm-start gives
(td_k, tof_k) on the GRID. The MILP's chronology constraint
`T_j == td_k + tof_k` then implies T_j must take grid values exactly
— but the warm-start's T_v values are the continuous arrivals.
HiGHS rejects the warm-start as infeasible *for the discrete model*,
even though the underlying physical trajectory IS feasible.

This is a **fundamental impedance mismatch**: discrete-window MILP
(or CP-SAT) can never accept the NLP-refined solutions that the
greedy + 2-opt pipeline produces.

## What this means for the architectural roadmap

The "Phase 1 = discrete-window MILP" path is **closed for this
problem**, just as discrete CP-SAT was (E-018→E-021). The remaining
architectural options:

1. **True PWL MILP** with continuous td_{i,j}, tof_{i,j} as variables
   and PWL approximation of the Δv(td, tof) surface per arc. This
   removes the grid lock-in and is compatible with NLP-style
   solutions. **Build cost: 4–7 days; likely needs commercial MILP
   solver (Gurobi) for the resulting ~50K-variable model.**
2. **Domain-specific custom heuristic** combining cluster-bridge
   enumeration + targeted exception-replacement LNS + per-leg
   makespan-NLP. ~2–3 days build, modest improvement (5–10d).
3. **Continuous-time NLP optimization with permutation as outer
   loop**, e.g., (i) outer LNS/SA over permutations, (ii) inner
   NLP per-leg with full (td, tof) freedom. The current SA already
   does this; the limit is the per-leg objective (first-feasible-tof
   vs makespan-min) and the move set's poor feasibility rate.

## Position vs goal

Banked: **142.99 d** (ratio 1.279 to rank-3). The find_transfer +
cluster-insertion + 2-opt + SA + cluster-first + discrete MILP
pipeline is now fully explored; advancing materially toward rank-3
(111.76 d) is a multi-day architectural investment, not a few-hour
tuning.
