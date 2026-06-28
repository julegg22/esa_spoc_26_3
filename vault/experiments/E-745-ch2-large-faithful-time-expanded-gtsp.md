---
id: E-745
type: experiment
tags: [ch2, large, small, gtsp, time-expanded, glkh, faithful-arcs, build-cost]
date: 2026-06-28
status: PARTIAL — faithful-per-node arc build is too slow at n=1051 (≈11h projected); tractable at n=49 (E-746). Solver formulation built + correct; large-scale arc construction needs dense-table lookup, not per-node faithful eval
related: ["[[E-744-ch2-large-global-td-solver]]", "[[E-718-ch2-large-glkh-time-expanded]]", "[[E-739-ch2-large-fast-batched-evaluator]]", "[[C-035-time-expanded-gtsp]]", "[[C-036-epoch-shift-trap]]", "[[ch2-small-floor-14292]]"]
corrects: []
---
# E-745 — Faithful time-expanded GTSP (E-744 stage 2): formulation built, large-scale arc build is the wall

Stage 2 of the global TD-Hamiltonian solver (E-744 named time-expanded GTSP as the principled solver after
LKH-on-static-cost stranded at leg 0). Built the full pipeline (`ch2_giant_texp_gtsp.py`): each comp0 city →
K=8 time-window copies placed at its **own cheap-departure regions** (quantiles of dense1d cheap-out epochs, not
E-718's uniform 12-day buckets); arcs `(i@w_a → j@w_b)` from the **fast faithful evaluator** (`batch_earliest`,
E-739); AGTSP with a dummy-depot cluster (open chronological path) solved by GLKH; decode → faithful chrono-walk.

## Result — the formulation is right; the **build cost** is the wall
- Graph: 601 cities × K=8 = **4808 nodes**, ~108 arcs/node.
- **Arc construction is O(nodes × neighbours × deps × tofs × revs) of faithful Lambert** — measured
  **~8.5 s/node** (node 500 reached at 4249 s). Full build ≈ **11 hours**, before GLKH even runs. Killed as
  impractical for the session.
- Root cause: faithful per-node evaluation **re-scans** every edge at every one of its window copies. That is the
  price of arc *fidelity* — and it does not scale to n=1051.

## The two tractable paths (large)
1. **Dense-table lookup arcs (E-718 style, but with E-745's adaptive windows + open-path AGTSP).** Build arcs by
   reading the precomputed `dense1d` cheap-tof-per-edge-per-epoch table (≈1-day resolution) — *seconds*, not
   hours. Loses sub-day arc precision, but the decode's **faithful chrono-walk** recovers exact timing, and ~1-day
   resolution is enough for arc *existence*. This is the pragmatic large-scale build; E-718's strand came from
   coarse 12-day buckets + cycle (not open-path) GTSP, both fixed here.
2. **Faithful arcs only for a candidate sub-graph** — prefilter to the ~30 cheapest neighbours per node, cutting
   the per-node cost ~5×. Still hours; only worth it layered on (1).

## Cross-scale finding (the live lever moved to small)
The resolution-vs-tractability tradeoff of [[C-035-time-expanded-gtsp]] is **scale-dependent**: at n=1051 the
faithful build is an 11h wall; at **n=49 (Ch2-small) it is tractable** — 49×K≈1200 nodes, faithful arcs
affordable. And small's standing diagnosis ([[ch2-small-floor-14292]]) names *exactly* this solver as its missing
architecture (joint sequence+epoch global search). So the **highest-EV application of this build is Ch2-small**,
not large — pursued in **[[E-746]]** (rank-6 → target rank-1). Large rank-2 via this route remains open but is
gated on the dense-table-lookup arc build (path 1), not on the solver, which is built and correct.

## Bank impact
None (diagnostic + tooling). Ch2-large bank unchanged at 890.99 (rank-3, held), improved this session via the
comp0 pass-2 assembly (separate lever). Nothing submitted.
