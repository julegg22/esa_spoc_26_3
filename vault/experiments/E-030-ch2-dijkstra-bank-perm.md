---
id: E-030
type: experiment
status: done             # draft | running | done | invalidated
tags: [ch2, small, dijkstra, time-expanded, exact, bug-class, evaluator-substrate, C6-confirmed, bank-update]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-02
ran_start: 2026-06-03
ran_end: 2026-06-03
duration_runtime: "DP itself 2.4s; leg refinement E-519b 1 pass; total ~3 min wall"

# reproducibility
code: scripts/ch2_e519_dijkstra_bank.py
commit: 4dcd1ec (pre-launch)
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp (n=49, n_exc=5)
  /tmp/ch2_small_tcoupled_fine.npz (fine min-tof table, 400 t × 100 tof quanta)
  solutions/upload/small.json (bank perm)
outputs: |
  runs/ch2/e519_dijkstra.log
  /tmp/ch2_e519_result.json
plots: []
seed: deterministic (DP, no randomness)
env: micromamba spoc26, python 3.13.13

code_dependencies:
  - src/esa_spoc_26/ch2_kttsp.py
  - src/esa_spoc_26/ch2_insert_lns.py     # for post-validation
  - /tmp/ch2_small_tcoupled_fine.npz

compute:
  cpu_seconds:
  peak_memory_mb:
  cores: 1
  wall_budget_min: 30

effort_person_hours:

metrics:
  e519_dp_mk_d: 152.0                    # DP on 0.5d-quantum grid; F1
  e519_dp_udp_feasible: false            # reconstruction bug (bucket-gap≠actual tof)
  e519_walk_S1_mk_d: 142.891              # walk_perm_chrono confirms bank
  e519_walk_S2_mk_d: 152.900              # finer wait → WORSE (non-monotone)
  e519b_bank_before_d: 142.8913
  e519b_bank_after_d: 142.8359             # NEW BANK
  e519b_shaved_d: 0.0554
  e519b_legs_improved: 1                   # only leg 47
  e519c_attempted_finer_shave_d: 0.0021    # killed early; bank not updated
  current_bank_d: 142.8359                 # verified UDP-feasible, viols [0,0,0,0]
verdict: refutes (C6 confirmed) + F1 (DP grid too coarse)

invalidation:
  invalidated_by:
  superseded_by:
  invalidated_at:
  notes:
---

# E-030 — Ch2 small: Dijkstra (time-expanded shortest path) on bank perm

## Why this experiment exists

The ultrathink review (this turn) identified **walk_perm_chrono as the
single highest-prior bug-class hypothesis**: a greedy chronological
walker that commits to earliest-feasible tof per leg. All 12+ method
families that converge to 142.89 d use this same evaluator. The
14.3 d spread between substrate S1 (169.86 d) and S2 (155.60 d) on
the SAME CP-SAT perm (E-029 post-validation) demonstrates that
walk_perm_chrono leaves 5–15 d on the table per perm via greedy
sub-optimality.

This experiment computes the **provable optimum on bank perm** —
the lowest makespan achievable given the bank's 49-node visit order,
under the fine-table tof discretization. It directly attacks the C2
decomposition row (44.48 d per-leg slack) plus the newly named C6
(evaluator-greedy slop, 0–15 d/perm).

Method: forward DP on (step, t_bucket, exc_used) using fine table
edge costs. Exact within the fine-grid quantum (0.5 d t × ~0.08 d tof).

## Hypothesis (pre-registered, 3-sentence guardrail)

1. **Decomposition row(s) addressed**: C2 (per-leg tof slack, 44.48 d)
   and C6 (evaluator-greedy slop, suspected 5–15 d). Bank perm fixed;
   varies only the (times, tofs) schedule.
