---
id: H-007
type: hypothesis
status: draft
tags: [ch2, large, ddd, milp, bannach, perspective-3]
parent: "[[O-011-hierarchical-budget-tradeoff]]"
created: 2026-05-23
priority: 2
mode: design

claim: >
  Bannach (IAC 2024) §5 DDD (Dynamic Discretization Discovery,
  Boland 2017) with TARGETED refinement — bisect ONLY chronology-
  violation arcs, not all intervals — yields a HiGHS-solvable MILP
  for Ch2 large (n=1051) within rank-3 cutoff (2072.84 d).

falsifiable_prediction: >
  After ≤ 20 DDD iterations starting from a coarse time grid (~50
  intervals), the MILP has ≤ 10⁶ binary variables and HiGHS finds
  an optimal-or-near-optimal feasible solution within 24 h wall.

estimated_effort_h: 16-32
expected_points: 12 (Ch2 large rank-3 ×(4/3)² ≈ 14 if R3 reached)
---

# H-007 — Bannach DDD with targeted refinement on Ch2 large

## Why this matters now

Our hierarchical decomposition (C-019) hit a hard ceiling at
~210/1051 nodes (O-011) — the orbital-element clustering plus exc
budget creates a structural saturation regardless of meta-route
strategy. The leaderboard shows R1 = 1251.33 d (TGMA), R3 cutoff =
2072.84 d. To score on Ch2 large, we need a fundamentally different
machinery. Bannach DDD is the standard OR approach.

## What we tried before and why it failed

S-2026-05-21 attempt: DDD with **naive bisect-all** — every time
interval was bisected each iteration. Result: 196 → 6272 intervals
in 5 iterations. Exponential blowup; HiGHS infeasibility timeouts.

## What Bannach actually does

Per Bannach (IAC 2024) §5 + Boland (2017) DDD:

1. **Initialize**: coarse time grid (e.g., 50 evenly-spaced
   intervals over the 3000 d horizon).
2. **Solve the relaxed MILP**: at this coarse grid, the LP
   relaxation gives a fractional solution `x*`.
3. **Identify violating arcs**: walk the LP/IP solution; for each
   arc (i, j, td, tof), check if its actual `compute_transfer`
   value lies within the discretized cell's bounds. If not, the
   arc VIOLATES the discretization.
4. **Targeted bisection**: bisect ONLY the time intervals
   containing violating arcs. Other intervals stay coarse.
5. **Repeat** until LP solution = IP solution = chronologically-
   valid walk.

The KEY is step 4: targeted, not blanket. Most intervals never get
bisected because they don't contain violating arcs.

## Implementation plan

### Phase 1 (4-8 h): infrastructure
- `ch2_ddd_targeted.py`: time-expanded MILP build via HiGHS
- Time grid as dynamic data structure (list of intervals, refined)
- Variable mapping: per-arc (i, j, td_idx, tof_idx) binary
- Chronology constraints as MTZ-style ordering on time-indexed
  vars
- Solver wrapper with violation detection

### Phase 2 (4-8 h): DDD loop
- Solve MILP at current grid
- Walk solution: detect chronology violations (arc enters too
  early at chosen td/tof, given the previous arc's actual
  arrival)
- Bisect only those intervals
- Re-solve

### Phase 3 (4-16 h): validation + optimization
- Test on Ch2 small (n=49) first — verify DDD converges to
  142.92 d basin (matching our existing banked)
- Scale up to Ch2 medium (n=181), expect ~274.5 d (matching
  banked) within hours
- Scale up to Ch2 large (n=1051), aim ≤ 2072.84 d

## Key risks

1. **HiGHS performance ceiling**: even with targeted DDD, the
   final MILP at n=1051 may have 10⁵-10⁶ binaries. HiGHS may
   time out. The Bannach paper uses Gurobi 8.5× faster on
   similar scales.
2. **Implementation bugs**: time-expanded ILPs have many indices;
   off-by-ones easy.
3. **Convergence speed**: 20+ DDD iterations may be needed; each
   MILP solve may take 1-4 h.

## Mitigation

- Validate on small (n=49) FIRST. If DDD-small banks 142.92 d
  (or better) in < 1 h, scale up.
- Use the Bannach paper's exact formulation, not re-derive.

## Status

Sketched — implementation pending.
