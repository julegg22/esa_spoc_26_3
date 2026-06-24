---
id: E-038
type: experiment
tags: [experiment, ch2, small, kttsp, epoch-aware, cluster-decomposition, refuted]
date: 2026-06-12
status: REFUTED — basic reorder NULL (big=0); phase-2 perturbation HUNG (DP/evaluator on degenerate perm) + is dominated by solve_open_path; bank 116.3738d holds
bank_before: 116.3738
bank_after: 116.3738
instance: small.kttsp (easy, n~49)
script: scripts/ch2_e564_small_epoch_aware.py
related: [[E-037-ch2-medium-epoch-aware-cluster-decomp]], [[E-034-ch2-large-epoch-aware-reorder]], [[E-618-ch2-small-grasp-multistart-floor]], [[M-general-foundation-then-search]]
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
**DP-on-ultrafine-grid** (E-529, [[M-general-foundation-then-search]]),
which already optimizes timing at the real arrival epoch. Medium/large
banks came from a *fixed-reference-time tof proxy* (the proxy⊥reality
trap), so epoch-aware re-timing had large slack to recover. Small has no
such slack — its evaluator was already epoch-faithful. **No proxy gap →
no epoch-aware lever.**

## Phase-2 (REFUTED — hung + dominated)

The script's phase-2 (`E564_PHASE2_S`) is randomized **relocate-perturbation**
of comp0-interior nodes + DP re-time, keeping improvements. A full-budget
run (`PHASE2_S=9000`, pid 97493) **HUNG**: log froze at "iter 1" for 36 min
at 99% CPU with zero `[P2]` output (phase-2 tries are fast and print every
2000 → silence = stuck on a single `dp_time_perm`/`kt.fitness` call for a
degenerate perturbed perm). Same class as the E-554 c2 DP spin. Reaped.

Beyond the hang, phase-2 is **dominated by design**: each phase-2 try just
relocates a node and re-times, but the deterministic epoch-aware step
already runs `solve_open_path` (a CP/OR-tools open-path optimizer) on every
comp interior — a *stronger* optimizer than random relocate. So random
perturbation can at best rediscover the interior order `solve_open_path`
already found (`big=0` on small). To be viable it would need (a) a per-try
wall-clock watchdog or finite-cost pre-filter to survive degenerate perms,
AND (b) a reason to beat solve_open_path, which it doesn't have. Shelved.

## Lesson (so far)

The **basic** epoch-aware interior-reorder lever only pays where the
incumbent was built on a fixed-reference-time proxy. Small's DP-on-fine
bank is already epoch-faithful, so the deterministic reorder is null —
unlike medium/large, there is no proxy slack to recover. Moving small
r6→r5 (gap ~4.6d to r5≈111.79) therefore needs a **topology change**
(comp0 is force-split into 24+16 runs by exception bridges; a different
split or exception allocation is untried) — NOT interior reordering or
relocate-perturbation, both of which are already covered by
`solve_open_path`. A topology search is a larger build with uncertain EV
for a ×1-weight near-floor instance, so it is **low priority** vs.
higher-weight levers. Same caveat applies to medium (its interiors are
also solve_open_path-optimal), so a medium relocate-perturbation phase-2
would be **dominated too** — the real untried medium lever is likewise
topology, not interior search.
