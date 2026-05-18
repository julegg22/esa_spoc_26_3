---
id: E-002
type: experiment
status: done
tags: [ch1, lns, milp]
hypothesis: "[[H-004-ch1-matching-mip-lns]]"

created: 2026-05-18
ran_start: 2026-05-18T17:42:00+02:00
ran_end: 2026-05-18T17:52:00+02:00
duration_runtime: 600s (4 parallel workers) + a failed silent run prior

code: src/esa_spoc_26/ch1_matching.py (parallel_mip_lns)
commit: 5ecabbf (code), result committed in this E's commit
inputs: "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt (|T|=25000)"
outputs: solutions/upload/matching-i.json (MIP-LNS, mass 33134.06, feasible)
plots: [vault/experiments/E-002/mip-lns-vs-rank3.png]
seed: "0,1,2,3 (drop_frac 0.15/0.20/0.25/0.30)"
env: spoc26 (highspy/HiGHS, numpy, scipy)
code_dependencies:
  - src/esa_spoc_26/ch1_matching.py
compute:
  cpu_seconds: ~2400
  peak_memory_mb: ~1200
  cores: 4
effort_person_hours: 1.0
metrics:
  matching_i:
    rank3_cutoff_mass: 33467.83
    rank1_cutoff_mass: 33555.62
    greedy_seed_baseline: 29791.69
    probe_70s_1thread: 32958.0
    campaign_600s_4w:
      best_mass: 33134.057
      per_worker: [33002.0, 33079.4, 33079.5, 33134.1]
      best_drop_frac: 0.25
      pct_of_rank3: 99.0
      est_leaderboard_rank: "~7 (scores points, not rank-3)"
  observability_incident:
    note: "first launch died silently — broken redirect from a truncated chain; no log/artifact. Re-run with harness-managed capture + heartbeats (L-001)."
verdict: refutes
---

# E-002 — Ch1 matching-i parallel MIP-LNS campaign

## Setup

`parallel_mip_lns`: 4 workers, drop_frac ∈ {0.15,0.20,0.25,0.30},
greedy seed, exact HiGHS sub-solve of the freed region, 600 s/worker,
spoc26, 4 cores.

## Procedure

Probe (70 s, 1 thread) → 32958 validated escaping the greedy local
optimum. Campaign launched; first attempt died silently (broken
output redirect from a truncated command chain — no diagnostics);
relaunched harness-managed with per-25-round heartbeats (L-001 fix).

## Results

| stage | matching-i mass | % rank-3 (33467.83) |
|---|---|---|
| greedy | 29791.69 | 89.0 |
| probe 70 s ×1 | 32958.0 | 98.5 |
| **campaign 600 s ×4** | **33134.06** | **99.0** |

Per-worker plateau tight (33002–33134) — a genuine basin, not a
"needs more time" artefact. Feasible; valid artifact written.

![mip-lns vs rank-3](E-002/mip-lns-vs-rank3.png)

## Verdict + analysis

**verdict: refutes** H-004's prediction (mass ≥ 33467.83 on
`matching-i` within a 600 s campaign). Result 33134 = **99.0 %** of
rank-3 — a strong near-miss (≈ leaderboard rank-7, *does* score
points; far above greedy/default-HiGHS) but **~1 % short of rank-3**.
The MIP-LNS *family* is validated (escapes the greedy optimum that
refuted H-001); independent parallel workers plateau ~1 % below the
cutoff because each converges to its own basin with no information
sharing and a fixed destroy size. → child
[[hypotheses/H-005-ch1-matching-coop-mip-lns|H-005]] (cooperative
shared-best + adaptive escalating destroy). Distilled:
[[takeaways/T-002-mip-lns-family-validated-but-plateaus|T-002]].
Lesson reinforced: [[lessons/L-001-greedy-localopt-and-suppressed-solver-log|L-001]]
(silent run = no diagnostics; always harness-capture + heartbeat).
