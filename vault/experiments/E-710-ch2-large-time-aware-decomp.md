# E-710 — Ch2-large time-aware decomposition: the coarse-tof discovery + fine-tof beam

**Date:** 2026-06-23
**Goal (user):** develop the time-aware decomposition (the competitor's cluster+LKH paradigm) for the
601-giant, in parallel with the Ch1-trajectory cores.

## Foundation chain (methodology: validate the evaluator BEFORE the search) — all positive-controlled

| Step | Question | Result |
|---|---|---|
| M0a | does table-propose + 1-faithful-verify reproduce a full faithful scan? | only 14/25 agree → suspicious |
| M0b | **is the cached 1d table corrupt?** audit 200 table-cheap cells | **stored (epoch,tof) verifies 100/100 → table is 100% FAITHFUL.** BUT a full faithful scan at 0.01d steps finds the cheap tof only 22/200 (11%); tof gap |true−stored| median **0.002d** |
| M0c | are cheap windows continuous in departure-epoch? | **median window 12d** (grid spacing 1.0d), 88% wider than grid → cheap windows are CONTINUOUS & WIDE |

### The discovery
Cheap transfers live in **~0.002d-wide tof bands** (≈3 minutes of flight time). **Every prior faithful
construction in this project (greedy 350, shorttof_walk, the SA retimes) scanned tofs at 0.01–0.05d and was
BLIND to ~89% of cheap edges.** This means:
1. The memory's **"beam overfit" (orders that look 0.3 d/leg on the table but 'retime to 1099d')** was
   substantially a **coarse-tof RETIMING artifact** — the retimer's 0.01–0.05d grid stepped over the narrow
   cheap band and was forced onto long tofs. Fine-tof retiming does not inflate.
2. Cheap windows are CONTINUOUS in epoch (12d wide), so a cheap tof exists at essentially any departure via
   a fine local search — the 950-epoch table over-samples them; the binding resolution was always **tof**.

### What the discovery does and does NOT overturn
- **DOES:** removes the "table-beam overfit" obstacle that closed the dense-precompute path (E-670/672).
  A beam's order can now be faithfully retimed accurately (fine tof) — the makespan measurements were wrong.
- **Does NOT (yet):** the **367/601 greedy wall is separate** — it is frontier exhaustion (a global
  sequencing problem), independent of tof resolution (the table-aware greedy already used the windows and
  still walled at 367). Confounded test: greedy-earliest **re-timing of the fixed bank order strands at leg
  52** because re-timing desyncs a fixed order's arrival times (bank is feasible only with its coordinated
  tofs). So the lever is a **fine-tof BEAM that builds order+timing together**, not retiming.

## The fast-faithful oracle (the enabling primitive)
`fine_cheap_arrival(i,j,row,t)`: table proposes the open grid epoch & tof hint → **fine local verify**
(0.0005d band around the hint, ~bounded Lamberts) → exact cheap arrival. ~100× cheaper than a full faithful
scan, immune to overfit (realized tof is exact). This is the accurate-AND-fast evaluator the prior work
lacked (faithful beam W=12 was <50/601 in 6min; this does W=60 at ~5s/depth).

## M2: fine-tof beam (running)
`ch2_giant_fine_beam.py W=60 K=18`: table-pruned candidates + fine faithful verify + global lookahead
(keep W earliest-time states, dedup by last-city for diversity). Threading **0.14 d/leg** early (rank-1
0.404). Checkpoints best path every 25 depths to `cache/ch2_giant_fine_beam_best.json` (resumable).
**Decisive question:** does W>1 lookahead thread past the 367 greedy wall toward a complete 601 @ <500d?

### RESULT (W=60, K=18): the global lookahead BREAKS the 367 wall
The beam threaded **558/601** (vs greedy 367 / static-TSP 10), makespan **283d for the 558** (0.508 d/leg;
0.29-0.41 d/leg through depth 500 — BELOW rank-1's 0.404), then stranded with **43 cities** unvisited
(beam collapsed 60->25 states near the end). This **overturns the E-709 "genuine wall / moonshot" verdict**:
the 367 greedy wall was frontier-exhaustion that GLOBAL LOOKAHEAD dissolves. A complete tour on this
trajectory extrapolates to ~300-380d -> UNDER rank-1's 424. The remaining gap is the last 43 hard-shell
cities. Two identified levers: (1) the beam never used the 5 allowed EXCEPTION legs (dv<=600, pure-cheap
only) - those are exactly for hard tail transitions; (2) beam-width collapse near the end starves diversity.

### M3 (running): W=120, K=24 + exception legs (<=5) for the hard frontier
Aims to close the 43-city gap into a complete 601-tour. If complete & makespan < 424 -> rank-1 lever for
large: stitch the 3x150 satellites, faithful udp verify, guard-bank (NEVER submit, escalate). [pending]

Refines [[E-709-ch2-large-audit]] (the "overfit" sub-claim partially retracted), [[M-general-foundation-then-search]] (evaluator was again the flaw), [[E-019-ch2-edge-compute-marginal-value-zero]]. Followed by [[E-713-ch2-large-rank1-attempt-suite]] (the rank-1 closer attempts).
