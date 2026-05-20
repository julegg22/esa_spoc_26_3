---
id: E-025
type: experiment
status: ongoing
tags: [ch2, cma-es, fcmaes, evolutionary, warm-start]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end:
duration_runtime: TBD
code: src/esa_spoc_26/ch2_fcmaes.py
commit: 4875643
inputs: "solutions/upload/small.json (142.99d) as warm-start; argsort encoding"
outputs: TBD
env: spoc26 + fcmaes 2.0.2
code_dependencies: [src/esa_spoc_26/ch2_fcmaes.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: ~7200_planned, peak_memory_mb: 2000, cores: 4}
effort_person_hours: 3.0
metrics:
  warm_start_mk: 142.989
  smoke_4k_evals: 142.989 (no improvement, basin held by best-tracker)
  drift_without_tracker: 731145 (CMA-ES μ drifted into infeasible space)
verdict: ongoing
---

# E-025 — fcmaes / CMA-ES warm-started from 142.99 d

## Rationale (user insight, S-2026-05-20)

The leaderboard submission helper is named `fcmaes` — Dietmar Wolz's
library known for winning ESA ACT optimization competitions on
orbital trajectory + permutation problems. Strong signal that
rank-1/3 use this library; we build the same approach.

Encoding (C-016 argsort): x ∈ ℝ¹⁴⁵
- x[0:48]   = departure times
- x[48:96]  = times of flight
- x[96:145] = real permutation keys, decoded via argsort

Fitness: `kt.fitness` decoded; makespan if feasible; penalty
otherwise (1000 + per-violation magnitude).

## Initial findings (smoke)

| sigma | n_evals | result | observation |
|---|---|---|---|
| 0.02 | 4 000 | 142.989 | best-tracker held warm-start; no improvement |
| 0.02 | 2 000 (no tracker) | **731 145** | CMA-ES μ drifted into infeasible space within iterations |
| 0.005, 0.02, 0.05 | 20 000 each | (timed out before completion) | larger budget needed |

## Diagnosis

The 142.99 d local optimum is **structurally tight in 145-dim**:
- Adjacent samples (σ ≈ 0.02–0.05) almost surely violate
  chronology or Δv constraints.
- CMA-ES's covariance update moves μ toward the BETTER samples
  in each generation. With ALL samples infeasible (high penalty),
  the "better" direction is one of arbitrary infeasibility — μ
  drifts away from x₀ even though x₀ was feasible.
- Without a best-ever-seen tracker, the returned μ is the final
  position after drift — much worse than x₀.

With best-tracker, the returned value is at least 142.989 (x₀),
but CMA-ES still doesn't find a better-feasible point in the local
σ-ball.

## What rank-3 fcmaes runs likely look like (interpretation)

Wolz's published fcmaes recipes for GTOC use:
- 64–512 parallel restarts (not 32)
- 100 000+ evals per restart (not 4 000)
- Sigmas from 0.05 → 0.5 (broad exploration)
- Often **multiple diverse warm-starts** (not just one)
- Wall time: **24–72 h on multi-core machines**

Our 4-core × 30K-eval × 32-retry budget is ≈ 1–2 h — likely
insufficient to break the basin. Larger compute and warm-start
diversity are the next levers.

## Currently running

Background run: `runs/ch2_v3/17_fcmaes_v2.log`, 32 retries × 30 000
evals each on 4 cores, ~1.5–2 h wall expected. Will update verdict
when complete.

## Architectural notes for follow-up

- **Warm-start diversity**: We have only the 142.99d perm as
  feasible seed. Generating 5–20 diverse feasible warm-starts
  (e.g., via multi-bias greedy + insertion-LNS) would let fcmaes
  cover more basins.
- **Constraint handling**: Penalty-based feasibility may waste
  search effort in infeasibility deserts. fcmaes supports
  feasibility-only filters or repair operators.
- **Permutation operators**: argsort encoding has flat plateaus.
  Hybrid (continuous CMA-ES on td/tof + integer LNS on perm) may
  outperform pure continuous search.
