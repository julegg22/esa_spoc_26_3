---
id: S-2026-05-24
type: session
tags: [session, ch1, trajectory, breakthrough, bug-fix, lesson, methodology]
date: 2026-05-24
created: 2026-05-24
participants: [JJ, Claude Code]
claude_model: claude-opus-4-7[1m]
commits: 3
created_nodes:
  - "[[L-012-solver-assumption-audit-before-research-grade-verdict]]"
  - "[[ch1-eccentric-orbit-fix]] (memory)"
  - "[[LESSONS-LEARNED.md]] (top-level)"
banked_changes: []  # production sweep pending — sweep was killed for solver-speed optimization
---

# S-2026-05-24 — Ch1 trajectory eccentric-orbit bug found; pipeline-audit lesson

## Scope

Multi-hour Ch1 trajectory ultrathink session driven by user push
("the leaders have an answer; HRI are optimization experts not
astrodynamicists"). Started believing rank-3 required research-grade
patched-conic SOI handoff; ended with a single-line bug fix in
`solve_arrival_dv` that unlocks the per-pair masses needed for rank-3.

## Timeline (chronological)

### Phase 1 — "30000× gap" diagnosis
- User asked "what are the numbers to beat?" → confirmed R3 = 452,820 kg vs our 14.82 kg.
- Computed Hohmann theoretical Hungarian bound = 445k kg → concluded gap is structural.
- Hypothesized patched-conic SOI handoff needed (1-2 days).

### Phase 2 — User pushback "reframe from scratch"
- User: "HRI are optimization experts not astrodynamicists — must be more direct."
- Investigated solve_transfer_direct, solve_transfer_dc bugs: found wrong residual (speed only, not direction).
- Built Lambert + 3-D DC, got 794 kg for (0,0). Felt validated.

### Phase 3 — Diverse-pair validation showed solver-not-universal
- 20 random pairs spanning LEO/MEO/GEO + various inclinations: **0/20 valid**.
- Even nearly-coplanar (E27→L116, Δi=0.09 rad = 5°) failed.
- Concluded: patched-conic SOI necessary.

### Phase 4 — User pushback "heavy optimization should work"
- User: "Contendants face same problem — solvable with SOA means."
- Tested pure-optimization paths (NM 11-var, DE): NONE found feasibility.
- Confirmed: feasibility manifold too thin (1e-36 volume) for blackbox.

### Phase 5 — Library-research dead-end
- Surveyed poliastro (archived), openlunar (2D planar only), pykep, lunar-horizon-optimizer.
- No drop-in solution.

### Phase 6 — Patched-conic v1 attempt
- Built Earth-Lambert→SOI + Moon-Lambert→LLO solver.
- 0/576 ICs valid even for (0,0). The 2-body prediction doesn't survive BCP propagation.

### Phase 7 — THE FIX: eccentric-orbit window
- Noticed dataset has 150 Moon orbits with eL > 0.3 (max 0.65).
- Realized solve_arrival_dv rejects when `|r - aL| > 384m` — only valid for circular orbits.
- For eL=0.65, valid arrival r spans 6,700 km — we were rejecting all of it.
- Wrote `solve_arrival_eccentric` targeting actual (aL, eL, iL).
- Re-tested previously-failed pairs.

### Phase 8 — BREAKTHROUGH
- (0,0) coplanar: 14.82 → 819 kg (55×)
- (267,181) GEO+eL=0.65: FAIL → **2037 kg**
- (266,234) GEO+eL=0.64: FAIL → 1211 kg
- (27,116) LEO+iE=0.11: FAIL → 332 kg
- 5/6 previously-failed pairs now positive.

### Phase 9 — Systematic correction
- User requested "lessons learned + treat affected branches."
- Wrote LESSONS-LEARNED.md (top-level).
- Added META.md invariant: "Solver-assumption audit before 'hard' verdict."
- Fixed `solve_arrival_dv` in source — all 22 callers auto-benefit.
- Annotated O-002 and O-012 with post-fix reinterpretation.
- Wrote L-012 (this lesson).

## Hypotheses opened/closed

- **Implicit H (open since 2026-05-19)**: Ch1 trajectory requires
  research-grade physics. **CLOSED — REFUTED**. The leaders use
  textbook techniques; we had a solver bug.
- **H-40 (now superseded)**: patched-conic SOI handoff for inclined
  pairs. Not needed; the eccentric-arrival fix handles inclined Moon
  orbits naturally.

## Open paths

- Production sweep with optimized eccentric-arrival solver (current
  solver is 15× slower than needed; trimming seeds + max_nfev).
- After sweep: Hungarian assignment → chromosome → bank.
- Expected mass: 200,000-500,000 kg (rank 3-5 territory).

## Key methodology lessons

- **Solver-assumption audit** (L-012): before declaring "needs better
  methods," verify each solver assumption against data distribution.
- **Theoretical bound check is cheap**: 2 minutes computed Hungarian
  upper bound = 445k kg. Achievement ratio = 30000× should have
  flagged solver bug on day 1.
- **Diversity test is non-negotiable**: testing only on (0,0)
  validated a degenerate case where the bug didn't manifest.

## Commits

- `e6cfa13` — Lambert+3D-DC solver hits 794kg on (0,0)
- (current branch) — Lessons learned + solve_arrival_dv source fix +
  annotated observations + L-012 lesson + S-2026-05-24 session note