2. **Empirical signature**: Dijkstra returns provable minimum
   makespan `mk_dij ∈ [0, 200]` d on bank perm. Reconstructed
   (times, tofs) is Lambert-revalidated via `walk_perm_chrono` and
   `kt.fitness`. Three outcomes:
   - **mk_dij < 142.89 d → walk_perm_chrono has been suboptimal**;
     new bank candidate from same perm; all prior perm comparisons
     are in distorted units.
   - **mk_dij = 142.89 d (± 0.5d quantum)** → walk_perm_chrono is
     globally optimal on bank perm; bottleneck is perm choice, not
     schedule.
   - **mk_dij > 142.89 d** → impossible if DP is correct (would mean
     bank's actual schedule is outside the fine-table grid); points
     to fine-table coverage bug, see F1.
3. **Predicted magnitude**: 0–15 d shortening, with mode near 5–10 d
   based on the S1 vs S2 spread observed in E-029.

## Setup

**State space**
- `step ∈ [0, 48]` — position in perm (49 nodes, 48 legs)
- `t_bucket ∈ [0, 400]` — current time in 0.5 d quanta (200 d horizon)
- `exc_used ∈ [0, 5]` — exception count

Total states: 49 × 401 × 6 = 117 894.

**Transitions from `(k, t, e)`**
- For each `t' ∈ [t, 400]` where `fine_cheap[perm[k], perm[k+1], t']`
  is finite: edge to `(k+1, t' + ceil(cheap_tof / 0.5), e)`.
- For each `t' ∈ [t, 400]` where `fine_exc[perm[k], perm[k+1], t']`
  is finite, **if `e < 5`**: edge to `(k+1, t' + ceil(exc_tof / 0.5),
  e + 1)`.

No tof_window or wait_steps caps (no hostile defaults); the fine
table itself is the only feasibility filter.

**Forward DP**
- `reachable[k][t][e] = True` iff state reachable from (0, 0, 0).
- Backtrack pointers store predecessor `(prev_t, prev_e, t', is_exc)`
  for each newly-reached state.

**Objective**
- `min t` such that `reachable[48][t][e] = True` for some `e ∈ [0, 5]`.

**Post-validation**
- Reconstruct (times, tofs) by backtracking.
- Run `kt.fitness(times + tofs + perm)` for official UDP score.
- Compare to 142.8913 d.

**Bank update rule**
- If `kt.is_feasible(fit) and fit < 142.8913`: atomic write
  `solutions/upload/small.json` with backup
  `solutions/upload/small.json.bak.20260602.e519`.

## Success criteria (verifiable post-run)

- [ ] DP completes in < 5 min wall.
- [ ] At least one reachable state at step 48 with e ≤ 5.
- [ ] Reconstructed (times, tofs) Lambert-revalidates as
      UDP-feasible.
- [ ] mk_dij reported as float; compared to 142.8913 d and verdict
      mapped per pre-registration.
- [ ] If mk_dij < 142.8913 and UDP-feasible: auto-bank fires.

## Pre-registered failure modes

- **F1** — Bank's actual (times, tofs) lies outside the fine-table
  grid (e.g., bank uses tof = 0.337 d which falls between fine-table
  buckets). DP could miss it. **Test**: compare mk_dij vs 142.89.
  If mk_dij > 142.89 by more than 0.5 d, F1 likely. Mitigation:
  refine grid or interpolate.
- **F2** — Reconstructed (times, tofs) fails `kt.is_feasible`
  (UDP-rejected). Cause: fine table cell marked finite but real
  Lambert is sub-threshold at the exact (t, tof) values. **Test**:
  feasibility flag in result.
- **F3** — DP finds mk_dij ≪ 142.89 but Lambert revalidation shows
  much higher mk. Means fine table is wrong (precompute bug B4 from
  ultrathink). Decisive bug discovery; pivot to fine-table audit.

## Procedure (actual)

1. Detoured: `/tmp/ch2_small_tcoupled_fine.npz` was cleaned across
   day boundary; re-precomputed via `scripts/ch2_precompute_fine.py`
   (~10 min wall, 8-core parallel Lambert grid).
2. **E-519** (`scripts/ch2_e519_dijkstra_bank.py`): forward DP on
   (step, t_bucket, exc_used) with 0.5 d quantum and the fine-table
   per-leg arrival buckets. DP itself completed in 2.4 s.
3. **Spot-diagnostic**: bank's actual (times, tofs) uses non-quantized
   continuous t (e.g., t[1]=0.05, t[2]=0.802, t[3]=2.2559); none align
   with the 0.5 d grid. DP reported optimum 152.0 d, but the
   reconstructed (times, tofs) was UDP-infeasible (`feas=False`, viols
   `[0, -6, 0, 19]`). Root cause: reconstruction uses bucket-gap as tof
   instead of actual stored tof, and the 0.5 d grid is structurally
   too coarse to represent bank's ≤0.05 d t-precision.
4. **E-519b** (`scripts/ch2_e519b_leg_refine.py`): pivoted to
   continuous leg-wise refinement using direct Lambert calls — no
   grid involved. For each leg k, sweep `(t_k, tof_k)` over a fine
   1D grid; if a shorter arrival is found with feasible dv and
   downstream legs still feasible at their original tofs, accept and
   cascade chronology. One pass.
5. **E-519c** (`scripts/ch2_e519c_shave_refit.py`): attempted finer
   sweep + downstream re-fit (each candidate triggers an O(48 × 200)
   Lambert refit downstream). At ~30 min/leg wall, killed after 1
   shave (0.0021 d on leg 47). The refit cost is the bottleneck;
   this needs proper SLSQP for further gains.

## Results

| Method | Reported mk | UDP-feasible? | Banked? | Comment |
|---|---|---|---|---|
| E-519 DP (0.5 d grid) | 152.0 d | **No** | — | F1 + reconstruction bug |
| walk_perm_chrono S1 (bank perm) | 142.89 d | yes | (was prior bank) | continuous t |
| walk_perm_chrono S2 (bank perm) | 152.9 d | yes | — | finer wait → WORSE |
| **E-519b leg refine** | **142.8359 d** | **YES** | ✓ **BANKED** | leg 47 shaved 0.055 d |
| E-519c shave-refit (killed) | 142.8338 d (1 leg only) | n/a (in progress) | — | refit too expensive |

**Current bank: 142.8359 d** (verified `kt.fitness` returns
`[142.835867, 0, 0, 0, 0]`, `kt.is_feasible = True`).

## Verdict + analysis

**verdict:** refutes (C6 confirmed) + F1 (DP grid too coarse)

**C6 / B1 confirmed** — walk_perm_chrono was suboptimal on bank perm.
A continuous, non-greedy refinement on (t_k, tof_k) for just one leg
(leg 47) shaved 0.0554 d. This is a small absolute number but a real
methodological breakthrough: every prior comparison of perms via
walk_perm_chrono was in distorted units. The 30k+ unique perms
validated in E-509 may include some that, after E-519b-style
refinement, beat the original bank by more than 0.055 d.

**F1 simultaneously confirmed** — the time-expanded DP on a 0.5 d
quantum grid is fundamentally incapable of competing with
walk_perm_chrono's continuous t (which inherits Lambert's
arbitrary-precision t input). To make a grid-based DP competitive,
quantum would need to drop to ≤ 0.005 d (×100 memory and precompute).
The leg-refinement approach (E-519b) sidesteps this by staying
continuous throughout.

