---
id: E-741
type: experiment
tags: [ch2, large, backtracking, warnsdorff, completion-wall, fast-evaluator]
date: 2026-06-28
status: DONE — backtracking DFS does NOT complete (217<beam's 338); 601-completion is combinatorial, not a speed wall
related: ["[[E-739-ch2-large-fast-batched-evaluator]]", "[[E-729-ch2-large-low-degree-bottleneck-and-cheap-slot]]", "[[E-713-ch2-large-rank1-attempt-suite]]", "[[ch2-large-first-bank-topology]]"]
---
# E-741 — Ch2-large: backtracking DFS fails the 601-completion; the residual is combinatorial, not speed

The E-739 fast evaluator made faithful construction fast (greedy beam 191→338 at 0.25 d/leg). E-739's named
residual was "completion needs backtracking." Built it (`ch2_giant_backtrack.py`): **Warnsdorff most-constrained-
first ordering** (visit about-to-be-isolated low-degree cities first) **+ DFS backtracking** on dead-ends, on the
fast faithful evaluator, bounded by an expansion cap.

## Result — backtracking is WORSE, and explodes
- **Best depth 217/601, then hit the 400k-expansion cap stuck there** (exp went ~226 at depth 200 → 400,001 at
  depth 217). **217 < the greedy beam's 338.**
- Why worse: Warnsdorff grabs low-degree cities via long "ugly" early hops (1.0-1.4 d/leg vs greedy's 0.18),
  which uses up phasing and leaves a worse mid-tour state. Greedy's short hops keep more options open longer
  (338) before stranding.
- Why it explodes: the dead-end is **far upstream** — a city visited around depth ~100-200 isolates a later
  city. Local backtracking near depth 217 cannot undo 100+ committed cities (a branch-6 tree can't reach that far),
  so it thrashes 400k combinations in a narrow region without escaping.

## Verdict — the 601-completion is a genuine combinatorial wall, NOT a speed wall
The fast evaluator (E-739) removed the SPEED barrier (faithful eval ~5ms/nbr) but **not the COMBINATORIAL one**:
constructing a complete time-dependent Hamiltonian path through the 601-node comp0 defeats both greedy beam (338)
and Warnsdorff+backtracking (217). This is the same structural bottleneck E-729 (118 low-degree cities) and E-713
identified — a far-upstream choice determines whether a late low-degree city is reachable, which no left-to-right
construction (greedy or constrained, with or without local backtracking) resolves.

**The genuine residual lever** (research-grade, the competitor's tool): a **global TD-Hamiltonian solver** — LKH /
Concorde / a large-neighborhood metaheuristic that optimizes the WHOLE permutation at once, using `batch_earliest`
as the now-fast faithful cost oracle. The campaign's prior time-expanded GTSP attempts (E-713/E-718) used the
BLIND evaluator and bucketing that mismatched the feasible bands; with E-739's fast FAITHFUL evaluator as the
edge-cost oracle, a faithful global solver becomes the next thing to build — but it is a substantial,
research-grade build (time-expanded graph construction + LKH integration), not a heuristic tweak.

## Ch2-large arc — honest summary
Y=932.53 (rank-2-walled). This session: built the named E-735 missing tool (fast batched faithful evaluator,
E-739, validated 1e-11, ~50×), proved it effective (faithful reach 191→338), and showed the remaining wall is
**combinatorial completion**, not evaluation speed. Two corrected rationales along the way (E-710 narrow-band
claim, E-587 reorder-trap). The lever is now precisely characterized: rank-2 needs a global TD-Hamiltonian solver
on the fast faithful cost — the cleanest, well-scoped (if heavy) next build. Bank unchanged, nothing submitted.
