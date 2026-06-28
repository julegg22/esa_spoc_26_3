---
id: E-742
type: experiment
tags: [ch2, large, lns, reorder, rank-3-headroom, faithful-retimer]
date: 2026-06-28
status: DONE stage-1 — faithful full-tour retimer realizes finesearch reorder = +7.6d (932.53->924.93 banked); ~66d was oracle-inflated
related: ["[[E-735-ch2-large-deepaudit-medium-machinery-untried]]", "[[E-739-ch2-large-fast-batched-evaluator]]", "[[ch2-large-first-bank-topology]]"]
---
# E-742 — Ch2-large: global-LNS / finesearch realization on the complete bank (user: secure rank-3 headroom)

User chose Option 2 (global LNS on the complete bank) to secure rank-3 with more headroom (board: us 932=rank-3,
next team 1028.59; r2=682). Built `scripts/ch2_giant_lns_e742.py`: a FAITHFUL full-1051-tour re-timer (greedy
earliest-arrival; cheap dv<=100 except the 5 exc bridges [149,416,566,807,957] dv<=600; numba cheap_first_tof).

## Result — faithful retimer works at mr=20; finesearch reorder realizes +7.6d (banked)
- **The retimer is fidelity-sensitive:** at mr=5/wait=2.5 it STRANDS at leg 314 (misses cheap transfers the bank
  uses, drifts). At **mr=20 (matching kt.max_revs) / tofhi=8 / wait=12 / dstep=0.02 it reproduces the bank: 931.63d
  faithful** (pos-control, −0.9 vs 932.53 since greedy-earliest is the order-fixed optimum, E-589). Cost: ~220s/walk.
- **Assembled the E-735 finesearch comp0-segment reorders (3/3 segments) → 924.93d feasible → GUARD-BANKED**
  (932.53→924.93, `.bak_lns1`, NOT submitted). Rank-3 headroom vs next 1028.59 grows 96d→104d.
- **HONEST: the gain is +7.6d, not the finesearch's apparent ~66d.** The finesearch optimized each segment in
  isolation (fixed endpoints + entry epoch) at its 0.02d oracle resolution; the faithful full-tour re-time —
  which already re-optimizes timing greedily — only realizes +7.6d of the reorder. The bank is near its faithful
  reorder optimum.

## Stage 2 (LNS destroy-repair) — bottlenecked by retimer speed
A faithful full-tour LNS needs the mr=20 retimer (~220s/walk) — too slow for iterative destroy-repair (thousands
of walks). The fast evaluator (E-739 batch_earliest, mr=3-5) is fast but drifts/strands on the full tour (fidelity).
So a faithful global LNS is bottlenecked by the speed/fidelity tension; the per-segment finesearch (fast oracle)
already explored the reorder and its faithful value is the +7.6d now banked. **Bigger Ch2-large gains need the
global TD-Hamiltonian solver (E-741 residual), not more local reorder.** Stage-1 headroom secured; bank 924.93.
