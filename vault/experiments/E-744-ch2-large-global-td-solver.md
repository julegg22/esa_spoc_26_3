---
id: E-744
type: experiment
tags: [ch2, large, global-td-solver, lkh, epoch-shift-trap, rank-2]
date: 2026-06-28
status: STAGE-1 — built+tested LKH-on-static-cost global TD solver; strands (epoch-shift trap); next = time-expanded GTSP on the faithful evaluator
related: ["[[E-741-ch2-large-backtracking-and-completion-wall]]", "[[E-739-ch2-large-fast-batched-evaluator]]", "[[E-718-ch2-large-glkh-resolution-mismatch]]", "[[ch2-large-first-bank-topology]]"]
---
# E-744 — Ch2-large global TD-Hamiltonian solver (user-requested rank-2 lever)

User: build+test the global TD-Hamiltonian solver (the E-741 residual, the only path to r2=682). Tools available:
elkai + the LKH-2.0.9 binary (E-718) + GLKH-1.1; dense1d gives the time-aggregated comp0 cost.

## Stage 1 — LKH on the static (min-over-epochs) comp0 cost: STRANDS (epoch-shift trap, confirmed)
`scripts/ch2_giant_lkh_td.py`: built the 601x601 ATSP cost = min-over-epochs cheap tof (dense1d), ran LKH (ATSP,
runs=5), chrono-walked the result faithfully, with an epoch-aware cost-update iteration.
- **LKH static tour cost 10014d** — it used a ~9999 penalty edge ⇒ **comp0's cheap graph has no Hamiltonian
  CYCLE** (ATSP needs a cycle; the cheap graph is ~21% dense, 74802/360600 edges). (A PATH formulation — dummy
  node — would avoid this; the deeper issue is below.)
- **Chrono-walk STRANDS at leg 0.** The static-optimal order assumes every edge at its OWN best epoch, which is
  impossible in a single timeline — the E-587 epoch-shift trap in full. The epoch-aware iteration can't bootstrap
  (0 realized legs to learn from when it strands immediately).

## Verdict — naive LKH-on-static-cost is the wrong frame; the fix is TIME-EXPANDED GTSP
A single static cost cannot represent a time-dependent transfer (the feasible tof depends on departure epoch).
The principled global TD solver is **time-expanded GTSP**: replicate each comp0 city into K time-window copies;
cluster = city; an arc (i@t_a -> j@t_b) exists iff a cheap transfer i->j departing in window t_a arrives in
window t_b (computed by the FAST FAITHFUL evaluator, batch_earliest); GLKH solves "visit exactly one copy per
cluster" = jointly pick the order AND each city's epoch. **This is the competitor's likely method.** E-718 tried
it but with the BLIND evaluator + 12d buckets vs ~0.002d feasible bands (1000-6000x mismatch) ⇒ infeasible arcs.
The NEW enabler (E-739 fast faithful evaluator) builds the time-expanded arcs CORRECTLY at fine resolution — the
exact gap E-718 lacked.

## Next build (the real solver)
Time-expanded GTSP: (1) pick K time-windows per city spanning [0, ~900d] (adaptive to each city's cheap-departure
bands from batch_earliest); (2) build arcs only where batch_earliest confirms a cheap feasible transfer between
windows; (3) GTSP cost = arrival-time / tof; (4) GLKH solve -> joint order+epochs; (5) chrono-validate +
kt.fitness. Bounded by K (windows/city) x 601 nodes; with K~8-16 that's ~5-10k GTSP nodes — GLKH-tractable.
Substantial but the faithful-arc construction is the part E-718 couldn't do and now can. (Local comp0/smalls
reorder + STM continue in parallel toward incremental rank-3 headroom + ch1 rank-5.)
