---
id: E-023
type: experiment
status: done
tags: [ch2, sa, simulated-annealing, lns, local-optimum]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "~2.8h wall (3 parallel SA × 5000 iters each)"
code: src/esa_spoc_26/ch2_sa.py
commit: 3172498
inputs: "solutions/upload/small.json (143.79d, 2-opt + or-opt local opt)"
outputs: solutions/upload/small.json (142.99d)
env: spoc26 + ortools
code_dependencies: [src/esa_spoc_26/ch2_sa.py, src/esa_spoc_26/ch2_insert_lns.py, src/esa_spoc_26/ch2_findtransfer_greedy.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 29286, peak_memory_mb: 800, cores: 3}
effort_person_hours: 2.0
metrics:
  initial_mk: 143.791
  best_mk: 142.989
  improvement_d: 0.802
  total_iters: 15000
  total_accepted: 368
  total_improvements: 1
  improvement_iter: 77
  improvement_seed: 2
  feasibility_rate: ~0.10
  rank3_target_d: 111.76
  ratio_to_rank3: 1.279
verdict: confirmed (modest improvement; local-optimum hypothesis supported)
---

# E-023 — SA finds 1 improvement in 15 000 iters: 143.79 → 142.99 d

## Result

Three parallel SA runs (5000 iters each, T_start=80, T_end=0.2,
geometric cooling, mixed move palette 25/20/40/10/5 of
2-opt / Or-opt / big-segment-reverse / cluster-swap / ruin-recreate):

| seed | best_mk | improvements | accepted | infeas | wall |
|---|---|---|---|---|---|
| 0 | 143.791 | **0** | 128/5000 | 4447 | 9821 s |
| 1 | 143.791 | **0** | 121/5000 | 2607 | 10342 s |
| 2 | **142.989** | **1** (iter 77, 2-opt) | 119/5000 | 1368 | 9124 s |

Final banked: **142.989 d** (Δ = 0.80 d, ratio to rank-3 1.279).

## Decisive observation — the basin is structurally tight

After the early 2-opt improvement on seed=2, **no SA run found
another improving move across the remaining 14 923 iterations**.
The acceptance rate stayed low (~2 % of iters) and the infeasibility
rate dominated (~30 %–90 % depending on temperature). The cooling
schedule did anneal the seeds back toward feasibility (cur=159–169 d
at T < 5 d), but never landed below the initial 143.79 d.

This is **strong evidence that 142.99–143.79 is a near-global local
optimum for the SA move set + constraints**:
- Small moves (2-opt, Or-opt) almost always break feasibility
  because all 5 exception slots are at structurally-necessary bridges
  (the 18→46 pre-cluster, 1→4 cluster-entry, 11→29 cluster-exit,
  21→33 late-big-cluster, 7→16 post-cluster-tail).
- Larger structure-aware moves (big-segment-reverse, cluster-swap)
  preserve bridges but the new arrangement's cost is typically much
  worse (mean +10–30 d above 143.79).
- Ruin-recreate (k=3, sampled 8 positions per insertion) finds
  feasible reinsertions but the resulting mk is similarly worse.

## Why this doesn't reach rank-3 (111.76 d)

The 32-day gap to rank-3 is *not* in the move-search space we
explored. Closing it would require:

1. **A different big-cluster sub-path decomposition** — the 40-node
   big cluster contributes 137 d of the makespan (~70 % of the total).
   The 5 exception slots constrain how it can be split.
2. **A fundamentally different exception placement** — perhaps
   splitting the small cluster across the path (one node alone, two
   together) with a different mix of in/out bridge pairs.
3. **Per-leg makespan-NLP with waiting search** — currently
   `find_earliest_transfer` returns first feasible tof at fixed
   t_start; a 2D (td_offset, tof) optimisation per leg could shave
   ~0.5–2 d total, partially closing the gap.
4. **Mixed-integer formulation with PWL approximation of Δv surface**
   — replaces discrete window CP-SAT (which failed at E-018→E-021)
   with continuous-time MILP. ~1 week build.

## Position vs goal

| metric | value |
|---|---|
| banked | **142.989 d** |
| rank-3 cutoff | 111.76 d |
| ratio | **1.279** |
| expected leaderboard placement | rank 6–10 |
| expected points | ~3–5 |
| total session compute on Ch2 | ~15 h |
| total Ch2 method iterations | 11+ experiments + 8 modules |

The polish ceiling for the find_transfer + cluster-insertion + 2-opt
+ SA approach is approximately **142–143 d** on small. To advance
materially toward rank-3 needs the bigger architectural change
(item 4 above) — not more iterations of the current pipeline.
