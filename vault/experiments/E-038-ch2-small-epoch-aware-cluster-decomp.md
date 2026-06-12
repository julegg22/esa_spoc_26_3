---
id: E-038
type: experiment
tags: [experiment, ch2, small, kttsp, epoch-aware, cluster-decomposition, refuted]
date: 2026-06-12
status: PARTIAL — basic epoch-aware interior reorder is NULL (big=0, 116.3738d holds); randomized comp0 relocate-perturbation (phase-2) IN FLIGHT (agent a6d7dbed)
bank_before: 116.3738
bank_after: 116.3738
instance: small.kttsp (easy, n~49)
script: scripts/ch2_e564_small_epoch_aware.py
related: [[E-037-ch2-medium-epoch-aware-cluster-decomp]], [[E-034-ch2-large-epoch-aware-reorder]], [[ch2-small-floor-14292]], [[foundation-then-search-methodology]]
---

# E-038 — Ch2 small: epoch-aware cluster-decomposition (REFUTED)

## Result

Ported the large/medium epoch-aware recipe (E-034/E-037) to small. It
found **nothing**: over 5 iterations the interior-reorder of every comp0
run returned `big=0` (no improving order), best DP **116.3755d** vs the
official bank **116.3738d** — i.e. the reorder optimum is *worse* than
the bank by 1.7e-3 d. Writes NOTHING (the script's re-validation gate
correctly refused). Bank holds at **116.3738d**.

## Why it doesn't transfer (unlike medium/large)

Small decomposes into segments `[(3,3),(0,24),(1,3),(0,16),(2,3)]` —
comp0 (the big component) is split into a 24-run and a 16-run by
exception bridges, with 3 small comps (3 nodes each) spliced between.
The epoch-aware interior reorder of the 24- and 16-runs found `big=0`
both runs, every iteration → **the bank already realizes the
chronologically-optimal interior order**.

This is consistent with the small bank's provenance: it came from
**DP-on-ultrafine-grid** (E-529, [[foundation-then-search-methodology]]),
which already optimizes timing at the real arrival epoch. Medium/large
banks came from a *fixed-reference-time tof proxy* (the proxy⊥reality
trap), so epoch-aware re-timing had large slack to recover. Small has no
such slack — its evaluator was already epoch-faithful. **No proxy gap →
no epoch-aware lever.**

## Phase-2 (in flight)

The script's phase-2 (`E564_PHASE2_S` budget) is a **different** lever:
budget-bounded randomized **relocate-perturbation** of comp0-interior
nodes, each followed by epoch-aware reorder + DP-time, keeping any
feasible improvement. This reaches space the deterministic basic reorder
(big=0) cannot. Agent a6d7dbed launched a 90s probe; a full-budget run is
the real test. Candidate-to-/tmp only; the loop guard-banks if it beats
116.3738d feasibly. Verdict pending.

## Lesson (so far)

The **basic** epoch-aware interior-reorder lever only pays where the
incumbent was built on a fixed-reference-time proxy. Small's DP-on-fine
bank is already epoch-faithful, so the deterministic reorder is null —
unlike medium/large, there is no proxy slack to recover. Moving small
r6→r5 (gap ~4.6d to r5≈111.79) therefore needs a **stronger global
search** (phase-2 perturbation, in flight) or a **topology change**
(comp0 is force-split into 24+16 runs by exception bridges; a different
split or exception allocation is untried), not deterministic interior
reordering.
