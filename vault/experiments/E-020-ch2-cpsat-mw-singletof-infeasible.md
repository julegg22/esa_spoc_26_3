---
id: E-020
type: experiment
status: done
tags: [ch2, cpsat, time-coupling, framing, reframe]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "<1 min (TW 2s + precompute 100s + CP-SAT 14s)"
code: src/esa_spoc_26/ch2_cpsat_tw.py + ch2_cpsat_mw.py + ch2_kttsp.precompute_windows
commit: (committed with this E)
inputs: "edges_small.npz; windows_small.npz (6634 windows at K=8 per pair, single-tof)"
outputs: none feasible
env: spoc26 + ortools
code_dependencies: [src/esa_spoc_26/ch2_cpsat_tw.py, src/esa_spoc_26/ch2_cpsat_mw.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 100, peak_memory_mb: 800, cores: 4}
effort_person_hours: 1.5
metrics:
  tw_single_window_status: INFEASIBLE (2 s)
  mw_multi_window_status: INFEASIBLE (14 s)
  mw_n_edges: 949
  mw_n_windows: 6634
  median_cheap_tof_d: 33.5
  rank3_target_d: 111.76
  sigma_48_random_cheap_tofs_d: 1312
  horizon_d: 200
verdict: refutes
---

# E-020 — Multi-window CP-SAT v1 also INFEASIBLE: the real reframe

## Result

Two CP-SAT runs back-to-back on the small instance:

1. **TW (single-window)** — one (td, tof) per pair from the static
   precompute → status **INFEASIBLE in 2 s** (49 nodes, ≤600 graph).
2. **MW (multi-window, K=8 per pair, all at fixed tof=TF[i,j])** —
   status **INFEASIBLE in 14 s** (949 edges, 6634 windows).

Single-tof multi-window gives ~6.8 td-windows per pair-with-any-window
(close to K=8 cap) but still cannot chain a 49-node Hamiltonian path
in the 200-day horizon.

## Decisive analysis — why it's infeasible (not a solver bug)

Cheap-edge TOF distribution on `edges_small.npz` (138 cheap pairs):

| stat | value (d) |
|---|---|
| min | 0.60 |
| p10 | 3.4 |
| p25 | 16.6 |
| **median** | **33.5** |
| p75 | 37.3 |
| max | 41.0 |

Monte-Carlo: median ΣTOF of 48 random cheap legs = **1312 d**.

- Horizon: **200 d**.
- Rank-3 target makespan: **111.76 d** → avg leg ≤ 2.3 d.
- Median cheap-leg TOF: **33.5 d** → 49-leg path infeasible.

**Conclusion: the precompute is selecting the wrong (td, tof)
point per pair.** It fixes `tof = TF[i,j]` — the *global-Δv-minimum*
tof — but rank-3 needs *short-tof* (~1–3 d) legs even at higher Δv.
The (Δv, tof) Pareto front per pair has both regimes; the static
precompute only stored the Δv-optimal one.

## Why E-018 missed this

E-018 framed the bug as "single-window can't chain chronologically";
true but secondary. The deeper issue (this experiment): even
**unlimited** windows at the static tof would not chain inside 200d
because ΣTOF blows the horizon. The principal heavy-compute target
is therefore **joint (td, tof) precompute**, not just td-window
extraction.

## The new precompute (committed with this E)

`precompute_windows_2d` (kttsp.py):

```
for tof in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 24.0, 36.0):
  scan td → cheap regions
  collect (Δv, td, tof) ≤ thr_max
diversify in (td × tof) 2D plane → up to K=12 reps per pair
```

Output: `windows2d_small.npz`, consumed by `solve_mw` unchanged.
Pending: run on small + decisive multi-window CP-SAT (v2 chain).

## Position vs the 6h research program

This **is** the decisive finding the user asked for. Heavy-compute
ranking (high → low marginal value):

1. **Joint (td, tof) window precompute (v2)** — fixes the 1312d ΣTOF
   blow-up; enables short-tof legs at moderate Δv. **HIGHEST**.
2. Multi-window CP-SAT solve on the v2 precompute — should be
   feasible if v2 captures the (Δv, tof) Pareto front correctly.
3. Edge-search resolution: still **ZERO** (E-019).
4. medium/large scale-up: same pipeline, ~3–10× cost.

Single-tof multi-window CP-SAT is REFUTED as the right model. The
right model is joint (td, tof, Δv) lookup with CP-SAT over arc-window
BoolVars + chronology — the same structure but with a *different*
window definition.
