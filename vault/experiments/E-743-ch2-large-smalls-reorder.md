---
id: E-743
type: experiment
tags: [ch2, large, smalls, reorder, rank-3-headroom]
date: 2026-06-28
status: DONE — reordered the 3 never-touched small clusters, banked +25.2d (924.93->899.69); the untapped lever
related: ["[[E-742-ch2-large-lns-headroom]]", "[[E-739-ch2-large-fast-batched-evaluator]]", "[[ch2-large-first-bank-topology]]"]
---
# E-743 — Ch2-large: reorder the 3 SMALL clusters (the untapped headroom)

User asked "any more headroom for ch2-large." DECOMPOSITION of the 924.93 bank found it: comp0 598 legs @1.117
d/leg (75%), **smalls 447 legs @0.505 d/leg = 226d (25%)**, bridges 5 legs 2d, idle 29d. **All prior reorder work
(beam, backtracking, finesearch) was on comp0; the 3 smalls were NEVER reordered** (assumed "already solved" per
E-592's TD-greedy result). PROBE: the largest small (150c) runs 66.1d in the bank but a greedy-NN re-walk from its
entry epoch completes at **12.0d (0.08 d/leg)** — a 54d unconstrained gap.

## Result — +25.2d banked (924.93 -> 899.69, feasible, guard-banked, .bak_smalls, NOT submitted)
`scripts/ch2_giant_smalls_reorder.py`: endpoint-constrained (keep each small's first+last = the bridge gateways)
greedy-NN reorder of all 3 smalls from their bank entry epochs (0.0, 351.8, 748.5), splice, faithful full-tour
re-time (mr=20), guard-bank. **All 3 reordered -> 899.69d.** rank-3 headroom vs next 1028.59 = 129d (was 104);
r2=682 gap 218d.

## Honest magnitude
The probe's 66->12d (54d/small, ~135-180d total) was OPTIMISTIC: unconstrained, single-small, and not in the
full-tour faithful context. The realized gain is **+25.2d total** over the 3 smalls — the endpoint constraint
(gateways fixed for the bridges) + the faithful mr=20 retime + cascading interactions shrink it. Still the
largest single reorder win of the session (comp0 reorder was +7.6d). Combined session reorder: 932.53->899.69
(-32.8d). Remaining headroom: or-opt on top of greedy-NN per small + a 2nd comp0 pass (epochs shifted) may add a
few more d; rank-2 still needs the global TD solver. Lever found: the smalls were the overlooked chunk.
