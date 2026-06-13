---
id: E-589
type: experiment
tags: [experiment, ch2, large, kttsp, retime-dp, departure-time, timing-floor, bank]
date: 2026-06-13
status: BANKED — large 934.4452 → 932.5304 d (−1.91 d), feasible (viols [0,0,0,0]), independently re-scored + round-trip via scripts/ch2_e586_bank.py. Timing axis now FLOORED for the fixed tour.
instance: ch2-large (hard.kttsp, n=1051)
script: ch2_e590_retimedp_large (bg agent ae7a8945), guard-bank scripts/ch2_e586_bank.py (CAND repointed to /tmp/ch2_large_retimedp_cand.json, then reverted)
related: [[E-587-ch2-large-lkh-trap-and-waiting-lever]], [[E-040-ch2-medium-ultrafine-retime]], [[ch2-large-first-bank-topology]]
---

# E-589 — Ch2 large: global retime-DP floors the timing axis → 932.53 d

## Setup
Follow-on to [[E-587-ch2-large-lkh-trap-and-waiting-lever]]: the E-588 greedy
departure-time waiting lever (−7.63 d → 934.45) was proven a **myopic special
case of the ultrafine-retime-DP** (the E-040 forward Bellman departure-bucket DP
that floors medium/small). Large's pipeline (windowed-LNS + earliest-feasible
chrono walk + greedy waiting) had **never** run the global retime-DP, so it was
the dominating closure to try. Adapted `scripts/ch2_e568_medium_ultrafine_retime.py`
to large (n=1051), keeping the banked permutation + 5 exc-bridge assignment FIXED,
optimizing ONLY departure times; bounded δ∈[0,12 d] wait windows for tractability
(full 180k-bucket horizon infeasible), fine 0.01 d delta + 0.0167 d tof grid.

## Result — BANKED 932.5304 d (−1.91 d)
| | makespan (d) | feasible | viols |
|---|---|---|---|
| prior bank (E-588 greedy) | 934.4452 | yes | [0,0,0,0] |
| **new bank (retime-DP)** | **932.5304** | yes | [0,0,0,0] |

Same 1051-perm, 5/5 exc (legs [149,416,566,807,957], max dv 598.18≤600), idle
29.59 d over 248 legs (vs greedy 17.25 d over 36). Guard-banked via
scripts/ch2_e586_bank.py (CAND temporarily repointed to the distinct
/tmp/ch2_large_retimedp_cand.json, then reverted); backups .bak.e586 +
/tmp/bank_bak/large_20260613_074940.json. Independently re-scored feasible twice.
**Validation caveat (resolved):** walk_perm_chrono at its COARSE default params
(18 d / 180 steps / wait_dt=1.0) falsely reports ok=False at leg 958 — it does the
same on the BANK perm itself, because it can't resolve the leg-957 exc-bridge at
coarse resolution. At fine params (40 d / 2400 / 0.25) the walk passes; kt.fitness
(authoritative) confirms feasible. **Any future large validation must use fine
walk params.**

## Key finding — the "Bellman dominance" here is RESOLUTION, not policy
The DP win over greedy reduces to a finer wait/tof grid, NOT a smarter policy. The
scalar earliest-arrival frontier is provably globally optimal for this problem
(per-leg min-arrival is monotone in input epoch: an earlier arrival's
reachable-departure set is a superset, so holding a dominated later state never
helps — including through the 5 fixed exc legs). Greedy E-588 already used that
same min-arrival objective, just at a 0.25 d wait quantum; the DP's 0.01 d grid
found shorter transfers the coarse quantum missed. The two tracked within ~1 d for
most of the tour; the DP pulled ahead only in the **dense endgame cluster (legs
~1000-1050)** where fine timing matters.

## Verdict — timing axis FLOORED; residual is structural
Under the fixed permutation + fixed exc-assignment, large's departure timing is now
at its optimum (932.53). δ∈[0,12 d] was rarely binding, so a wider window helps
little. **Residual gains require changing the node PERMUTATION or exc-bridge
placement, not retiming** — and pure reordering hits the epoch-shift trap (E-587),
so the only trap-free reorder is chrono-walk-evaluated local search. Launched
agent a4aafdcd = endgame-cluster joint reorder+retime (chrono-walk-evaluated,
trap-free) to test the last residual. **Session large total: 1013.29 → 932.53 d
(−80.76 d, −8.0%).** Point-EV still 0 (rank-2 secure, r2=1143.56; r1=424.62 =
2.2× gap, now confirmed reachable ONLY by a from-scratch global time-dependent
solver co-optimizing order+timing — three global attacks + LKH + retime-DP all
floor short of it).
