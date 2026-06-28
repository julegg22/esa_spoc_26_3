---
id: E-747
type: experiment
tags: [ch2, large, lns, destroy-repair, epoch-shift-trap, refuted]
date: 2026-06-28
status: REFUTED — naive perturb + greedy-retime produces 0 feasible candidates (epoch-shift fragility, C-036). The worst-leg target was right; the move/evaluator was wrong
related: ["[[E-742-ch2-large-global-lns]]", "[[C-036-epoch-shift-trap]]", "[[C-034-time-aware-beam-narrow-window-tdtsp]]", "[[C-026-dp-on-time-expanded-graph]]", "[[ch2-large-first-bank-topology]]"]
corrects: []
---
# E-747 — Worst-leg destroy-repair LNS on comp0: defeated by epoch-shift fragility

The E-742 headroom decomposition localized Ch2-large's gap precisely: comp0 = 93% of flight at 1.345 d/leg, with
**103 legs >2d carrying 40% of the flight** and a median-floor of ~452d. comp0 pass-2 (segment or-opt) plateaued at
890.99 — a small-move local optimum. The hypothesis: a **larger, targeted** move — destroy the R=12 comp0 cities
arriving via the worst legs, greedily reinsert them at cheapest faithful positions within their comp0 run (run
endpoints fixed → 5 bridges preserved), full-retime, accept if better — would escape it.

## Result — 0 feasible candidates in 45 iterations
Baseline reproduced 890.99 (pos-control OK), but **every** destroy-repair candidate came back infeasible
(`try infeas`), none banked. ~26 s/iter.

## Diagnosis — the epoch-shift trap (C-036), not a tuning issue
The bank tour is a finely-tuned chronological chain. Removing a few cities and **re-timing the whole tour greedily
from t=0** shifts every downstream epoch; the greedy earliest-arrival walk then strands on some later leg whose
cheap window has moved — so the candidate is infeasible *regardless of how good the local repair was*. Compounding
it, the repair scored insertions at **epoch 0** (cheap to rank) but cities are actually visited hundreds of days
in, so the chosen positions aren't even feasible at the real epoch. Both are the same failure: **a TD tour cannot
be perturbed-then-re-timed** — order and timing are inseparable ([[C-036-epoch-shift-trap]]).

## The lesson (reasserted) — carry the exact clock during construction
The campaign's methods that actually thread this TD structure **co-optimize timing with order, carrying an exact
running clock per state**: the time-aware beam ([[C-034-time-aware-beam-narrow-window-tdtsp]]) reached 558/601 on
comp0; DP-on-ultrafine-grid ([[C-026-dp-on-time-expanded-graph]]) solved small. Perturb-then-retime (this) and
static-order-then-retime ([[E-744-ch2-large-global-td-solver]]) and window-discretize-then-realize
([[E-746-ch2-small-time-expanded-gtsp]]) all strand on the same trap. **The worst-leg TARGET is correct** (that is
where the 209d to rank-2 lives); the move must be an exact-clock local search (segment re-DP / beam-repair around
the worst legs), not a perturbation. That is the next build for the large rank-2 lever.

## Bank impact
None. Ch2-large unchanged at 890.99 (rank-3, held). Nothing submitted.
