---
id: E-610
type: experiment
status: done
tags: [ch2, small, kttsp, evaluator-layer, tof-granularity, assumption-audit, anti-oscillation, closure]

hypothesis: "The last accessible crack in the Ch2-small evaluator layer is the
0.05 d TOF-grid granularity of the ultrafine table (it rounds each leg's tof UP
to the grid). E-609 flagged this as the one remaining lever after closing ORDER.
Measure the OPTIMISTIC flight-reduction available from continuous (0.005 d scan +
10x refine) per-leg minimal feasible tof at the bank's own departure epochs. If
small (<~2 d) the granularity lever is rank-irrelevant and Ch2-small is closed
under our Lambert model; if large, rebuild a finer table and re-DP."

created: 2026-06-13
ran_start: 2026-06-13
ran_end: 2026-06-13
duration_runtime: "<2 min"

# reproducibility
code: /tmp/ch2_small_e610_tof_audit.py
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp (n=49, n_exc=5)
  solutions/upload/small.json (bank decision vector, mk=116.3755)
  kt.compute_transfer (the official KTTSP multi-rev Lambert Delta-v)
outputs: /tmp/ch2_small_e610.log
seed: deterministic scan (no rng)
env: micromamba spoc26, PYTHONPATH=src, OMP_NUM_THREADS=1
---

## What was done
For each of the bank's 48 legs, at the bank's OWN departure epoch t_start[k],
scanned tof from 0.02 d upward at 0.005 d resolution (10x finer than the 0.05 d
table grid) to the first tof with Delta-v <= cap (cap = 600 for the 5 exception
legs, 100 otherwise), then refined downward at 0.0005 d. `save[k] =
bank_tof[k] - true_min_tof[k]`. Sum = OPTIMISTIC flight reduction (optimistic
because it lets every leg take its own per-epoch minimum, ignoring the
chronological coupling times[k]+tofs[k] <= times[k+1] that forbids using all
minima jointly).

## Decisive result
| metric | value |
|---|---|
| bank flight Sigma_tof | 109.9893 d |
| OPTIMISTIC flight reduction (sum per-leg, coupling-free) | **1.0171 d** |
| optimistic flight floor | 108.97 d |
| optimistic makespan floor (coupling-free) | **115.36 d** |
| legs with >0.02 d savable | 20 (max single-leg save 0.0497 d) |
| R3 gap on makespan | -5.49 d |
| R1 gap on makespan | -14.72 d |

Every per-leg saving is tiny (max 0.0497 d, all <0.05 d = one grid cell, exactly
as expected for a round-UP-to-grid artifact). The savings are uniform noise at
the grid scale, not a concentrated win on any leg.

## Verdict — the Ch2-small EVALUATOR LAYER is CLOSED
The TOF-granularity lever caps at **1.02 d optimistic**, and the realizable
value is strictly less (chronological coupling forbids every leg taking its
per-epoch minimum). This is **5.4x too small to pass rank #5 (R3, -5.49 d)** and
**14x too small to reach R1 (-14.72 d)**. Rebuilding a finer TOF table and
re-DPing cannot move the rank.

This closes the last accessible crack in the evaluator/edge layer for Ch2-small:
- ORDER lever — CLOSED ([[E-609-ch2-small-global-order-search]]: 422k orders,
  big-valley, bank near-global; corrects the [[E-607-ch2-small-global-reroute]]
  router artifact caught by [[E-608-ch2-small-e607-verification]]).
- edge MEMBERSHIP — CLOSED ([[E-606-ch2-small-edge-resolution]]).
- TOF GRANULARITY — now CLOSED (this experiment, 1.02 d bound).
- bank is FLIGHT-bound, not phasing-bound (6.38 d wait, no leg waits >0.5 d).

## What the residual gap therefore IS (the same shape as Ch1 A0)
Bank flight 109.99 d vs R1 101.65 d = **8.34 d** of route headroom that is NOT
in our resolved cheap/exc edge set at any TOF resolution our Lambert model can
represent. By exact analogy to the Ch1 trajectory A0 falsification
([[ch1-trajectory-mass-lever-exhausted]] ★★★★): **our patched-conic / multi-rev
Lambert Delta-v is NOT the problem's transfer floor.** HRI's 101.65 d almost
certainly uses transfers (or an edge set) that our `compute_transfer` model
structurally cannot produce — finite-thrust, low-thrust, or a different feasible
arc family that yields shorter realizable tofs and/or admits cheap edges our
Lambert scan never finds. The lever is the **transfer MODEL**, not the table
resolution, the router, or the timing DP.

## Consequence for the campaign queue
Ch2-small is closed under every method available to the autonomous loop's
Lambert-model toolchain. Reaching R3/R1 requires re-deriving the transfer model
itself (out-of-model physics), which is a large, uncertain, multi-day build with
the same risk profile as the deferred Ch1 WSB/low-thrust work. Per the
gap-decomposition discipline, the order/edge/granularity rows are all exhausted;
the only open row is the transfer-model row, and it is not cheaply reachable.

## Methodology note (anti-oscillation)
This is the terminal step of the E-603 -> E-606 -> E-607/E-608 -> E-609 -> E-610
audit chain that began from the user's "solutions >101.65 exist, find the flaw
not the optimum" directive. The flaw chain resolved cleanly: NOT order (E-609),
NOT edge membership (E-606), NOT TOF granularity (E-610) -> the flaw is assumption
A0-Ch2 "our Lambert Delta-v is the transfer floor", the exact twin of Ch1's A0.
No oscillation: each lever was quantitatively bounded against the gap and closed.

links: [[E-609-ch2-small-global-order-search]] [[E-606-ch2-small-edge-resolution]]
[[E-608-ch2-small-e607-verification]] [[E-603-ch2-small-gap-anatomy]]
[[ch1-trajectory-mass-lever-exhausted]] [[methodology-triggers]]
