---
id: E-041
type: experiment
tags: [experiment, ch2, large, kttsp, gap-decomposition, diagnostic, topology]
date: 2026-06-12
status: DECISIVE — 624d gap to r1 is ordering/phasing-recoverable; static 4-comp decomposition is an artifact; global epoch-aware rebuild justified
instance: hard.kttsp (n=1051)
script: scripts/ch2_e571_large_gap_probe.py
related: [[E-034-ch2-large-first-bank]], [[ch2-large-first-bank-topology]], [[O-014-competitor-inference]], [[ch2-large-bank]]
---

# E-041 — Ch2 large: gap-decomposition probe (1048d → r1=424d)

## Result (decisive diagnostic, not a search)

**The entire 624d gap to rank-1 is ordering/phasing, not a physical
floor.** Two measurements on the 1048.98d bank:

**Part A — realized per-leg tof distribution (idle = 0):**
- mk 1048.98d = tof_sum 1049.0d exactly (**idle = 0** — nothing to
  squeeze on timing; makespan IS the sum of transfer times).
- tof mean 0.999d, median 0.718d, p10 0.184, p90 1.787, max 24.23.
- Fat tail: **654 legs > 0.5d (excess 616.9d)**, 334 > 1.0d (excess
  355d), 87 > 2.0d, 38 > 3.0d (excess 105d).
- r1 = 424.62d ⇒ avg 0.404d/leg vs our 0.999d. **Bringing the 654
  over-0.5d legs down to 0.5d alone → ~432d ≈ r1.**

**Part B — epoch-availability probe (150 nodes × 11 epochs in [0,1100d]
× ≤40 static-cheap neighbors, find_earliest_transfer):**

| epoch | min-tof p10 | med | p90 | mean feas-nbrs | frac feas |
|---|---|---|---|---|---|
| all 0→1100 | **0.050** | **0.150** | 0.45–0.96 | **36.8 / 40** | **1.00** |

The min available cheap tof is **median 0.150d at EVERY epoch**, and
every sampled node keeps ~37 feasible cheap neighbors at every epoch
(frac_feas = 1.00 throughout). Overall median min-cheap-tof **0.150d vs
our realized avg leg 0.999d** → short hops are abundant; we're just not
routing through them.

## Why this refutes the decomposition premise

The static cheap-adjacency (E-533) splits n=1051 into 4 components
[601,150,150,150] with **zero cheap inter-component edges** — but that
is one reference epoch. Part B shows that at the *realized* epochs the
cheap graph is richly connected (≈37 cheap neighbors per node, every
epoch). So the 4-component structure that forced the 5-bridge
"comp0-last" topology (E-559→E-562b) is a **static-snapshot artifact**,
and the frozen-topology per-piece OR-Tools refinement (E-562b: split
points, bridge endpoints pinned; only interiors re-ordered) plateaued at
1048d because it never re-routes across the (epoch-dependent) rich
connectivity. The lever is a **single global epoch-aware tour with a
freed topology**, not piecewise decomposition.

## Next (E-042)

Global epoch-aware OR-Tools rebuild over all 1051 nodes: seed from the
current 1048 order, build a global epoch-aware cost (find_earliest_transfer
at each node's walk-epoch over its cheap candidates), one global
open-path GLS solve (long budget), re-walk → fresh epochs, iterate. Guard
-bank only if feasible & < 1048.98d. Cheap-only Hamiltonian may even
exist (≤5 exc may be unnecessary).

## Lesson

When a decomposition is built from a STATIC cost/adjacency snapshot but
the true cost is epoch-dependent, the decomposition can be an artifact
of the snapshot. Probe connectivity vs epoch BEFORE trusting a static
decomposition — here it converted a presumed "structural research
frontier" into a quantified, ordering-recoverable 624d gap in ~30s of
compute. (Same family as the E-040 finding that timing grids hide free
days — static modeling choices silently cap the search.)
