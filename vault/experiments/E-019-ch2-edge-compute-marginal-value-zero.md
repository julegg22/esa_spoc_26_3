---
id: E-019
type: experiment
status: done
tags: [ch2, structure, resolution]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~13 min (4-rung ladder, 180-pair sample, 4 cores)
code: src/esa_spoc_26/ch2_rescurve.py
commit: (committed with this E)
inputs: "180-pair sample of Ch2 small; ladder coarse→veryfine"
outputs: vault/experiments/E-019/rescurve.png
plots: [vault/experiments/E-019/rescurve.png]
seed: 0
env: spoc26
code_dependencies: [src/esa_spoc_26/ch2_rescurve.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 800, peak_memory_mb: 600, cores: 4}
effort_person_hours: 0.4
metrics:
  ladder:
    coarse: {t_step: 3.0, tof_max: 30, wall_s: 29.3, frac_le100: 0.050, frac_le600: 0.406, median: 671.0, min: 32.2}
    medium: {t_step: 1.5, tof_max: 50, wall_s: 92.2, frac_le100: 0.050, frac_le600: 0.406, median: 668.6, min: 31.2}
    fine: {t_step: 1.0, tof_max: 80, wall_s: 202.2, frac_le100: 0.050, frac_le600: 0.406, median: 668.2, min: 31.2}
    veryfine: {t_step: 0.5, tof_max: 110, wall_s: 468.9, frac_le100: 0.050, frac_le600: 0.406, median: 668.2, min: 31.2}
  compute_ratio_veryfine_vs_coarse: 16x
  density_gain: zero
verdict: refutes
---

# E-019 — Edge-search compute past coarse has ZERO marginal value

## Result

Four resolution rungs on a fixed 180-pair sample, cumulative
~13 minutes parallel-compute:

| res | wall (s) | frac ≤100 | frac ≤600 | median Δv | min Δv |
|---|---|---|---|---|---|
| coarse | 29 | **0.050** | **0.406** | 671.0 | 32.2 |
| medium | 92 | 0.050 | 0.406 | 668.6 | 31.2 |
| fine | 202 | 0.050 | 0.406 | 668.2 | 31.2 |
| veryfine | 469 | 0.050 | 0.406 | 668.2 | 31.2 |

![rescurve](E-019/rescurve.png)

## Verdict + analysis

**verdict: refutes** the E-017 "under-resolved cheap-edge graph"
hypothesis *quantitatively*. 16× more compute at "veryfine" added
**zero** cheap edges at either ≤100 or ≤600. Median Δv shifted by
< 0.5 %. The cheap-edge graph is structurally saturated at coarse
resolution.

**Decision impact for "where to spend heavy compute":**
- **NOT on edge-search resolution** — flat marginal value.
- The hi-accuracy `edges_small.npz` *is* essentially the complete
  cheap-edge graph (138 ≤100 + 837 in (100,600]).
- The unsolved bottleneck (E-018) is **time-coupling**: each cheap
  edge has narrow windows in absolute time; chronological chaining
  is the binding constraint.
- Right heavy-compute target → (a) **multi-window-per-edge
  extraction** (cheap-window list as a function of t_dep, not a
  single min — feeds (b)); (b) **time-windowed CP-SAT solver** with
  chronology constraints; (c) **medium/large** scale-up of the same
  pipeline (heavy precompute reused, structure preserved per Q6).
