---
id: E-003
type: experiment
status: done
tags: [ch1, lns, milp]
hypothesis: "[[H-005-ch1-matching-coop-mip-lns]]"
created: 2026-05-18
ran_start: 2026-05-18T18:05:00+02:00
ran_end: 2026-05-18T18:25:00+02:00
duration_runtime: 1200s (4 cooperative workers)
code: src/esa_spoc_26/ch1_matching.py (parallel_coop_mip_lns)
commit: 3a4e2ca
inputs: "matching-i.txt (|T|=25000)"
outputs: solutions/upload/matching-i.json (mass 33319.99, feasible)
plots: [vault/experiments/E-003/coop-ladder.png]
seed: "0-3 (cooperative, shared pool-best, adaptive drop 0.10→0.65)"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_matching.py]
compute: {cpu_seconds: ~4800, peak_memory_mb: ~1200, cores: 4}
effort_person_hours: 0.7
metrics:
  matching_i:
    rank3_cutoff: 33467.83
    rank5_cutoff: 33345.05
    independent_plateau_H004: 33134.06
    coop_best: 33319.99
    pct_of_rank3: 99.56
    est_rank: "~6 (scores ~5 pts; below rank-5 by ~25)"
    per_worker: [33318.5, 33318.5, 33318.5, 33320.0]
verdict: refutes
---

# E-003 — Ch1 matching-i cooperative+adaptive MIP-LNS

## Setup / procedure

`parallel_coop_mip_lns`, 4 workers, shared global-best npy, adaptive
escalating destroy (0.10→0.65 on stuck counter), greedy seed,
1200 s, spoc26/4 cores.

## Results

greedy 29 792 → independent MIP-LNS 33 134 → **cooperative 33 320**
(99.56 % of rank-3). All workers converged to ~33 318–33 320
(cooperation worked: shared best pulled them together).

![ladder](E-003/coop-ladder.png)

## Verdict + analysis

**verdict: refutes** H-005's prediction. Cooperation closed ~56 %
of the residual gap (333.8 → 147.8 mass) but **missed rank-3
(33 467.83) and even the conservative rank-5 fallback (33 345) by
~25**. Lands ≈ leaderboard rank-6 (scores ~5 pts; up from H-004's
~rank-7). Diminishing-returns ladder confirmed: each operator
upgrade halves the remaining gap. The last ~0.44 % is a distinct,
hard regime — see [[takeaways/T-003-diminishing-returns-need-exact-polish|T-003]].
Next: warm-started large-sub-MIP "polish" ([[hypotheses/H-006-ch1-matching-exact-polish|H-006]],
running) and the open Gurobi-licence question (commercial exact
solver is the realistic top-field method).
