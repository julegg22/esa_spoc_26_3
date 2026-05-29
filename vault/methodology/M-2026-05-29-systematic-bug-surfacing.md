---
date: 2026-05-29
tags: [methodology, debugging, lessons, scientific-process, anti-oscillation]
status: ACTIVE — applies to Ch1 now and generalizes
---
# M-2026-05-29 — Systematic bug surfacing in scientific/optimization code

## The bug pattern we found

`try_bcp_apogee_3impulse` validated trajectories via UDP fitness using a
placeholder `idD=0`. UDP fitness applies `m_d = min(m_l, (200-ΔT)·c_ld)`.
For idLs where `c_ld[idL, 0]` is tiny, valid 320-kg trajectories returned
m_d ≈ 0.9 kg and were rejected by the solver's `mass > 50` filter. The
bug was silent — no exception, no warning, just consistently low candidate
masses across thousands of pair evaluations.

**Pre-dates the anti-oscillation work by 3 days** (commit fec0f68 of
2026-05-26). But it was the anti-oscillation discipline that surfaced it,
via a per-pair physics check.

## Why it stayed hidden so long

Every check we did was *aggregate*:
- "Phase A v2 finds 6256 valid pairs averaging 500 kg" → looks reasonable
- "Hungarian gain plateaus at +6k kg" → blame bipartite constraint
- "Bank caps around 215k" → blame architecture ceiling

None of those wave-hands forced a per-pair "what does the physics predict
vs what does the solver return" comparison. We assumed solver outputs were
accurate per-pair; aggregate behavior matched our (wrong) ceiling estimate
just well enough to confirm the wrong story.

## What surfaced it

The anti-oscillation discipline (A-2026-05-29) introduced one rule:
**every lever's expected gain must be predicted from a per-pair physics
model, and validation must measure actual gain against that prediction.**

Building this prediction forced me to compute mass per (idE, idL) from
first principles (Hohmann dv0 + LOI dv from vis-viva). When my model
predicted 320 kg for (313, 156) and the solver returned 0.9 kg, the
factor-of-300 discrepancy made the bug undeniable.

## Systematic plan to surface MORE bugs (this challenge)

There are likely more bugs like this. Plan to find them:

### 1. Build the physics-ceiling table for ALL pairs
For every (idE, idL) in 400×400:
- Compute theoretical m_l from analytical formulas:
  - LEO+LMO: Hohmann + LOI
  - LEO+high-eL: Hohmann + LOI at apoapsis
  - GEO+x: scaled Hohmann
- For pairs in our results pool, compute |predicted − actual| / predicted
- Flag pairs where actual < 0.3 × predicted (= solver giving <30% of
  achievable) for investigation

### 2. Cross-validate solvers
Run multiple solvers on the same pair and compare:
- `try_bcp_apogee_3impulse` (3-impulse DC architecture)
- `solve_arrival_eccentric` direct call on perilune state (2-impulse)
- pygmo CMA-ES on the 12-dof problem
- Manual best-config from fine grid sweep

If outputs differ by >30%, one is buggy.

### 3. Test boundary cases
For each function, test deliberately edge values:
- idLs with **c_ld[idL, 0] < 0.1** (the case we missed) — verify mass returned
- idLs with eL = 0.0 vs eL = 0.65 (extreme apoapsis behavior)
- idEs with iE = 0 vs iE = π/2 (plane-change limits)
- t0 = 0 vs t0 = π (frame rotation — that was the B6 bug)

### 4. Audit every conversion / normalization
List every place in the code that scales / discounts / shifts a value:
- UDP fitness applies c_ld discount + computes from-dv mass
- state2earth, state2moon, syn_to_inertial_earth (frame conversions)
- Rocket equation (5000·exp(-dv/Isp/g0) - 500)
- T_unit_to_days conversion (×86400 / T ≈ 3.7567e5)
- Hungarian m_l_from_row (recomputes from dvs)

For each: write a single sanity test with known input/output. Flag
discrepancies.

### 5. Check the "silent reject" paths
Search for code paths that drop candidates without logging:
- `return None` after a numerical check
- `if mass < threshold: continue`
- `if not np.all(np.isfinite(...)): return None`
- `try/except` swallowing real errors

For each, count how many candidates exit via that path during a typical
run. High count + low diversity = likely bug.

