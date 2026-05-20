---
id: E-026
type: experiment
status: done
tags: [ch2, milp, bannach, time-expanded, highs, infeasible]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "~30 min (4 MILP runs at dt=4, 8 + diagnostic 5-node test)"
code: src/esa_spoc_26/ch2_bannach_milp.py
commit: (with this E)
inputs: "windows2d_small.npz (18651 arcs); time grid dt ∈ {4, 8} days"
outputs: kInfeasible (with exc budget) / kTimeLimit (without)
env: spoc26 + highspy (HiGHS 1.x)
code_dependencies: [src/esa_spoc_26/ch2_bannach_milp.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 700, peak_memory_mb: 1500, cores: 4}
effort_person_hours: 3.0
metrics:
  encoding_test_5node_synthetic: OPTIMAL (mk=40d, correct)
  dt8_with_exc_budget: kInfeasible (7.7s)
  dt4_with_exc_budget: kInfeasible (47.7s, after sign + snap fixes)
  dt4_without_exc_budget: kTimeLimit (300s, no feasible found)
verdict: refutes
---

# E-026 — Canonical Bannach time-expanded MILP: encoding correct, HiGHS struggles

## Trigger

Per O-009 (M-005 external intel survey) — Bannach/Acciarini/Izzo
(IAC 2024) define the canonical KTSP encoding as ILP on a
time-expanded network. Our prior MILP attempt (`ch2_milp_pwl.py`,
E-024) used MTZ + window-binaries — wrong formulation per Bannach
paper. This experiment rebuilds correctly per the paper.

## Encoding (Bannach §3, our implementation)

- Vertices V = A × T (n=49 tomatoes × n_t time points; dt=4 or 8 d)
- Arcs: E_C coasting (α, t)→(α, t+1) + E_T transfer (α, t)→(β, t')
  from precomputed `windows2d_small.npz`
- Per-(α, t) flow: in − out + (s[α] if t=0) − (e[α] if t=n_t−1) = 0
- Σ s[α] = 1, Σ e[α] = 1 (one start, one end)
- Departure: Σ xfer-out + e[α] ≥ 1 for each α
- Makespan: mk ≥ t' · x for each xfer arc terminating at t'
- Exception budget: Σ x[arc, dv>100] ≤ 5
- Objective: min mk

## Encoding-correctness verification

**5-node synthetic test** (line graph 0→1→2→3→4, dv=50, tof=10 d):
- Status: **kOptimal**, mk = 40 d, start=0, end=4 — **correct**
- Confirms the encoding works on a feasible instance

## Real-instance results (n=49)

| dt | exc budget | n_xfer | n_vars | status | wall | obj |
|---|---|---|---|---|---|---|
| 8 | yes | 15877 | 17201 | kInfeasible | 7.7 s | inf |
| 4 | yes | 18651 | 21200 | kInfeasible | 47.7 s | inf |
| 4 | **no** | 18651 | 21200 | kTimeLimit | 300 s | inf (no feasible) |

## Interpretation

**With exception budget**: HiGHS proves infeasibility quickly. The
snapped graph at dt=4 doesn't admit a 49-node Hamiltonian path with
≤5 exception arcs.

**Without exception budget**: HiGHS doesn't find a feasible solution
in 300 s either (the LP relaxation has fractional solutions; integer
search is exhaustive).

Per O-009 Table 1: Gurobi solved |A|=20, |T|=41 in **5.89 s** while
HiGHS took **19.56 s** (3.3× slower). For |A|=20, |T|=41 with
exception budget HiGHS would likely take ≫100 × 19 s = many hours.
For our n=49 (~6× more arcs than |A|=20 ref), HiGHS is **likely
beyond practical reach** without Gurobi licence.

## Why our 142.99 d feasible doesn't translate to MILP feasibility

The 142.99 d solution uses **continuous (td, tof)** per leg, with
many short-tof arcs (tof = 0.05, 0.45, 0.55 d). Snapping these to a
dt=4 d grid:
- Original arc: leg 30 at (td=143.5, tof=0.5, dv=536) — exception bridge
- Floor td → t_idx = 35, grid[35] = 140
- Ceil arr → tp_idx = 36, grid[36] = 144
- Snapped arc: (i, 35) → (j, 36) with tof_snapped = 4 d

The Δv at the snapped (td=140, tof=4) would likely be VERY different
(higher) from the original 536 m/s. So the snapped arc's recorded
Δv = 536 is **fictional** — at the snapped (td, tof), the actual
ΔV(140, 4) is unknown without recomputing.

This means: even if the MILP found a "feasible" solution on the
snapped graph, the decoded trajectory in continuous time would have
DIFFERENT actual Δv values and might be infeasible per the official
fitness function.

## Recommendation

**Path 1 (still highest leverage)**: ask Julian about HRI's SpOC3
method. HRI won SpOC3 with global score 78.444 (vs fcmaes's 68.667).
What method did HRI use?

**Path 2 (MILP) is now refuted with HiGHS** for the 49-node instance:
either requires Gurobi (commercial, not available per L-002) or a
much smarter formulation (DDD per Bannach §5, which we haven't
implemented).

**Path 3 (fcmaes-at-scale) is empirically blocked**: 32 retries × 30K
evals × diverse warm-starts converged at 142.989 across 14 of 14
completed seeds (basin tight; no escape found).

Currently banked **142.99 d** remains the realistic deliverable
without architectural pivot or commercial-solver acquisition.
