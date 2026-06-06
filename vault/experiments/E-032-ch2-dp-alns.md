---
id: E-032
type: experiment
status: done
tags: [ch2, small, alns, dp-evaluator, numba, breakthrough, c6-resolution]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-05
ran_start: 2026-06-05
ran_end: 2026-06-06
duration_runtime: "22h 47min wall (stopped early at plateau; 72h budget unused)"

code: scripts/ch2_e529_dp_alns.py + scripts/ch2_dp_numba.py
commit: 49c8097
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp
  /tmp/ch2_small_tcoupled_ultrafine.npz (from E-526)
  solutions/upload/small.json (entry: 126.4255 d from E-527)
outputs: |
  runs/ch2/e529_dp_alns.log
  /tmp/ch2_e529_ckpt_chain{0..5}.json
  /tmp/ch2_e529_chain{0..5}_hist.jsonl
  solutions/upload/small.json (exit: 116.3755 d)
plots: []
seed: chain-specific
env: micromamba spoc26, python 3.13.13, numba 0.65.1

code_dependencies:
  - src/esa_spoc_26/ch2_kttsp.py
  - scripts/ch2_dp_numba.py (forward DP, numba JIT'd)
  - /tmp/ch2_small_tcoupled_ultrafine.npz

compute:
  cpu_seconds: ~492000   # 22.8h × 3600 × 6 chains
  peak_memory_mb: ~600   # 6 chains × ~100 MB each (numba + table + DP arrays)
  cores: 6
  wall_h: 22.8

effort_person_hours: 3                   # design + numba JIT + smoke + launch
metrics:
  bank_entry_d: 126.4255
  bank_exit_d: 116.3755
  delta_d: -10.05
  n_banked_events: 10
  total_iter_aggregate: ~720000
  avg_iter_per_chain_per_min: 160
  dp_feasibility_pct: ~1.2
  sa_accepted_aggregate: ~9000
  numba_jit_speedup_vs_python: 80          # 220s → 2.7s per DP eval
  productive_op_dominance:
    segment_reverse: 8
    swap: 2
    double_bridge: 0
    random_k_insert: 0
verdict: supports — DP-aware ALNS yields large stepwise gains for ~12h then plateaus

invalidation: {}
---

# E-032 — Ch2 small: DP-ALNS (E-529) with numba-JIT'd evaluator

## Why this experiment exists

E-527 banked 126.43 d (−15.86 d) by replacing walk_perm_chrono with a
forward DP on the 0.05 d ultrafine Lambert table. This experiment
deploys ALNS on top of that evaluator: each candidate perm is
DP-evaluated for its provable global-optimum schedule under the
ultrafine grid, then SA-accepted/rejected.

## Hypothesis

1. **Decomposition row addressed**: perm choice. The DP closes the
   schedule slack (C2/C6) exactly per perm; the only remaining
   question is whether non-bank perms have lower DP-optimum makespan.
2. **Empirical signature**: stepwise improvements via SA-driven
   perm mutations, each accepted only if DP returns a feasible-and-
   better mk.
3. **Predicted magnitude**: 1–15 d in 72 h. The walk+SLSQP-aware
   search (E-521 r1) banked −0.55 d on a much weaker substrate; with
   DP eval we expected several × that.

## Setup

- 6 parallel ALNS chains, each independent (seeded by chain_id).
- Destroy ops: random-k (3 or 5 nodes), segment_reverse (2-opt),
  double_bridge, swap. Weights [3, 2, 2, 3, 2, 1].
- Repair: random-position insert (cheap; DP handles feasibility).
- Evaluator: numba-JIT'd forward DP on 0.05 d-quantum ultrafine
  Lambert table (49 × 4000 × 6 state space; ~2.7 s/eval hot).
- Acceptance: simulated annealing, T0=5.0, decay 0.999/iter.
- Reseed: every 6 h, chain checks global bank; if better by > 0.1 d,
  adopt and reset T.
- Bank update: atomic on any DP-feasible result with mk < current bank.

## Numba speedup

Initial Python DP: 220 s/eval. JIT'd version (single decorator on the
forward-pass loop): **2.7 s/eval = 80× speedup**. Enabled by `numba
0.65.1`. The hot loop is a simple double-`for tp in range(t, T)` with
boolean reach checks; numba handles it cleanly.

