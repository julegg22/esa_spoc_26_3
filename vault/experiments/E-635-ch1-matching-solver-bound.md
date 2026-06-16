# E-635 — Ch1 matching i/ii are SOLVER-BOUND (free MIP tools exhausted)

**Date:** 2026-06-16
**Verdict:** Both Ch1 weighted 3-D-matching instances plateau below the
leaderboard leaders with every free solver tried. The gap is **solver-bound**,
not algorithm-bound: closing it needs a stronger (commercial/academic) MIP
solver, not a better heuristic.

## Banks vs leaders (2026-06-16)

| Instance | bank | leader r1 | gap | our rank |
|---|---|---|---|---|
| matching-i  | 33,352.99 | 33,555.62 | −202.6 (0.61%) | 4 |
| matching-ii | 72,206.52 | 73,714.03 | −1,507.5 (2.05%) | ~4–5 |

(matching-i bank improved 33,338.18 → 33,352.99 this session via coop-MIP-LNS,
E-626, guard-banked; backup `matching-i.json.bak.20260616.e626`.)

## Tools tried, all plateau

1. **Warm coop-MIP-LNS** (HiGHS sub-MIPs): matching-i +14.8 then converged;
   matching-ii 0 improvement over many fair rounds (E-626/627).
2. **Monolithic HiGHS B&B** (E-628, 2h, warm): ROOT-STUCK — dual frozen 34,120,
   primal frozen 33,353, gap 2.30%, 2.1M LP iters, never branched out of node 0.
3. **Diverse non-warm multistart** (E-630/631/632, 12 basins): only one fluke
   basin beat the bank (+11.4, lost to variance); bank ≈ free-LNS ceiling.
4. **SCIP 10.0** (pyscipopt, free academic) (E-633/634): matching-i identical
   plateau to HiGHS (obj 33,353, dual 34,118, gap 2.30%, no primal gain in 25min);
   matching-ii ROOT-STUCK 2h on the 92k-var model (node 1, no primal gain).

## Why solver-bound

The leaders' scores are achieved feasible solutions, so the integer optimum is
≥ leader and sits within the LP bound (matching-i 34,120). Two strong free MIP
B&C engines (HiGHS, SCIP) both stall at the root LP relaxation on these
set-packing models (15k–30k cliques, 25k–92k binaries) and neither tightens the
dual nor improves the primal. This is the classic regime where commercial
solvers (Gurobi/CPLEX) — with far stronger presolve, cut separation, and
primal heuristics for set-packing — typically close the remaining 0.6–2% gap
quickly.

## Recommendation (user-gated)

Research institutions (e.g. Honda RI) typically have **free academic Gurobi or
CPLEX licenses**. Solving these two MIPs with such a solver would very likely
reach/near the optimum ⇒ **high-probability top rank on matching-i (×1) AND
matching-ii (×4/3)** — the only clearly high-probability top-rank lever found in
the campaign. Until such a tool is available, matching is at its free-tool
frontier; no further free-solver compute is warranted.

See [[objective-optimal-not-points]] (high-probability architecture gate) and
[[basin-overarching-search]].
