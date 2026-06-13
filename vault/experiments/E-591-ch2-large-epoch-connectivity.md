---
id: E-591
type: experiment
tags: [experiment, ch2, large, kttsp, epoch-connectivity, cheap-graph, intrinsic-floor, r1-gap]
date: 2026-06-13
status: DIAGNOSTIC (no bank change) — explains the 2.2× r1 gap as CONNECTIVITY, not order/timing. Optimistic floor under the fixed 5-exc topology ≈ 882.6 d (still 2.08× r1=424.62); residual 95.1 d of intrinsic tof is unremovable by any reorder/retime.
instance: ch2-large (hard.kttsp, n=1051)
script: scripts/ch2_e591_epochconn_heavy.py (bg, runs/ch2_e591_epochconn.log, /tmp/ch2_large_epoch_conn.json)
related: [[E-589-ch2-large-retime-dp-timing-floor]], [[E-587-ch2-large-lkh-trap-and-waiting-lever]], [[ch2-large-first-bank-topology]]
---

# E-591 — Ch2 large: the r1 gap is cheap-graph CONNECTIVITY, not order/timing

## Question
After E-587 (LKH reorder = epoch-shift trap), E-589 (retime-DP floors timing),
E-590 (endgame reorder NULL), and the lookahead agent's monotone-arrival proof
(greedy-earliest IS the order-fixed timing optimum), every BOUNDED lever on the
fixed 5-exc topology is exhausted at bank 932.53 d. The open question gating a
multi-day global-rebuild decision: **is the 2.2× gap to r1=424.62 reachable by a
smarter global solver, or is it instance-inherent connectivity?** Test: for each
heavy-tof source node, sweep 75 epochs across the [0, 3000 d] horizon and count
how many admit a CHEAP (Δv<100) outgoing transfer. If a heavy node has cheap
epochs *somewhere*, a global TD reorder could in principle place it there
("epoch-locked"). If it has cheap transfers at NO epoch, it is "intrinsic" — no
order/timing can make it cheap under the current exc budget.

## Result — 14 epoch-locked, 22 intrinsic; optimistic floor ≈ 882.6 d
| metric | value |
|---|---|
| bank makespan | 932.53 d |
| leader r1 | 424.62 d |
| heavy legs (tof>3 d) | 36, summing 159.0 d |
| heavy source nodes | 36 |
| → epoch-locked (cheap at SOME epoch) | 14 |
| → **intrinsic (cheap at NO epoch, 0/75)** | **22** |
| flagged worst 739 / 343 / 753 | all **intrinsic**, 0/75 |
| rough floor if all epoch-locked heavies relocated | **≈ 882.6 d** |
| residual intrinsic tof (unremovable) | **95.1 d** |

## Interpretation — the gap is structural connectivity, capped well above r1
1. **Even a PERFECT global TD reorder under the fixed 5-exc topology caps at
   ≈882.6 d** (−50 d from bank), still **2.08× r1=424.62**. The remaining 95.1 d
   of intrinsic tof belongs to 22 nodes that have NO cheap transfer at ANY of 75
   sampled epochs — no permutation or departure-time choice removes it.
2. **The 3 most-flagged heavy nodes (739, 343, 753) are intrinsic, not
   epoch-locked.** They were the prime suspects for "relocate to a cheap epoch";
   the diagnostic kills that hope — they are simply expensive to reach with cheap
   Δv regardless of when.
3. **Therefore r1=424.62 cannot use our partition + exc allocation at all.** To
   beat ~882 d you must spend exception bridges (high-Δv legs) ON the intrinsic
   nodes — but our 5 bridges are fully committed to the comp0↔3-smalls star just to
   keep the tour FEASIBLE (the smalls are reachable only via exc). Reallocating
   breaks coverage. r1 almost certainly uses a fundamentally different
   feasibility structure (different partition + exc placement, or a different
   exc-budget regime), reachable only by a from-scratch global solver that
   co-optimizes partition + exc + order + timing under a chrono walk.

## Verdict — large is connectivity-bound; within-topology headroom is point-0
- **r1 basin confirmed NOT a search-strength problem.** Three global attacks
  (E-042/044/046) + LKH (E-587) + retime-DP (E-589) + this connectivity audit all
  converge: the gap is the cheap-graph topology, not the optimizer.
- **Within-topology residual ≈ 50 d** (932.53 → ~882.6 optimistic) exists but is
  **point-EV 0** (large stays rank-2; r2=1143.56 secure by >200 d), and it is
  trap-bound (epoch-shift on reorder, monotone-saturated on timing) — only a
  trap-free chrono-walk-evaluated cluster relocation of the 14 epoch-locked heavies
  could chip at it, with diminishing ROI.
- **The honest campaign read:** large's only point-positive move is rank-2→1,
  which needs <424.62 — proven out of reach for bounded autonomous methods. Large
  is FLOORED for points at rank-2. The realized value here is the *closed
  question*: no more "smarter solver" attempts are warranted; the bank stands.
- **Session large total: 1013.29 → 932.53 d (−80.76 d, −8.0%), rank-2 secure.**
