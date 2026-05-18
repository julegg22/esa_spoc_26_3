---
id: E-005
type: experiment
status: done
tags: [ch1, lns, milp]
hypothesis: "[[H-006-ch1-matching-exact-polish]]"
created: 2026-05-18
ran_start: 2026-05-18T19:00:00+02:00
ran_end: 2026-05-18T19:25:00+02:00
duration_runtime: 1503s (4 cooperative workers)
code: src/esa_spoc_26/ch1_matching.py (parallel_coop_mip_lns)
commit: 86ebe22
inputs: "matching-ii.txt (|T|=92103, |E|=|L|=|D|=10000)"
outputs: solutions/upload/matching-ii.json (72018.21, feasible)
plots: [vault/experiments/E-004/polish-ceiling.png]
seed: "0-3 cooperative, time_per_sub=12s"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_matching.py]
compute: {cpu_seconds: ~6000, peak_memory_mb: ~2200, cores: 4}
effort_person_hours: 0.2
metrics:
  matching_ii:
    rank3_cutoff: 72101.13
    rank4_cutoff: 72089.34
    rank5_cutoff: 71637.58
    greedy_baseline: 63313.02
    coop_best: 72018.21
    pct_of_rank3: 99.88
    est_rank: "~5 (scores ~6 pts; 83 below rank-3, 71 below rank-4)"
    per_worker: [72001.3, 72017.1, 72018.2, 72018.2]
verdict: inconclusive
---

# E-005 — Ch1 matching-ii cooperative MIP-LNS (bank run)

## Setup / procedure

Same `parallel_coop_mip_lns` operator as E-003, on the larger
`matching-ii` (92 103 vars / 30 000 constraints), 4 workers,
`time_per_sub=12 s`, 1503 s. Executes the user-approved
"run matching-ii similarly, bank it" step before the H-002 pivot.

## Results

greedy 63 313 (87.8 %) → **coop 72 018.21 (99.88 % of rank-3)**.
All workers ~72 017–72 018. ≈ leaderboard **rank-5 → ~6 pts**;
only 83 mass below rank-3 (closer than matching-i's 0.4 %).

![ceiling](../experiments/E-004/polish-ceiling.png)

## Verdict + analysis

**verdict: inconclusive** for a rank-3 claim (not predicted — this
is a bank run, not a hypothesis test), but it **banks a valid
~rank-5 artifact (~6 pts)**. Confirms the same HiGHS-family
near-ceiling behaviour as matching-i (T-004) at larger scale.
Closes the Ch1-matching line execution: total banked ≈ 11 pts
(matching-i ~rank-6 + matching-ii ~rank-5). Frontier proceeds to
[[hypotheses/H-002-ch1-trajectory-greedy|H-002]]. See
[[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]].
