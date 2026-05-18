---
id: E-004
type: experiment
status: done
tags: [ch1, lns, milp]
hypothesis: "[[H-006-ch1-matching-exact-polish]]"
created: 2026-05-18
ran_start: 2026-05-18T18:30:00+02:00
ran_end: 2026-05-18T18:55:00+02:00
duration_runtime: 1500s (4 workers, warm-start 33320)
code: src/esa_spoc_26/ch1_matching.py (parallel_coop_mip_lns, warm_artifact)
commit: 87e5bb5
inputs: "matching-i.txt; warm-start solutions/upload/matching-i.json (33320)"
outputs: solutions/upload/matching-i.json (33338.18, feasible)
plots: [vault/experiments/E-004/polish-ceiling.png]
seed: "0-3 cooperative, time_per_sub=25s, large escalating destroy"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch1_matching.py]
compute: {cpu_seconds: ~6000, peak_memory_mb: ~1400, cores: 4}
effort_person_hours: 0.4
metrics:
  matching_i:
    rank3_cutoff: 33467.83
    rank5_cutoff: 33345.05
    warm_start: 33319.99
    polish_best: 33338.18
    pct_of_rank3: 99.61
    delta_vs_coop: 18.19
    est_rank: "~6 (scores ~5 pts; still below rank-5 by ~7)"
verdict: refutes
---

# E-004 — Ch1 matching-i exact-polish (warm-started large sub-MIPs)

## Setup / procedure

`parallel_coop_mip_lns` warm-started from the 33 320 incumbent,
`time_per_sub=25 s`, escalating destroy, 4 workers, 1500 s.

## Results

33 320 → **33 338.18** (+18.2). All 4 workers converged to 33 338.2.
99.61 % of rank-3; **still below rank-5 (33 345) by ~7**.

![ceiling](E-004/polish-ceiling.png)

## Verdict + analysis

**verdict: refutes** H-006 (≥ 33 467.83, fallback ≥ 33 345). The
+18 over 1500 s on top of the prior ladder
(29 792→33 134→33 320→33 338) is the **terminal flattening** of the
HiGHS-based approach: ~33 340 is a hard ceiling, ~0.4 % short of
rank-3, with no commercial solver available (user: open-source
only). Decision (user-approved): bank the `matching-i` artifact
(≈ rank-6, scores ~5 pts), run `matching-ii` with the same method,
**pivot frontier to [[hypotheses/H-002-ch1-trajectory-greedy|H-002]]**.
Distilled: [[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]].
