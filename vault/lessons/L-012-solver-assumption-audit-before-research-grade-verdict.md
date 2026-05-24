---
id: L-012
type: lesson
status: confirmed
tags: [methodology, debugging, ch1, trajectory, gotcha, fundamental]
kind: methodology
scope: solver-design + benchmark-evaluation
severity: critical
confidence: high
created: 2026-05-24
source: "5-day misdiagnosis of Ch1 trajectory as 'research-grade required' when actual bug was solve_arrival_dv rejecting eccentric Moon orbits"
related:
  - "[[O-012-ch1-traj-under-determined-residual]]"
  - "[[O-002-leaderboard-2026-05-18]]"
  - "[[ch1-eccentric-orbit-fix]] (memory)"
effort_person_hours: 5.0
---

# L-012 — Run a solver-assumption audit before declaring "research-grade needed"

## The failure

For 5 days (2026-05-19 → 2026-05-24) we treated Ch1 trajectory's
14.82 kg banked mass as "structural" — the leaderboard R3 was 452,820
kg, a 30,000× gap. We progressively concluded:

1. The solver finds positive mass for only ~0.25% of pairs → "thin
   feasibility ridge."
2. Lambert+DC fails for inclined pairs → "BCP perturbation too large."
3. Diverse-pair test gives 0/20 → "fundamentally hard problem."
4. Even 5° inclination breaks the solver → "research-grade physics
   required (patched-conic SOI, WSB, 3-impulse Lambert)."

Each step was a reasonable inference from the symptoms, but the
underlying assumption — that **our solver was correct** — was never
audited.

## The bug

A single line in `ch1_trajectory_solve.solve_arrival_dv:72`:

```python
if abs(r - a_m) >= L * tol:  # 384m
    return None
```

This filter only allows arrival radius within 384m of `aL`. Correct
for circular Moon orbits (eL ≈ 0); wrong for eccentric. The dataset
contains 150 Moon orbits with eL > 0.3 (max eL = 0.65), whose valid
arrival radii span thousands of km. The solver was rejecting all of
them, generating the "infeasibility" symptoms.

Fix: target the actual `(aL, eL, iL)` orbit family instead of
circularizing at arrival radius.

Impact on test pairs:
- (0,0): 14.82 → **819 kg** (55×)
- (267,181) GEO+eL=0.65: FAIL → **2037 kg**
- (266,234) GEO+eL=0.64: FAIL → **1211 kg**
- (27,116) iE=0.11, iL=0.02: FAIL → 332 kg

## Why we missed it

Three compounding errors:

1. **Initial bank (14.82 kg, idL=0, eL≈1e-7) was a degenerate case**:
   eL≈0 means the bug doesn't manifest. We then polished this pair
   to 794 kg and considered the solver "validated."

2. **Tested only on (0,0) and similar low-eL pairs**: The data
   contained pairs where the bug WAS active (eL > 0.01) but we
   didn't sample them randomly. Our "validation" was biased toward
   the case where the solver happened to work.

3. **30,000× ratio was treated as evidence of difficulty**: Should
   have been a red flag that solver was broken. Theoretical Hungarian
   bound (445k kg) computed in 2 minutes once we did it.

## The lesson — Solver-Assumption Audit Protocol

Before any of:
- declaring a benchmark "research-grade"
- pursuing exotic algorithmic approaches (manifold methods, 3-body
  dynamics, WSB, etc.)
- spending >1 day on a single approach

Run this 3-step audit:

### Step 1: Theoretical bound check
Compute the best-case theoretical bound for the metric. Compare to
current achievement.

- Ratio < 2×: you're polishing, current solver is correct.
- Ratio 2-10×: room to improve solver; not necessarily broken.
- **Ratio > 100×: solver almost certainly has a bug.** Don't pursue
  algorithmic improvements until the bug is found.

### Step 2: Assumption-vs-data audit
List every implicit assumption in your solver. For each:
- What does it assume about the input?
- What does the data distribution actually contain?
- Does the assumption hold across the entire distribution?

Examples that should have caught our bug:
- "solve_arrival_dv assumes circular target orbit" + "data has eL up
  to 0.65" → mismatch.
- "We target a_m radius" + "valid radii span [a(1-e), a(1+e)]" →
  mismatch for e > 0.001.

### Step 3: Diversity test
Test the solver on ≥10 inputs sampled across the data's diversity.
NOT the easiest cases. Specifically include:
- Each extreme of every parameter (min/max a, e, i)
- Pairs that stress different assumptions
- Random samples (not curated)

If any "easy by physics" input fails, the solver has a bug.

## How to apply

Add this audit as a checklist item before any "this needs better
methods" verdict. The audit takes ~30 minutes. Skipping it cost us
5 days. The ratio is ~250:1.

For SpOC4 / similar benchmarks where ground truth is unknown but a
strong baseline (e.g. leaderboard) exists:
- The leaderboard top-N is approximately the theoretical bound for
  practical purposes.
- Gap > 10× → suspect solver; investigate before algorithmic changes.
