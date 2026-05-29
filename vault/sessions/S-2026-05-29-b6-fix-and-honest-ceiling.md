---
date: 2026-05-29
tags: [session, ch1, b6-fix, structural-bug, ceiling, decision]
status: B6 fix landed (small gain) — architecture ceiling confirmed at ~220k kg
bank: 215,527 kg / 296 transfers
target_R3: 453,000 kg
gap: -237k kg
---
# S-2026-05-29 — B6 structural fix + architecture ceiling confirmed

## Today's discovery: audit B6 was real but smaller-than-hoped

Sprint on B1 v2 (Lambert-to-r_apo) revealed the actual structural bug:
**`syn_to_inertial_earth` was applying R(t0) rotation to dv0 direction,
silently inverting it for t0=π configs → impactor → silent reject.**

Audit estimated <2k kg impact. Re-polish with B6 fix gave +1k kg total
across 140 polished transfers (most use t0=0 where bug was silent).

**Why I overestimated**: I assumed the bank's poor t0=π results meant
"need to find a better config" — but the bank already used t0=0
optimally. The B6 fix only unlocks new t0=π configs that happen to be
*better than* the existing t0=0 ones for that pair. That's rare.

Fine perilune sweep on (8, 175) found a t0=π config with perilune ≈
r_apo_target (the "perfect geometry"). But its DC convergence still
gave dv1=1300 m/s — the geometric alignment doesn't automatically yield
low-dv1 plane change.

## Bank trajectory across the campaign

| Date | Event | Bank |
|---|---|---|
| 2026-05-24 | Eccentric-orbit bug fix | 14k → ~100k |
| 2026-05-26 | iL-matching scoring breakthrough | 120k → 186k |
| 2026-05-27 | Audit (B1/B2/B3/B4/B5/B6) | 186k → 187k (B4+B5 only) |
| 2026-05-27 | Polish extended t2_d (+t2_d ∈ {2,3,5}) | 187k → 209k |
| 2026-05-28 | Phase A v2 + CMA-ES + Tier 1A v2 | 209k → 214k |
| 2026-05-29 | B6 polish + Phase 2 (in progress) | 214k → 215k |
| **2026-05-29 end** | | **215,527 / R3 = 453k** |

## Architecture ceiling analysis

After all known levers, bank caps around 215-225k kg. R3 (453k) requires
breaking through this ceiling. From the arithmetic:
- 41 MEO/GEO at 1900 kg avg = 78k (theoretical max 2700 = +33k headroom)
- 92 LEO low-iE at ~500 kg avg = 46k (theoretical 1100 = +55k headroom)
- 163 LEO mid+high-iE at ~450 kg avg = 73k (theoretical 950 = +82k)
- 104 unused (mostly hardest pairs) at 0 = 0 kg (theoretical ~600 = +62k)

**Total impulsive-architecture ceiling: ~370k kg.** Even with perfect
optimization, we cap below R3.

R3 average dv (3320 m/s) is *below* the impulsive Hohmann minimum
(3940 m/s) — direct evidence they use **non-impulsive physics** (WSB /
manifold-theoretic capture / Sun-Earth-Moon resonances).

## Why the audit-driven sprint didn't break the ceiling

The audit framed B1/B2/B3 as bug-fixes that would unlock new geometry.
What I learned:

- **B1 (apolune plane change)**: only matters when trajectory geometry
  *naturally* reaches the target's r_apo. Most don't — they pass at
  30-60M m from Moon while target apoapsis is at 8M m. Without
  precise Lambert targeting (which fails due to BCP perturbations),
  we can't reach the right geometry.

- **B2 (drop pv_tgt over-constraint)**: validated as design pattern
  but solve_arrival_eccentric already accepts free RAAN/argp/ea.
  Dropping pv_tgt while keeping the DC trajectory architecture
  doesn't unlock anything by itself.

- **B3 (joint NLP minimizing total dv)**: would be the right hammer
  but requires careful implementation. My attempts hit Nelder-Mead
  convergence issues.

- **B6 (frame rotation bug)**: REAL bug, but small impact (+1k kg
  this session) because most bank already used t0=0.

- **WSB**: Tier 0 confirmation showed random Hohmann perturbation can't
  enter Moon SOI precisely enough for LMO. For high-eL Moon targets,
  Tier 1A v2 found top mass 807 kg (still below bank ceiling). Proper
  manifold theory (Tier 2) is the only path with adequate dv-savings
  potential — 1-2 weeks of focused R&D.

## What the leaderboard probably uses

Educated guess based on the 620 m/s dv-saving signal:
- Multi-revolution lunar gravity assists (Belbruno-Miller style)
- BCP Sun perturbation steering (manifold-targeted)
- Probably implemented as a multi-shooting differential corrector
  rather than impulsive grid search

These methods are publication-grade work. They're not "structural bugs"
in our code — they're missing physics implementations.

## Honest recommendation

**Submit 215k Ch1 and pivot.** Compelling evidence the impulsive
architecture is saturated:
1. Every recent lever produces <5k kg
2. B6 fix (the real "structural bug" found this session) gave only +1k
3. Phase 2 with B6 fix is finding LOWER masses than the bank median
4. The R3 dv-budget is below impulsive Hohmann minimum

**Estimated time to compete for R3**: 1-2 weeks of focused R&D on
manifold-theoretic transfers + multi-shooting DC. High implementation
risk; high reward potential.

For SpOC4 competition (likely time-constrained), the better ROI is to
**ensure Ch2 and Ch3 are at their respective ceilings** and accept
mid-rank on Ch1. The mandatory two challenges (Ch1 + Ch2) score equally;
maximizing Ch2 might matter more than chasing R3 on Ch1.

## Cross-references
- C-024 — WSB design v2 (the unimplemented path)
- A-2026-05-27 — audit (B6 was hidden gem; estimate was wrong)
- C-022 — current production (BCP-apogee 3-impulse, saturated)