## Results

### Bankings

| # | mk | Δ | op | iter (chain) |
|---|---|---|---|---|
| 1 | 125.0752 | −1.35 | segment_reverse | 347 (c2) |
| 2 | 124.8252 | −0.25 | swap | 793 (c1) |
| 3 | 123.9750 | −0.85 | segment_reverse | 2 215 (c2) |
| 4 | 123.7250 | −0.25 | segment_reverse | 23 916 (c0) |
| 5 | 123.1252 | −0.60 | segment_reverse | 28 067 (c3) |
| 6 | 122.8283 | −0.30 | segment_reverse | 31 306 (c2) |
| 7 | 119.9283 | **−2.90** | segment_reverse | 46 625 (c4) |
| 8 | 119.7283 | −0.20 | segment_reverse | 81 669 (c4) |
| 9 | 118.5255 | −1.20 | swap | 112 965 (c0) |
| 10 | **116.3755** | −2.15 | segment_reverse | 118 381 (c2) |

**Bank trajectory: 126.4255 → 116.3755 d (−10.05 d in 12.5 h wall).**

### Plateau

Hours 12.5–22.8 produced **zero new bankings** despite ~30 k more
DP-feasible perms evaluated across the 6 chains. The bank-adjacent
DP-feasible basin is saturated under the current destroy operator mix
(random-k ≤ 5, segment_reverse, double_bridge, swap).

Stopped early at 22h 47min wall because:
- Diminishing returns since hour 12.5
- 49 h of remaining budget at ~0 progress
- Better ROI redeployed to (a) cluster-aware destroy and (b)
  multi-perm DP application

### Pattern observations

- **`segment_reverse` dominates** productive ops (8/10), with `swap`
  taking the remaining 2.
- `double_bridge` and `random_k` did NOT produce any banking event —
  they're either too disruptive (yield DP-infeasible) or land in
  basins worse than the current state.
- The two largest jumps (#7: −2.90 d, #10: −2.15 d) both came from
  `segment_reverse` after many smaller accepts had walked the state
  away from bank — this is the classic SA "escape then refine"
  pattern.
- DP feasibility ~1.2 % across all candidates (98.8 % rejected by DP
  in < 1 s as "no sink reachable").

## Verdict + analysis

**verdict:** supports — DP-aware ALNS delivers large stepwise gains
for ~half a day on Ch2 small, then plateaus around 116.38 d at the
current operator mix.

The plateau is bona-fide for THIS operator mix; bigger-radius destroy
(k=8-15) or cluster-aware destroy is necessary to break out. The
methodology trigger fires: stop optimizing within the current
substrate, switch substrates.

## What it opens up

1. **Cluster-aware destroy ALNS** (next experiment, E-033): destroy
   an entire small-comp's interior order, or destroy a contiguous
   segment of comp0 of length 8-15. Forces the search out of the
   2-opt-adjacent basin.
2. **Multi-perm DP application** (E-034): the ALNS history files
   contain ~9 000 SA-accepted perms across chains. DP-evaluating each
   one fresh (in case SA-accept didn't lead to bank-update due to
   global-state staleness) could surface perms that weren't tested at
   the bank-update step.
3. **R3 reach assessment**: bank is now 4.62 d above R3 (111.76).
   Two more bankings of #7/#10 magnitude clear it. R1 (101.65) is
   14.73 d away, harder but not implausible.

## Memory pointer

Updated `ch2-small-floor-14292.md` and `MEMORY.md` to reflect bank
at 116.3755 d.
