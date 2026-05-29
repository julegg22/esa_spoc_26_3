---
date: 2026-05-29
tags: [methodology, scientific-process, bug-detection, debugging, general]
scope: GENERAL — applies across projects, NOT specific to ESA SpOC
status: distilled from empirical experience (Ch1 idD=0 bug 2026-05-29)
---
# Bug-surfacing principles for scientific / optimization code

A set of working principles for detecting silent bugs in code where:
- Inputs and outputs are numeric
- "Correctness" can't be checked by example-matching alone
- Aggregate behavior is the usual diagnostic
- Bugs often hide in normalization, default values, sign conventions, and
  rejection paths

These principles are distilled from a specific incident (see project's
M-2026-05-29 for the trigger case) but stated here in project-agnostic form
so they generalize.

## The trap: aggregate plausibility

Optimization / scientific code is often validated by aggregate metrics
("our solver beats baseline by 10%", "results cluster near theoretical
ceiling"). This is necessary but **not sufficient**.

**Wrong hypotheses CAN produce correct aggregate behavior** if the data
has enough degrees of freedom. The model "system is at capacity ceiling"
will fit reams of aggregate evidence even when the truth is "solver
throws away 30% of valid candidates due to a silent bug" — because both
explanations leave the same observable footprint.

Diagnostic implication: aggregate match doesn't confirm; it just fails to
falsify. To rule OUT wrong hypotheses, you need per-instance checks.

## Principle 1: First-principles prediction as test oracle

For numerical / optimization code, the "expected output" is OFTEN
computable from first principles, at least for special cases. Use that
analytical answer as the test oracle, **not just "example matches"**.

Concrete form: for any solver output, compute a closed-form lower or
upper bound. The solver's output should fall within (and ideally near)
that bound.

When solver output is >2× off from the analytical bound: a bug exists.
Either in the solver, or in your understanding of what it should compute.

## Principle 2: Per-instance check before aggregate conclusions

Before drawing aggregate conclusions (e.g., "solver is saturated", "this
lever doesn't work"), run a per-instance check on 3–5 representative
inputs. For each:
1. Predict the expected output analytically
2. Run the code
3. Compare

If ANY individual case is >2× off, investigate before believing the
aggregate story.

This catches bugs that aggregate stats can't, because individual cases
have less room for the data to "cover up" a wrong hypothesis.

## Principle 3: Diversity-of-method consistency

Implement the same computation TWO independent ways. They should agree
modulo numerical noise.

Disagreement means:
- One implementation has a bug, OR
- An undocumented assumption differs between them, OR
- A genuine ambiguity (sign convention, frame, units) needs resolution

In all three cases, you've surfaced something that needs attention.

For optimization: a known-feasible analytical baseline (Hohmann + LOI in
trajectory optimization; LP relaxation in combinatorial optimization;
2-opt baseline in TSP) compared to the solver's output. Disagreement of
>30% in either direction is a signal.

## Principle 4: Hostile-default-values audit

Default parameter values OFTEN hide bugs. The default is "the value
you'll see most often", but it's also "the value adversaries inadvertently
trigger when they don't know better".

Audit: for every default value in your code, ask:
> *What if this default were INSTEAD a maximally adversarial value? Would
> the function still behave correctly?*

If the function silently misbehaves on adversarial default values, document
the constraint OR change the default OR add a defensive check.

The trigger case for this principle: a "placeholder" `idD=0` was used in
trajectory rows for later assignment. The validation function treated it
as authoritative. For input data where `c_ld[idL, 0]` was tiny, the
validation silently rejected valid 320-kg trajectories with measured
discounted mass of 0.9 kg.

## Principle 5: Anti-oscillation as a bug detector

When you find yourself oscillating between two explanations for an
observed gap, **NEITHER is the full truth**. The gap is multi-causal.

Anti-oscillation procedure:
1. Build a single coherent quantitative decomposition. Example:
   "The gap of −X consists of: cause A (−x₁) + cause B (−x₂) + cause C
   (−x₃) + UNEXPLAINED (−x₄)."
2. Investigate the UNEXPLAINED residual first. That's where bugs hide
   most often.
3. Each lever's expected gain must be predicted by the model. After
   implementation, measure actual vs predicted. >30% off = bug.

The oscillation is a SIGNAL: it means you've stopped accumulating new
evidence and are instead re-arguing the same incomplete picture. Force
yourself to decompose quantitatively to break out.

## Principle 6: Log every silent reject path

Every code path that REJECTS a candidate or DROPS data without logging
is a potential bug hiding place:
- `return None` after a numerical check
- `if mass < threshold: continue`
- `if not np.all(np.isfinite(...)): return None`
- `try/except` swallowing errors
- Filters in pipeline stages

Instrument them. For each rejection path, log:
- How many rejections occurred (in a given run)
- The values that triggered the rejection (histogram or sample)
- WHICH rejection check fired (give them names)

If a solver rejects 90% of candidates but you don't know which check
caused it, you can't distinguish "the check is correct" from "the check
is too aggressive due to a bug".

## Principle 7: The cross-conversion ratchet

Every place in the code that scales / discounts / shifts / converts a
value is a potential silent corruption point. Audit each.

Common offenders:
- Unit conversions (km vs m, days vs seconds, deg vs rad)
- Sign conventions (prograde vs retrograde, source minus target vs
  target minus source)
- Frame conversions (synodic vs inertial, body-fixed vs orbit-plane)
- Normalization (dimensional vs non-dimensional)
- Aggregations (sum vs mean vs weighted)

For each, write a single sanity test with known input → known output.
Run them periodically (not just once).

## Composition: how the principles interact

These principles compose into a workflow:

1. **At the start of a project**: write down expected analytical bounds
   per output type (Principle 1). Inventory default parameters and their
   adversarial values (Principle 4). Identify the conversion chain
   (Principle 7).

2. **During development**: after each implementation milestone, do
   per-instance checks on 3-5 cases (Principle 2). If something is off,
   diagnose via diversity-of-method (Principle 3).

3. **When debugging unexpected aggregate behavior**: don't keep
   oscillating between explanations. Build the quantitative decomposition
   (Principle 5). The unexplained residual is your investigation target.

4. **When a solver / pipeline rejects more than 30% of candidates**:
   instrument the rejection paths (Principle 6). Surface what's being
   thrown away.

## Why this matters beyond one project

Most scientific code reviews emphasize:
- Code style / readability
- Test coverage by line / branch
- Performance benchmarks
- Example-based unit tests

These are necessary but they SYSTEMATICALLY miss the class of bugs we
faced: silent rejections that produce wrong aggregate behavior matching a
wrong (but plausible) hypothesis. Those bugs survive code review,
survive unit tests, survive performance benchmarks, and survive aggregate
metric checks. They only die when caught by per-instance physics-vs-actual
comparison.

The contribution of this document: **scientific code reviews should
explicitly require first-principles test oracles, per-instance checks,
hostile-default audits, and silent-reject instrumentation as part of the
standard methodology** — not as optional bonus practices.

## Where this document lives

Project-local copy: `vault/methodology/M-general-bug-surfacing-for-scientific-code.md`

The trigger case (Ch1 idD=0 silent rejection bug, 2026-05-29) is documented
project-specifically in:
- `vault/methodology/M-2026-05-29-systematic-bug-surfacing.md`
- Memory: `scientific-bug-surfacing-method.md`

If extracting for blog post / external sharing: this file (the general
form) is the canonical text. The trigger case provides motivation but
isn't required for the principles to stand.
