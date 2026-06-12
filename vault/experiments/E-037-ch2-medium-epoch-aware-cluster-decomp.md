---
id: E-037
type: experiment
tags: [experiment, ch2, medium, kttsp, epoch-aware, cluster-decomposition, bank]
date: 2026-06-12
status: BANKED medium 228.9748 -> 195.7748 d (-33.20d); crosses r3 (216.95) by 21.18d
bank_before: 228.9748
bank_after: 195.7748
instance: medium.kttsp (n=181)
script: scripts/ch2_e563_medium_epoch_aware.py
related: [[E-034-ch2-large-epoch-aware]], [[ch2-medium-bank]], [[ch2-large-first-bank-topology]]
---

# E-037 — Ch2 medium: epoch-aware cluster-decomposition

## Result

Ported the large-instance epoch-aware recipe (E-034) to medium and broke
a plateau that 3 prior permutation-search runs (E-547/550/551) could not:

- **195.7748 d** official `kt.fitness`, viols `[0,0,0,0]`, all 181 nodes
  covered. **Beats the bank (228.9748d) by 33.20d**; **beats r3 (216.95d)
  by 21.18d** → medium moves **rank 4 → rank 3 (+1.33 pts, ×4/3)**.
- Guard-banked via `scripts/ch2_e563_bank.py` (independent re-score +
  round-trip + backup `.bak.e563` / `/tmp/bank_bak/medium_*.json`). The
  build agent wrote a candidate to `/tmp` only; the bank write was done
  separately after verification.

## Method

Decompose the cheap-arc graph into components; epoch-aware re-order each
segment's interior with **fixed bridge endpoints**, DP-time on the v2
epoch table used only as a *relative* driver, iterate. The single best
perm is then re-timed bank-faithfully on the 160-tof fine grid (matches
E-540) for the official verdict.

- Search converged on the v2 proxy: 220.45 → 206.29 → 199.57 (iters 0-2),
  flat thereafter.
- Fine re-timing realized **195.77** — *better* than the 199.57 proxy
  because the v2 40-tof table is ~19d pessimistic.

## Medium structure & binding constraint

- 4 SCC cheap components, sizes **[121, 20, 20, 20]**, density 9.77%.
- Inter-component bridge graph is a **star centered on the big component
  (1)**: smalls (0,2,3) connect only to 1, and comp 2 has no incoming
  bridge → the tour is *forced* to start in comp 2, and visiting 0/3
  forces out-and-back excursions that split comp 1 into 3 runs.
- That topology is fixed by connectivity, **not** a bank flaw → the lever
  was epoch-aware re-ordering of segment interiors, not topology change.

## Lesson (reinforces E-034)

The earlier medium plateau was a **timing-proxy artifact**: a
fixed-reference-time tof is orthogonal to the chronological walk cost.
Permutation search around the bank (E-547/550/551) was stuck in a basin
defined by the *wrong* cost; recomputing transition cost at the real
arrival epoch is what unlocks the improvement. The same recipe has now
won on large (2225→1049d) and medium (229→196d); small is in flight
(E-564, E-038-to-be).
