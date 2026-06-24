---
id: E-035
type: experiment
status: banked (Ch1 trajectory 227,653.57 → 228,107.78 kg)
tags: [ch1, trajectory-matching, ledger, rematch, hungarian, bank-reconcile]

hypothesis: "newer per-pair caches (esp. tier2_heavy) were never re-assembled into the banked trajectory assignment; re-matching the union table improves the bank"

created: 2026-06-11
ran_start: 2026-06-11
ran_end: 2026-06-11
duration_runtime: "~13 min wall (compute-light, single-threaded)"

code: scripts/ch1_e564_ledger_rematch.py
inputs: |
  solutions/upload/trajectory.json (banked 2026-05-30)
  runs/ch1/tier2_heavy_results.json + 14 other per-pair caches in runs/ch1/
outputs: |
  solutions/upload/trajectory.json (228,107.78 kg)
  solutions/upload/trajectory.json.bak.e564
  runs/ch1/76_e564_ledger_rematch.log
env: micromamba spoc26 (heyoka + pykep official UDP)

verdict: confirms-weakly (+454.22 kg; the May-30 rebank had never re-run after tier1-light v2). Tier2-heavy suspicion DISPROVED (already merged).
---

# E-035 — Ch1 trajectory bank-ledger reconciliation + re-matching

## Motivation
Belief about the trajectory bank was stale ("186k-215k kg"); suspected
unbanked newer per-pair results (esp. runs/ch1/tier2_heavy_results.json).

## Results
- **True current bank (official udp.fitness): 227,653.57 kg, 302 transfers** —
  matches the May-30 polish log (227,654). The 186-215k belief was WRONG/stale.
- Union table = bank + 15 caches → 6,154 distinct (idE,idL) pairs.
- **Tier2-heavy suspicion DISPROVED**: tier2_heavy_results.json contributed 0
  new/improved pairs (already merged before the May-30 bank).
- Two-stage Hungarian (optimistic pair-cap, then destination assignment) → 301
  transfers, all passed official validation iter-1; table-predicted == official
  (0.0% disagreement).
- **BANKED 227,653.57 → 228,107.78 kg (+454.22)**: 8 tier1_light rows (9,045 kg)
  + 2 hungarian_seeded rows (3,147 kg) swapped in for 11 weaker bank rows. The
  May-30 rebank had simply never been re-run after tier1-light v2.
- Backup trajectory.json.bak.e564; agent re-validated from disk (228,107.78).
  **NOTE: independent heyoka re-eval by orchestrator DEFERRED (load contention
  2026-06-11 17:16) — verify next low-load tick; backup safe, change small.**

## Context vs rank-3
R3 trajectory cutoff = 463,513 kg (06-11, tightened). Bank 228,108 ≈ 49% of R3,
gap ~235k. This experiment was reconciliation, NOT the lever — see below.

## Heavy-phase scope (now DEFINED — for E-554's 3 cores tonight)
All three are dv-bound (zero capacity-capped → lower-dv trajectories are the
only lever; some banked pairs at <56% of theoretical mass = real headroom):
1. **99 unused idE × 99 unused idL** — need the Lambert+DC pipeline
   ([[C-005-differential-correction-shooting]] + [[E-701-ch1-eccentric-departure-solver-fix]]), NOT SADE (pygmo
   log 70 got 0 valid on these).
2. **~1,300 tier-1 pairs** await 3-impulse DC polish (tier-2 heavy run was
   truncated at ~200/1500 in log 75); historical 5-30% per-pair gains.
3. Per-pair re-solve headroom confirmed real by Path-C validation (log 77).

These three define the embarrassingly-parallel Ch1 heavy sweep to launch when
E-554 frees 3 cores (~01:10 tonight). Gated separately: the WSB lever (E-565
prototype) for the physics ceiling beyond impulsive ~371k.
