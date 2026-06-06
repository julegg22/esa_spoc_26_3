---
id: E-033
type: experiment
status: invalidated (stopped early without progress)
tags: [ch2, small, alns, dp-evaluator, cluster-aware, plateau]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-06
ran_start: 2026-06-06
ran_end: 2026-06-06
duration_runtime: "~10 h wall, stopped early (0 banking events)"

code: scripts/ch2_e530_cluster_alns.py
commit: bb40741
inputs: |
  solutions/upload/small.json (116.3755 d after E-529)
  /tmp/ch2_e529_ckpt_chain{1..5}.json (diverse chain seeds)
  /tmp/ch2_small_tcoupled_ultrafine.npz
outputs: |
  runs/ch2/e530_cluster_alns.log
plots: []
env: micromamba spoc26

code_dependencies:
  - scripts/ch2_dp_numba.py
  - /tmp/ch2_small_tcoupled_ultrafine.npz

compute:
  cpu_seconds: ~144000   # 10h × 4 cores effective (oversubscribed)
  cores: 6 (chains), 4 (hardware)
  wall_h: 10

verdict: refutes (cluster-aware destroy doesn't escape 116.38 d basin in 10 h)

invalidation:
  invalidated_by: "leaderboard query 2026-06-06 + medium re-attack priority"
  superseded_by: "E-531 (medium precompute) + E-532 (medium DP eval)"
  invalidated_at: 2026-06-06
  notes: "Kept E-530 running 10h with zero bankings, then killed in favor of redirecting all 4 cores to medium re-attack. Bank preserved at 116.3755 d for later resumption."
---

# E-033 — Cluster-aware DP-ALNS stalled at 116.38 d basin

## Setup

E-529 hit a plateau at 116.3755 d after 12.5 h of small-destroy ALNS.
This experiment (E-530 script) added:
- (a) Cluster-aware destroy operators: `seg_rev_large` (8-15 nodes),
  `seg_shuf_large` (8-15 nodes), `small_comp_shuf`, `random_k` (5-10
  nodes vs 3-7 before)
- (b) Diverse chain seeding: chain 0 from current bank, chains 1-5
  from the E-529 chain checkpoints (mks 127-133, different basins)
- Higher SA T₀ = 8.0 (was 5.0)
- 48 h budget

## Results

**Zero banking events in 10 h.** All 6 chains stayed at or above
116.38 d (best_local for c1 = 116.6272 — one chain found something
close but not under). Per-chain stats:
- ~5000-6000 DP_feasible per chain
- ~5000 SA-accepted moves per chain
- Currently in 127-142 d range (T cooled from 8 → ~3 by hour 10)

## Why we stopped

The plateau pattern matched E-529's: rapid initial progress then
stagnation. With only 4 physical cores and a tighter R3 target
(110.88 d, was 111.76 in audit), the marginal value of grinding
another 38 h at 0 bankings/hour was negative.

Decision (2026-06-06 18:30 UTC): kill E-530, redirect all 4 cores to
medium re-attack (E-531 precompute + E-532 DP eval + DP-ALNS). Bank
preserved at 116.3755 d.

## What this rules out for small

The single-axis destroy operators in E-530 (still bank-anchored, just
with larger radii) do not escape the 116.38 basin. To break it would
likely need:
- Multi-chain crossover (sharing structural pieces between basins)
- Destroy that respects WHICH legs are exc (not just position)
- Or a fundamentally new perm class (different start/end small comps)
  — but E-525 already showed those don't have walk-feasible tours

## Implications

This is a partial confirmation of "diminishing returns" at the small
116.38 d level under the current methodology. Two paths forward when
we return to small:
1. **Crossover operators between chain elites** — never tried
2. **Sub-quantum DP** at 0.01 d on a refined table — small expected
   gain but methodologically clean

For now: medium has 75 d of headroom by the leaderboard, much higher
EV. Sentence the small bank as "rank 5 candidate at 116.38 d" and
focus compute on medium.
