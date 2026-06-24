---
id: E-040
type: experiment
tags: [experiment, ch2, medium, kttsp, ultrafine-retime, bank, rank-1]
date: 2026-06-12
status: BANKED medium 195.7748 -> 192.9002 d (-2.8747d); crosses live r1 (195.6816) -> RANK 1
bank_before: 195.7748
bank_after: 192.9002
instance: medium.kttsp (n=181)
script: scripts/ch2_e568_medium_ultrafine_retime.py
related: [[E-037-ch2-medium-epoch-aware-cluster-decomp]], [[E-038-ch2-small-epoch-aware-cluster-decomp]], [[O-016-leaderboard-2026-06-12]], [[E-040-ch2-medium-ultrafine-retime]]
---

# E-040 — Ch2 medium: ultrafine re-time of the banked perm (RANK 1)

## Result

The E-037 medium bank (195.7748d) was final-timed on the E-540/E-563
fine grid: tof = `linspace(0.025, 12.0, 160)` (~0.075d spacing),
departure quantum 0.1d. The live board (O-016, 2026-06-12) showed
**r1 = 195.6816 — only 0.093d above our bank**. Re-timing the UNCHANGED
bank permutation on a 2× denser grid recovered far more than needed:

- **192.9002 d** official `kt.fitness`, feas=True, viols `[0,0,0,0]`,
  all 181 nodes covered. **−2.8747d vs bank; beats live r1 by 2.78d →
  medium RANK 2 → RANK 1 (+1.33 pts, ×4/3).**
- Guard-banked: same perm as bank (pure re-timing), independent
  fresh-process re-score 192.900157, round-trip match, strictly better;
  backups `medium.json.bak.e040` + `/tmp/bank_bak/medium_pre_e040_*`.

## Method

Per-leg ultrafine cheap/exc tof scan + exact forward DP (min-makespan
under the 5-exception budget):
- tof grid `linspace(0.025, 12.0, 319)`, departure quantum **0.05d**.
- **Superset-grid correctness:** 319 points include all 160 bank-grid
  points at even indices, and 0.05d ⊃ 0.1d departures, so the bank's
  exact (departure, tof) assignment is inside the search space ⇒ the DP
  result is **provably ≤ bank**. (A first attempt with N_TOF=320 was NOT
  a superset and was scrapped to avoid a false negative — see the small
  null below.)
- DP "earliest-reached bucket per (leg, exc-count)" relaxation keeps it
  O(legs·T·nexc); decode via predecessor backtrack; official-score the
  decoded vector.

## Why a pure re-time bought 2.87d

The makespan is `Σ tof + idle`. The bank perm is order-optimal
(E-037/E-038: interiors are solve_open_path-optimal), but its *timing*
was quantized at 0.1d departures on a 160-tof grid. Halving both
resolutions let the DP (a) depart each leg up to 0.05d more precisely
and (b) pick a marginally shorter feasible tof per leg; over 180 legs
these accumulate to 2.87d. This is the **same class of lever as E-529
on small** (DP-on-finer-grid), here applied to the medium bank whose
final timing was coarser than small's.

## Companion null (small) — P2 closed

The same tool on small (E568_PROB=small) returned mk=120.14 > bank
116.37 (WORSE → discarded). Small's bank came from E-529's ultrafine
method, NOT this uniform `linspace(0.025,12,160)` grid, so the uniform
grid is not a superset of it and cannot reproduce the bank timing.
**Small is timing-floored: its 6.385d non-tof idle is forced, not
slack** (consistent with E-038 perm-optimal + E-529 provenance). The
P2 small idle-squeeze lever is closed.

## Lesson

When a bank's final timing used grid resolution X, re-timing the SAME
perm on a strict-superset grid 2× finer is a near-free, provably-safe
improvement — but ONLY if the new grid is a genuine superset (matching
endpoints + integer-multiple quantum), else you risk a false negative.
This is the cheapest possible rank gain (no search, minutes of compute)
and applies wherever the incumbent timing grid is coarser than feasible.
Large's bank (E-562b) was epoch-aware-iterated, not uniform-grid timed,
so the same retime is unlikely to help there (and large is rank-locked
at r2 regardless until the r1=424 topology rebuild).