## Systematic plan (general scientific/engineering methodology)

### Principle 1: First-principles prediction as test oracle

For numerical / optimization code, the "expected output" is OFTEN
computable from first principles, at least for special cases. Use that as
test oracle, NOT just "example matches".

In Ch1's case: rocket equation + Hohmann + vis-viva gives a closed-form
estimate of achievable mass per pair. Compare to solver output. >2× off
= investigate.

### Principle 2: Per-instance check before aggregate conclusions

When aggregate behavior matches your hypothesis (e.g., "bank caps at
215k = architecture ceiling"), still run per-instance checks. Wrong
hypotheses CAN produce correct aggregate behavior if the data has
enough degrees of freedom.

The minimal viable per-instance check:
- Pick 3-5 representative instances
- For each, compute the expected output from theory
- Compare to actual
- If ANY is >2x off, investigate

### Principle 3: Diversity-of-method consistency

Implement the same computation TWO independent ways. They should agree.
Disagreement = bug or undocumented assumption.

For trajectory optimization: a "computed dv via vis-viva" should match
"dv extracted from solver's saved trajectory's velocity components". If
they don't, ONE is wrong.

For competition contexts: if the leaderboard cluster shows a value YOU
can't reproduce, either (a) your implementation has a bug, or (b) they're
using a method you haven't tried. Per-instance check on the SAME pair
under both methods diagnoses which.

### Principle 4: Hostile default values

Default parameter values OFTEN hide bugs. The `idD=0` default in our
trajectory rows was a "placeholder for later assignment", but the
validation function treated it as authoritative.

Audit: for every default value in your code, ask "what if this default
were INSTEAD a maximally adversarial value? Would the function still
behave correctly?"

In our case: `idD=0` was adversarial for any idL where `c_ld[idL, 0]` is
tiny. The function silently failed. Test: pass `idD=399` (largest valid)
and compare — if results differ, there's a hidden dependency.

### Principle 5: Anti-oscillation as bug discovery

If you're oscillating between two explanations for an observed gap,
NEITHER is the truth. The gap is the sum of multiple causes. Build a
single coherent quantitative model that DOES the breakdown:
- "The 240k gap consists of: lever A (-50k), lever B (-80k), lever C
  (-60k), and ?-50k unexplained."
- Investigate the UNEXPLAINED gap first — that's where bugs hide.

In our case, after building the coherent model (A-2026-05-29), the
"unexplained" residual was actually a per-pair-validity bug, not a new
lever.

### Principle 6: Log the rejection mode

Every solver / filter that REJECTS candidates should log:
- How many rejected
- WHY (which check failed)
- Distribution of values that triggered the reject

If your solver rejects 90% of candidates but you don't know which check
caused it, you can't tell if the rejection is correct or a bug.

In our code, `try_bcp_apogee_3impulse` had several rejection paths but
none logged. Adding instrumented logging would have surfaced the
"f >= 0 → return None" path catching many should-be-valid pairs.

## Application to this challenge — concrete next steps

1. **TODAY**: write the per-pair physics-ceiling table for the bank's
   currently-banked 302 pairs. Find any where actual << prediction
   (factor of 2+ off). Investigate each.
2. **TODAY**: instrument try_bcp_apogee_3impulse with a per-call
   "reject reason" counter. Run on 100 pairs, see the rejection
   distribution. Look for "f >= 0" rejects that have m_l > 50 (the bug
   we just fixed — verify it doesn't recur).
3. **THIS WEEK**: cross-validate the 3-impulse solver against an
   independent 2-impulse solver (our `solve_arrival_eccentric` direct
   call) on 50 representative pairs. Discrepancies = potential bugs.

## Application to scientific methodology generally

Submit as a methodology contribution / blog post:
- The pattern "oscillation between explanations → build coherent model
  → per-instance check → bug surfaces" is generalizable
- Key insight: aggregate behavior CAN match wrong hypotheses, per-instance
  cannot
- Implication: scientific code reviews should include first-principles
  test oracles, not just example-based tests

## Cross-references
- A-2026-05-29 — coherent physics model (the discipline that surfaced
  the bug)
- The (313, 156) debug session — the per-pair check that revealed it
- Commit fec0f68 — when the bug was introduced (silently)
