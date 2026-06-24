---
id: E-586
type: experiment
tags: [experiment, ch2, large, kttsp, lns, windowed-destroy-repair, bank, recovered-candidate]
date: 2026-06-13
status: BANKED — large 1013.2886 → 971.0669 d (−42.22 d), feasible (viols [0,0,0,0]), independently re-scored + round-trip verified via scripts/ch2_e586_bank.py
instance: ch2-large (hard.kttsp, n=1051)
script: scripts/ch2_e586_large_window_continue.py, scripts/ch2_e586_bank.py (bg agent a4f79ab6)
log: runs/ch2_v3/ (E-586 continue seeds)
related: [[E-034-ch2-large-epoch-aware-reorder]], [[E-034-ch2-large-epoch-aware-reorder]], [[O-017-leaderboard-2026-06-13]], feedback-experiment-health-checks
---

# E-586 — Ch2 large: recovered + extended windowed-LNS bank → 971.07 d

## The unexpected finding (NEVER-STOP deep-dive payoff)

A Ch2-large deep-dive agent (audit-evaluator-first) reproduced the live bank
exactly (official UDP scores `solutions/upload/large.json` = 1013.2886 d,
feasible) — confirming the 2.4× gap to r1=424.62 is REAL, not a re-score bug.
Then it surfaced a **buried, never-banked candidate**: the prior E-578 windowed
destroy-repair LNS (8 h run, 2026-06-12) had descended to **979.768 d** but was
**killed by a mamba-lock error before the banking step**, leaving the result
unverified in `/tmp/ch2_large_window_cand_s2.json`. Official re-score: 979.7676 d,
feasible — 33.5 d better than the live bank, silently lost.

## Method (two compounding, basin-escaping effects)

The gap was already exhaustively decomposed by prior work (E-041 idle=0 fat
tail; E-042 ruled out global surrogate/fixpoint/greedy-NN/Or-opt; E-046 refuted
fine-grid global reorder = the TD-TSP epoch-shift trap). Per anti-oscillation
discipline these were NOT re-derived. The one lever that escapes the basin is
**monotone windowed destroy-repair LNS** (E-578). Applied as:
1. **fine-grid re-walk** of the 979.768 candidate (n_steps=2400, E-045 sweet
   spot) → **974.764 d** with zero search;
2. **continued windowed LNS** from there (`ch2_e586_large_window_continue.py`,
   2 seeds) → **971.067 d**.

## Result — BANKED

| | makespan (d) | feasible | viols |
|---|---|---|---|
| prior live bank | 1013.2886 | yes | [0,0,0,0] |
| **new bank** | **971.0669** | yes | [0,0,0,0] |

`scripts/ch2_e586_bank.py` independently re-scored `/tmp/ch2_large_cand.json`
with the official `KTTSP.fitness` (hard.kttsp), confirmed feasible + strictly
better + round-trip match, backed up the old bank
(`solutions/upload/large.json.bak.e586` + `/tmp/bank_bak/large_20260613_050540.json`),
and wrote the new bank. **−42.22 d total.** Valid 1051-permutation, 5/5 exc,
idle=0. Two LNS seeds still running (TL=70 min) may push slightly lower → re-bank
if they win.

## EV / verdict

Mechanically high-value (clean, fully verified −42 d) but **point-EV ≈ 0** under
the binary rank threshold: large stays RANK 2 (r2=1143.56, secure with a now
even larger margin), and r1=424.62 remains unreachable without a from-scratch
epoch-robust global TD-TSP solver that three prior attacks (E-042/E-044/E-046)
failed on — confirmed structural, not a marginal-search problem. The improved
bank strengthens the rank-2 margin / tie-breaker at zero cost. **Lever for r1 =
multi-day global rebuild; do NOT chase incrementally.**

## Process lesson

33.5 d of improvement sat unbanked because a crash killed the run before its
banking step. Reinforces feedback-experiment-health-checks: long LNS runs
must checkpoint-and-bank incrementally, not only at the end. The loop should
sweep `/tmp/*cand*.json` for un-banked survivors after any run that died
abnormally.
