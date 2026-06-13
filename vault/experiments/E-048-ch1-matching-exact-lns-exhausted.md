---
id: E-048
type: experiment
tags: [experiment, ch1, matching, matching-i, matching-ii, exact, lns, gurobi, cpsat, exhausted]
date: 2026-06-13
status: EXHAUSTED — both matching instances are deep local optima robust to connected-region exact LNS; the leaderboard gap needs a stronger GLOBAL exact solver than our restricted Gurobi / time-boxed CP-SAT
instance: matching-i / matching-ii
script: /tmp/gurobi_lns2.py, /tmp/gurobi_lns_ii.py, /tmp/cpsat_probe_ii.py (bg agents adb22f05, a29e2af0)
log: runs/ch1/91_gurobi_lns_s11.log, runs/ch1/matching_ii_lns_s11.log, runs/ch1/matching_ii_lns_s22.log, runs/ch1/matching_ii_cpsat.log
related: [[E-039-ch1-matching-evaluator-audit]], [[O-017-leaderboard-2026-06-13]], [[E-004-ch1-matching-i-exact-polish]], [[E-005-ch1-matching-ii-coop-mip-lns]]
---

# E-048 — Ch1 matching-i & matching-ii: strongest exact LNS exhausted

## Context

E-039 left the matching lever as "exact-solver power on the pure 3-index ILP."
This session applied the strongest open-source method available and pinned the
limit precisely.

## Method (the strongest neighborhood we can run)

**Connected-region Gurobi ILP-LNS:** BFS a connected conflict region (rows
sharing an e/l/d node) grown to ≤~680 rows — the largest block that fits
Gurobi 13's RESTRICTED (non-production) license, which hard-caps a model at
~2000 vars+constraints (the full 25k/92k models error out with "Model too
large for size-limited license"). Free all selected rows in the block,
re-solve to PROVEN optimality with Gurobi, accept strict gains. Plus a global
**CP-SAT feasibility probe**: full model + the cut `objective ≥ bank + 0.001`,
warm-hinted, 2 workers, 2400 s.

## Results — both instances NULL

| instance | bank Σw | live r1 (gap) | exact block re-opts | gains | CP-SAT obj>bank probe |
|---|---|---|---|---|---|
| matching-i  | 33,338.184 | 33,555.61 (0.65%) | 66,660 | 0 | UNKNOWN @2400s |
| matching-ii | 72,204.293 | 73,714.03 (2.05%) | 22,700 | 0 | UNKNOWN @2400s |

Zero improving moves across tens of thousands of exact block re-optimizations
on each instance ⟹ **the bank is optimal within EVERY ≤680-row connected
block.** The CP-SAT global probe could neither improve nor prove optimality in
40 min (a budget timeout on a 25k–92k-var model, not an optimality proof).

## Interpretation

The leaderboard headroom (competitors reach r1, proving a higher optimum
exists, esp. 2.05% on matching-ii) combined with a NULL small-block exact LNS
means **any improving move requires changing MORE THAN ONE ~680-row block
simultaneously** — a neighborhood larger than the restricted license can
reach. Competitors evidently out-muscled this with a stronger GLOBAL exact
solve (unrestricted Gurobi/CPLEX) or a specialized 3-index assignment method
(Lagrangian relaxation / column generation).

## Open angle launched (NEVER-STOP)

CP-SAT has no license size cap, so a **large-neighborhood LNS using CP-SAT as
the block solver** (free ~2000–6000-row sub-instances spanning ≥2 of the small
blocks, re-optimize time-boxed, accept gains) is the one untried open-source
angle that directly targets the plateau. Launched 2026-06-13 (agent abfe9c6c);
verdict pending. If it also plateaus, both matching instances are definitively
exhausted under all our open-source options → the lever becomes a user
license/$ decision (unrestricted commercial solver), not an algorithm we can
run here.

## EV

Matching is ×1 weight (easy). Even cracked, the per-instance gain is a few
ranks (a few points). Do NOT sink further open-source compute beyond the
pending CP-SAT-LNS test; the dominant Ch1 value remains elsewhere and the
campaign's dominant unrealized value is SUBMISSION of the RANK-1 medium /
RANK-2 large banks (O-017).
