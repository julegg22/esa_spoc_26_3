---
id: E-001
type: experiment
status: done
tags: [ch1, milp, baseline]
hypothesis: "[[H-001-ch1-matching-mip]]"

created: 2026-05-18
ran_start: 2026-05-18T16:18:00+02:00
ran_end: 2026-05-18T17:05:00+02:00
duration_runtime: ~47m wall (incl. one 600s MIP cap)

code: src/esa_spoc_26/ch1_matching.py
commit: 9c56837 (+ uncommitted ch1_matching.py at run time; committed in this E's commit)
inputs: "reference/SpOC4/Challenge 1 Luna Tomato Logistics/matching-i.txt (|T|=25000), matching-ii.txt (|T|=92103)"
outputs: solutions/upload/matching-i.json, solutions/upload/matching-ii.json (greedy, valid/feasible)
plots: [vault/experiments/E-001/methods-vs-rank3.png]
seed: 0
env: spoc26 (highspy/HiGHS, numpy 2.3.5, scipy 1.17.1)
code_dependencies:
  - src/esa_spoc_26/ch1_matching.py

compute:
  cpu_seconds: ~750
  peak_memory_mb: ~600
  cores: 1
effort_person_hours: 1.5

metrics:
  matching_i:
    rank3_cutoff_mass: 33467.83
    rank1_cutoff_mass: 33555.62
    highs_default_600s: {mass: 26404.456, n_selected: 3704, mip_gap: 1.2267, status: kTimeLimit}
    greedy: {mass: 29791.692, n_selected: 3870, wall_s: 0.02, pct_of_rank3: 89.0}
    naive_lns_90s: {mass: 29791.692, iters: 6730, improvement: 0.0}
    ejection_lns_60s: {mass: 29791.692, iters: 524, improvement: 0.0}
  matching_ii:
    rank3_cutoff_mass: 72101.13
    greedy: {mass: 63313.022, n_selected: 7759, wall_s: 0.06, pct_of_rank3: 87.8}
verdict: refutes
---

# E-001 — Ch1 matching: HiGHS-default / greedy / LNS first attempts

## Setup

Weighted 3-D matching ILP (max Σwᵢxᵢ; each e/l/d used ≤1). Methods:
(a) HiGHS MIP default settings, 600s cap; (b) weight-desc greedy;
(c) ruin + weight-greedy-recreate LNS; (d) ejection-chain LNS
(1-in/≤3-out + greedy fill). spoc26 env, single core.

## Procedure

`ch1_matching.py`: `solve()` (HiGHS passModel), `greedy()`,
`lns()` / `ejection_improve()`. Run on `matching-i` (and greedy on
`matching-ii`). Compared to O-002 2026-05-18 rank-3 cutoffs.

## Results

| method | matching-i mass | % of rank-3 (33467.83) |
|---|---|---|
| HiGHS default 600s | 26404.46 (gap 1.23) | 78.9 % |
| greedy (0.02 s) | 29791.69 | 89.0 % |
| naive LNS 90 s | 29791.69 | 89.0 % (0 improvement) |
| ejection LNS 60 s | 29791.69 | 89.0 % (0 improvement) |

`matching-ii` greedy = 63313.02 = 87.8 % of rank-3 (72101.13).

![methods vs rank-3](E-001/methods-vs-rank3.png)

## Verdict + analysis

**verdict: refutes** H-001's `falsifiable_prediction` (HiGHS MIP /
cheap methods reach mass ≥ 33467.83 within 30 min). No method
≤ allotted effort cleared rank-3; best (greedy) is 89 % / 87.8 %.

Root cause (analytical, not a bug): greedy adds transfers in
weight-descending order, so any *excluded* transfer i was blocked
by an already-selected transfer of weight ≥ wᵢ. Therefore for the
"add i, eject its ≤3 conflicts" move, `wᵢ − Σ w(conflicts) ≤ 0`
always — **greedy is a strict local optimum** for the 1-in/≤3-out
neighbourhood, and ruin+greedy-recreate returns to it (greedy is a
fixed point). HiGHS default is far worse (weak 3-D-matching LP
relaxation ⇒ B&B floods with no incumbent improvement; 122 % gap).
Competitors sit at +12.5 % over greedy ⇒ they use materially
stronger search (long ejection chains / worse-accepting / MIP-based
LNS / strong exact solver). Observability gotcha recorded as
[[lessons/L-001-greedy-localopt-and-suppressed-solver-log|L-001]].
Closure takeaway: [[takeaways/T-001-ch1-matching-needs-strong-search|T-001]].
Valid feasible baselines were still produced (META.md §2).
