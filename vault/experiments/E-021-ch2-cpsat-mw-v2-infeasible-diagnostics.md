---
id: E-021
type: experiment
status: done
tags: [ch2, cpsat, time-coupling, diagnostics, decisive-finding]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "<10 min (5 diagnostic CP-SAT solves + greedy probes)"
code: src/esa_spoc_26/ch2_cpsat_mw.py + ad-hoc CP-SAT diagnostics
commit: (committed with this E)
inputs: "windows2d_small.npz (v2 joint td-tof, K=12, 9431 windows)"
outputs: 5 diagnostic CP-SAT statuses
env: spoc26 + ortools
code_dependencies: [src/esa_spoc_26/ch2_cpsat_mw.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 600, peak_memory_mb: 1200, cores: 4}
effort_person_hours: 1.5
metrics:
  static_graph_hampath_with_exc5_only: OPTIMAL  # graph topology OK
  sum_of_min_tofs_hampath: 73.0_d  # static-min-tof Σ ≤ 200 by ~3×
  v2_mw_cpsat_horizon_200d: INFEASIBLE_proven_in_~1min
  v2_mw_cpsat_horizon_1000d: UNKNOWN_in_2min
  greedy_no_wait_first_start: returns_None
  cheap_windows_at_tof_le_4d: 55_pairs_of_2352
  exc_windows_at_tof_le_4d: 615_pairs_of_2352
verdict: refutes
---

# E-021 — Multi-window CP-SAT v2 INFEASIBLE: discrete (td, tof) point-windows are too sparse for 200d chronology

## Diagnostics run (5)

| diagnostic | constraint relaxed | result |
|---|---|---|
| static Ham-path + ≤5 exc | drop chronology + time | **OPTIMAL** (graph OK) |
| min-Σtof Ham-path + ≤5 exc | drop chronology, pick per-arc min-tof window | **OPTIMAL, Σtof = 73 d** |
| **v2 MW CP-SAT @ 200d** | **full chronology + ≤5 exc + ≤200d** | **INFEASIBLE proven** |
| v2 MW CP-SAT @ 1000d | chronology, relaxed horizon | UNKNOWN (timeout) |
| greedy no-wait | constructive baseline | None (dead-end on first start) |

## Why infeasible — the window-coverage gap

v2 windows in 8 tof-slices [0.5, 1, 2, 4, 8, 16, 24, 36]:

| tof | ≤100 wins | (100,600] wins |
|---|---|---|
| 0.5 | **5** | 276 |
| 1.0 | **17** | 231 |
| 2.0 | **40** | 194 |
| 4.0 | **61** | 329 |
| 8.0 | 105 | 1439 |
| 16.0 | 167 | 2387 |
| 24.0 | 170 | 1911 |
| 36.0 | 154 | 1945 |

Cheap (≤100) windows are heavily biased to long-tof (med tof=16d).
**Only 55 of 2352 ordered pairs have any cheap window at tof≤4d**;
615 pairs have any (≤600) window at tof≤4d. So short-tof navigation
mostly relies on exception edges — but ≤5 exceptions cap that.

## The fundamental issue — continuous vs discrete time

Each window forces `T_j = td_k + tof_k` *exactly*. The forced arrival
T_j at j then must satisfy `T_j ≤ td_{k'}` for some chosen out-window
from j. With finite K=12 windows per pair (4×3 td×tof bins), the
*specific* T_j values are scattered and rarely align with any out-
window's td. **Discrete point-windows over-constrain the CP-SAT model.**

The leaderboard (rank-3 = 112 d) proves feasibility exists; the
**competitors must use either**:

1. **Continuous (td, tof) optimization** (NLP per leg + permutation
   search via local-LNS or ML),
2. A vastly denser discrete grid (K ≫ 12, finer tof resolution),
3. A different parametrisation entirely (e.g., MGA / impulsive
   linear-programming-with-trajectory-segments).

## Decision impact — heavy compute target reframed (again)

Updated ranking (high → low marginal value):

| target | marginal value | rationale |
|---|---|---|
| **Continuous-time formulation** (NLP per leg + permutation LNS) | **HIGHEST** | Lifts the discrete-grid coverage gap; matches leaderboard reality. Higher build cost than CP-SAT (~1 day) but addresses the binding constraint. |
| Much denser v3 window precompute (K=30+, tof step 0.5d) | MEDIUM | Possibly enough; cheap to try (~30 min compute). Cap is K, not tof breadth. |
| Continuous Δv ≤ 600 PWL constraint | MEDIUM | CP-SAT with PWL approximation of Δv(td, tof) surface per arc. ~2× build cost. |
| Edge-search resolution (E-019: refuted) | ZERO | flat. |

## What the user gets from the 6-hour window

**Yes — we now know where heavy compute pays:** *not* on edge-search,
*not* on single-tof multi-window (E-020), *not* on joint-tof
multi-window v2 (this E). The actual heavy-compute target is the
**continuous-time per-leg optimization framework** (NLP / least-squares
Lambert refinement) coupled with a permutation search (LNS / GA over
permutations). This **inverts the previous T-008 ranking**:

- T-008's "Multi-window CP-SAT" target → **refuted** in this E.
- The right approach is the **opposite**: solve the per-leg continuous
  problem exactly, search the permutation space metaheuristically.

This is concrete actionable knowledge for the post-window investment.
