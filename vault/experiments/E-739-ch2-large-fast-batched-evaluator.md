---
id: E-739
type: experiment
tags: [ch2, large, fast-evaluator, batched-lambert, beam, rank-2-lever]
date: 2026-06-28
status: ACTIVE — built the fast batched faithful evaluator (the named E-735 lever); global beam running on it
related: ["[[E-735-ch2-large-deepaudit-medium-machinery-untried]]", "[[ch2-large-first-bank-topology]]", "[[E-725-ch2-large-fast-faithful-evaluator]]"]
---
# E-739 — Ch2-large: the fast batched faithful evaluator (E-735's named lever), + global beam

E-735 concluded large is walled by **evaluation SPEED**: faithful eval ~250ms/edge ⇒ global TD construction
(601-depth beam, millions of evals) infeasible; the missing tool is a **fast batched faithful evaluator** the
682/391 competitors must have. Built it.

## What was built (`scripts/ch2_fast_transfer.py::batch_earliest`)
A numba `parallel=True` primitive for BEAM EXPANSION: from city i at epoch t, compute the **earliest cheap
(dv≤100) arrival to ALL of a city's ~150 cheap neighbours in ONE call**, parallel over neighbours (each scans a
[t,t+W] dep grid × tof, early-exit at first cheap tof). Reuses the validated E-725 numba Kepler-eph + Izzo
multi-rev Lambert.

## Validation + speed (measured)
- **Faithful: `transfer_dv` matches official `kt.compute_transfer` to 3.79e-11**; `batch_earliest` reproduces a
  bank comp0 leg's arrival (67.857 vs bank 67.853d).
- **Key speed finding: `kt.max_revs=20`** was the hidden cost (40 Lambert iterations/edge). Short-tof cheap hops
  are low-rev — at **max_revs=3, tof_hi=2d, dstep=0.1: ~5 ms/neighbour** (vs the old ~250 ms/edge oracle, ~50×).
  A full 601-city beam is now **~2.5 h** (was ~16 h / infeasible). Restricting to short-tof (low-rev) is
  *desirable* — it forces the short-hop regime that defines rank-1 pace (0.65 d/leg). It is CONSERVATIVE, not
  optimistic: max_revs=3 sees a subset of cheap edges (66 vs 103/150 reachable), never a false-cheap edge.

## The beam (`scripts/ch2_giant_fasteval_beam.py`)
Faithful global beam over comp0 (601): states dominated by last-city (min arrival), width BW, expansion =
`batch_earliest` over unvisited cheap neighbours, keep K earliest. This is the FIRST comp0 beam that is BOTH
faithful AND fast (prior beams were faithful-but-slow stranding ~191, or fast-but-optimistic-table reaching 558).
Running (BW=25, K=8, mr=3, tofhi=2, start city 2 @67.1d). **Binary:** completes 601 at <0.65 d/leg ⇒ assemble
+smalls+bridges, validate kt.fitness; if <682 ⇒ RANK-2 lever realized. Strands/drifts ⇒ the phasing bottleneck
(E-729 low-degree cities) is real even with the right fast tool, and rank-2 needs more (wider beam / backtracking
/ the multi-rev edges). Result pending (~2.5h). Bank unchanged, nothing submitted.

## Beam run 1 result (BW=25, mr=3, tofhi=2)
**Threaded 339/601 faithfully at 0.24-0.27 d/leg, then STRANDED** (no feasible successor). This is the key
datum: **339 vs the prior FAITHFUL beam's 191** — the fast evaluator nearly doubled faithful reach, at
*well-below-r1 pace* (0.27 vs r1 0.65). It strands because mr=3/tofhi=2 restricts connectivity (66/150 reachable)
— the low-degree bottleneck cities (E-729) need the multi-rev edges. So: the fast evaluator unlocks faithful
construction, and a plain greedy beam gets to 339; completion is gated by the connectivity/phasing wall, not pace.
**Run 2 (mr=5, tofhi=2.5 → 79/150 reachable, BW=35) launched** to push past 339. If a complete 601 emerges at
<0.65 d/leg, the comp0 path (~160-250d vs bank 876d) assembles toward a rank-2/rank-1 large tour. If it still
strands, the residual is backtracking / a wider beam / a proper TD-LKH on the faithful short-tof cost — but the
*evaluator* lever (the named E-735 missing tool) is delivered and demonstrably effective (191→339 faithful).

## Beam run 2 (mr=5, tofhi=2.5, BW=35) + VERDICT
**Stranded at 338/601 — essentially identical to run 1's 339**, despite more connectivity (79 vs 66 reachable)
and wider beam. ⇒ the strand is a **structural bottleneck at a specific tour position (~338)**, NOT a general
connectivity/width issue — a plain greedy beam walls there regardless. **Final verdict:** the fast evaluator (the
named E-735 lever) is DELIVERED and effective — it took the faithful comp0 beam from 191→338 at *well-below-r1
pace* (0.25 d/leg). But **completion of 601 needs more than a greedy beam**: the residual sub-lever is
**backtracking** (on strand, pop the deepest committed state and try alternates) or a TD-LKH / large-neighborhood
search on the faithful short-tof cost using `batch_earliest` as the move evaluator. That is the clean, named next
build for any future Ch2-large rank push — the evaluator that makes it tractable now exists and is validated.
NB: 338 faithful at 0.25 d/leg means the *easy* 56% of comp0 is threadable at rank-1 pace; the hard ~263 cities
(the E-729 low-degree set) are the structural completion problem the backtracking search must solve.
