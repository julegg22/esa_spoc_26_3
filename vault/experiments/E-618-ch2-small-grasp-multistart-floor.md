---
id: E-618
type: experiment
status: done             # draft | running | done | invalidated
tags: [ch2, small, kttsp, grasp, multi-start, independent-construction, basin-overarching-search, free-method-floor]

hypothesis: "The 112.996d Ch2-small bank was found by deterministic earliest-arrival greedy + LNS (ONE construction basin). Independent randomized-greedy (GRASP) multi-start, building whole tours from scratch with a restricted candidate list, samples DIFFERENT permutation basins the deterministic argmin pruned away — and may reach a shorter-tof permutation closer to R1 (101.65)."

created: 2026-06-15
ran_start: 2026-06-15
ran_end: 2026-06-15
duration_runtime: "~3.2h observed (24h budget), 4 workers; null decisive well before budget"

# reproducibility
code: |
  scripts/ch2_e618_grasp_multistart.py   (GRASP construction on ultrafine table + DP-polish + guard-bank)
  imports evaluate_perm_dp, INST, OUT, FINE from scripts/ch2_e529_dp_alns.py
inputs: |
  reference/SpOC4/.../problems/easy.kttsp  (n=49, dv_max=100/dv_exc=600/n_exc=5, max_time=200d — OFFICIAL header)
  /tmp/ch2_small_tcoupled_ultrafine.npz    (cheap/exc min-tof per epoch bucket, q=0.05d, T=4000)
  solutions/upload/small.json              (bank 112.996d)
outputs: |
  runs/ch2_v3/94_e618_grasp_multistart.log
  guard-bank backup: solutions/upload/small.json.bak.20260615.e618 (bank UNCHANGED — nothing banked)
seed: per-worker rng = wid*104729 + 7; rcl=3
env: micromamba spoc26, python 3.13.13
---

## Question

The 112.996d bank is the local-descent attractor of ONE construction family
(E-022 deterministic earliest-arrival greedy + cluster-insertion LNS; E-529 SA;
E-617 ILS all live in/around it). E-617 proved that bank an ISOLATED optimum —
~14.8k local perturbation+repair attempts, its entire 3–7-node neighborhood is
>1% worse. The one untested search family is INDEPENDENT from-scratch
construction: does a randomized-greedy multi-start, sampling orderings the
deterministic argmin pruned, ever land in a different (shorter-tof) basin that
DP-polishes below 112.996? This is the basin-overarching test the campaign
thesis ([[basin-overarching-search]]) calls for on Ch2-small.

## Method

GRASP on the precomputed ultrafine table (same edge model as the DP evaluator, so
a constructed tour's greedy makespan and its DP makespan are consistent):
- Randomized-greedy construction: at each step gather cheap candidates at the
  current epoch bucket (advance up to WAIT_MAX=40 buckets on dead-end), fall back
  to exception legs if budget remains, sort by arrival bucket, pick uniformly from
  the top rcl=3 (Restricted Candidate List).
- Each completed permutation is DP-polished (`evaluate_perm_dp`) for its provable-
  optimum schedule (departure epochs + exc-leg selection).
- Guard-bank any tour < 112.996 (backup-first, round-trip `kt.fitness` verify).
- 4 independent workers, distinct seeds, 24h budget.

## Result — DECISIVE NULL

~3.2h, 4 workers, ~22k+ COMPLETED independent constructions (dpfail=0 — every
completed tour DP-evaluates cleanly), **best_seen=123.175d**, plateaued across the
final 4 health-check ticks. **NO construction came within 10d of the 112.996
bank; nothing banked.**

Construction dead-ends ~99.8% of attempts (≈300 attempts/s/worker, ~0.18%
complete) — the direct fingerprint of the near-forced cheap graph: 33/49 nodes
have ≤2 cheap out-edges, so any randomized (non-argmin) hop strands the tour. The
deterministic earliest-arrival greedy that built the bank succeeds precisely
because it follows the forced argmin path; GRASP's randomization breaks the forced
routing and either dead-ends or completes into a worse (~123d) basin.

## Conclusion — Ch2-small R1 gap is a genuine FREE-METHOD floor

Three orthogonal families now converge on 112.996 as the free-method floor under
our architecture (construction + DP-timing on the fixed cheap graph):
- **E-616** — tof≤8 precompute cap does NOT fragment the cheap graph (0 new dv≤100
  edges at tof∈(8,40]); sparsity is PHYSICAL, not an artifact.
- **E-617** — bank is an ISOLATED local optimum (3–7-node neighborhood all >1%
  worse, ~14.8k attempts).
- **E-618** — independent randomized construction cannot reach within 10d of the
  bank basin (~22k from-scratch tours floor at 123.175d).

The leaderboard front (refetch 2026-06-15) sits far below: R1 101.65, a new
r2/r3 cluster at 108.77, r4/r5 at 111.76–111.79 — all inside E-618's unreachable
zone. Competitors reach them with a fundamentally different architecture (joint
sequence+epoch global search — time-expanded LKH / SA / GA with epochs as free
variables), the pipeline we never built. Our 112.996 = rank 6 (submittable, 5
wpts); closing to the 108–111 cluster would need that competitor pipeline, a
high-effort build whose best realistic payoff is rank 6→5 (+1 wpt) given how
crowded the 108–111 band is ⇒ low ROI vs submitting the existing banks.

**Ch2-small free-method search frontier CLOSED.** Do not re-open without the
joint sequence+epoch global-search architecture (not another
construction/local-move method on the fixed graph). See
[[ch2-small-floor-14292]], [[basin-overarching-search]], [[deep-single-prompt-audit]].
