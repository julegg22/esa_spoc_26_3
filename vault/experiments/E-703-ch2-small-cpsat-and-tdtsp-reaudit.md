---
id: E-703
type: experiment
status: CP-SAT DEVELOPMENT + DEEP REAUDIT (no bank change yet). Built the time-coupled CP-SAT properly
  (FLAW-A objective + FLAW-B truncation fixed) on a freshly-rebuilt bank-representable ultrafine table.
  Verdict: CP-SAT is INTRACTABLE at the needed resolution (215k vars/303k constraints, 1800s → 165d
  feasible, LB never left 0). OR-Tools routing (E-511) violates the time-coupling. The fast table-DP
  evaluator has a confirmed +5.5d offset from the official continuous optimum (not faithful). Remaining
  viable path under test: order search on the fast table-DP + continuous-retime the winners.
date: 2026-06-23
tags: [ch2, small, cpsat, tdtsp, time-coupling, reaudit, evaluator-faithfulness]
related: [[E-702-ch2-small-joint-basin-audit]], [[ch2-small-floor-14292]], [[M-general-foundation-then-search]]
---
# E-703 — Ch2-small: CP-SAT TD-TSP development + deep reaudit

## Mandate
User: "Start Ch2-small CP-SAT when there's headroom; test+estimate feasibility; deep reaudit /
more-straightforward approaches if you stall." After the trajectory fill freed cores.

## Foundation: rebuilt ultrafine table + the GATE
The /tmp tables were wiped; rebuilt **cache/ch2_small_tcoupled_ultrafine.npz** (0.05d quantum, 4000
epochs, coarse-prescan-masked: 1157 edge pairs of 2352 fine-scanned, ~5.6h, checkpointed/resumable).
**Bank-representability gate** (`ch2_cpsat_bankrep_check.py`): at top_k=60 only 6/48 bank legs
representable with the "nearest cell" distance growing **monotonically** with leg index — the
fingerprint of **FLAW B**: E-507's `top_k`-by-EARLIEST-ARRIVAL truncation keeps only early-epoch cells,
but a tour progresses in time so late-tour legs need late-epoch cells. At top_k=all, **47/48
representable** ⇒ the table is correct; **E-507's INFEASIBLE was a truncation artifact**, as suspected.

## CP-SAT v2 (`ch2_cpsat_v2.py`) — FLAW A & B fixed, but INTRACTABLE
Fixes: candidate cells = cheapest-arrival per **time-bin** (full-horizon coverage, bounded size);
objective = **true makespan** = max-over-cities arrival via per-city arrival IntVars (not `max t_node`).
Model: 75k vars → **214,984 vars / 303,493 constraints** after presolve. 1800s, 4 workers:
**FEASIBLE 165.55d** (far worse than bank 112.996, officially infeasible: 2 legs >600, 11 exc), and the
**lower bound never moved off 0** the entire run. ⇒ CP-SAT does pure primal local search on this model
and cannot solve it; intractable at the resolution required to beat the 2.1d gap. (No warm start was
used — a possible but uncertain rescue; the zero LB suggests the model is just too large.)

## OR-Tools routing (E-511) — coupling-violating
Reads as: edge cost = min over t_starts of (t_start+tof) = earliest-arrival **assuming optimal t_start
per edge independently** → ignores the chronological coupling; "if a leg's actual arrival exceeds the
routing optimum, the coupling is violated." Same dead end as static-LKH/iter-LKH (E-654).

## The real wall: no FAST FAITHFUL evaluator
`ch2_faithful_walk.py` positive control on the BANK ORDER:
- earliest-**departure** greedy → 152.2d (myopic: first cheap epoch often has a long tof).
- earliest-**arrival** greedy (optimal on the grid for a fixed order by domination) → **118.5255d**,
  exactly the +5.529d offset E-653 saw. Official continuous optimum (S1 CMA) = 112.996d.
⇒ even the optimal 0.05d table-DP is **+5.5d off** the official continuous optimum. The fast evaluator
is **not faithful**; the only faithful evaluator is the slow continuous CMA (~30s+/order).

## Remaining viable path (under test)
Order search **minimizing the fast table-DP**, then **continuous-retime the best orders** officially.
Prior order searches (E-609/E-617) failed because they compared table-DP candidates against the
*official* bank value (the +5.5d apples-to-oranges bug). Done correctly, IF table-DP rank correlates
with official rank, a sub-118.53 table-DP order could retime below 112.996. Decisive test: SA on the
fast walk (`ch2_walk_sa.py`) → retime the winner. (If table-DP is order-dependently offset and
uncorrelated, Ch2-small is genuinely blocked for fast methods — accept rank 6 / escalate.)

## Pivot test result (`ch2_walk_sa.py`, 4 workers × 40k iters = 160k orders)
- **The bank order is table-DP-OPTIMAL**: no order beats 118.525 on the fast walk (160k explored).
  Echoes E-609/E-702 — basin-locked, now also on the fast evaluator.
- **The continuous retime is unreliable from a non-optimal seed**: retiming the bank order seeded from
  its *walk* schedule (118.53) returns 118.5255, NOT 112.996 — the CMA is a local polisher and cannot
  bridge the 5.5d to the true optimum (which S1 reaches only because it seeds from the bank's *actual*
  112.996 schedule). So we cannot fast-evaluate an arbitrary order's true official makespan.

## VERDICT (Ch2-small fast methods EXHAUSTED, honest)
Every fast lever fails on the same rock — **the time-coupling has no fast faithful evaluator**:
| method | failure |
|---|---|
| CP-SAT time-coupled (flaws fixed) | intractable (215k vars, LB never left 0, 165d) |
| OR-Tools routing (E-511) | earliest-arrival relaxation violates the coupling |
| fast table-DP walk | +5.5d offset from official; bank is its optimum anyway |
| continuous CMA retime | faithful only from the optimum's own seed; can't evaluate other orders |
The bank **112.996 is optimal under our table + reachable search**. The competitor's 110.88 (R3) /
101.65 (R1) must come from something we cannot currently reach. **One untested coverage hypothesis**:
our table caps tof at **8.0d** — a better order may use a longer (>8d) cheap transfer we never scan;
extending TOFS past 8d is the one concrete, cheap-ish follow-up. Otherwise Ch2-small stays rank 6 and
the +2.1d to rank-3 is not reachable by the methods available. No bank change; nothing submitted.
Trajectory (the day's big lever) banked separately at **327,926 kg (+64,807 today)**.