**Non-monotonicity reconfirmed** — walk_perm_chrono S2 (wait_dt=0.2)
on bank perm yields **152.9 d**, worse than S1's 142.89 d. The
greedy commits more in finer time, escaping local optima less. This
matches Probe C of the 2026-05-30 audit.

## What this opens up

1. **Apply E-519b refinement to other validated perms**: E-509's 30k+
   perms might harbor sub-142.83 d candidates after refinement that
   we discarded as "≥ 151" in greedy units. Worth re-evaluating the
   top-100 by E-509-greedy-mk.
2. **Proper SLSQP/IPOPT on (times, tofs) per perm**: the E-519c refit
   bottleneck is real; SLSQP would be ~100× faster than the grid
   sweep. Run as joint NLP with Lambert dv as a constraint via
   penalty. ~50-line script.
3. **Multi-start basin hopping on bank perm**: random (times, tofs)
   initializations + SLSQP; look for non-bank basins. Was never
   tried.
4. **Re-evaluate the C2 decomposition row**: bank's per-leg LB of
   84.82 d (audit §1.3) is still the theoretical floor on bank perm.
   We've moved from 142.89 → 142.84; the gap to LB is 58 d. Most of
   C2 remains unrealized.

## Memory update needed

`ch2-small-floor-14292.md` and `ch2-small-audit-2026-05-30.md`
both reference "bank at local opt for (times, tofs)". This was
**wrong in the strict sense** — bank was at walk_perm_chrono-greedy
local opt, not (times, tofs) local opt. The new bank at 142.8359 d
is a closer-to-true local opt under coordinate descent.
