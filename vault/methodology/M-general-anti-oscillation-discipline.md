---
date: 2026-05-29
tags: [methodology, scientific-process, decision-making, investigation, general]
scope: GENERAL — applies across projects, NOT specific to ESA SpOC
status: distilled from empirical experience (Ch1 WSB-vs-B1 oscillation 2026-05-27 → 2026-05-29)
---
# The anti-oscillation discipline

A working methodology for investigations / debugging / scientific reasoning
when you find yourself **flip-flopping between two (or more) competing
explanations** for an observed phenomenon, without accumulating new
evidence.

Distilled from a specific incident (see `M-2026-05-29-systematic-bug-surfacing.md`)
but stated here in project-agnostic form so it generalizes.

## The symptom

You observe a gap between expected and actual outcomes. You propose
explanation A. You investigate, A seems partially right but not enough.
You propose explanation B. You investigate, B also seems partially right.
You return to A with new framing. Then back to B. And again.

Hours or days pass. Each oscillation cycle FEELS productive (you're
"learning"), but in fact you're re-arguing the same incomplete picture.
You're not converging on truth; you're shuffling between two corners of
the answer space.

**Recognize the pattern as a signal**: it means you've stopped accumulating
new evidence and started re-interpreting the existing evidence.

## The trap

Each oscillation generates a story that fits some of the data. Both
stories are partially right. The instinct is to keep refining whichever
story you're currently committed to. But:

- Neither story alone fully explains the gap
- The gap is **multi-causal**
- You can't decide between A and B because both are present (with C, D,
  E that you haven't named)
- Continuing to argue A vs B is a dead end

## The discipline

When you notice the pattern, STOP and execute this procedure:

### Step 1: Build a coherent quantitative decomposition

Write down the gap as a sum of named causes:
> The gap of −X consists of:
> - cause A (−x₁)
> - cause B (−x₂)
> - cause C (−x₃)
> - UNEXPLAINED RESIDUAL (−x₄)

The CRITICAL move: budget every named cause with a quantitative estimate.
Not "WSB matters", but "WSB closes ~60k of the 240k gap, IF applied to
the 200 high-eL pairs and IF saves ~300 m/s LOI per pair".

Show your work. If you can't estimate the magnitude of a cause, you
don't yet understand it well enough.

### Step 2: Reveal the unexplained residual

After budgeting all the named causes, what's left over? That residual is
where the truth most likely hides. It indicates:
- A cause you haven't named (= a missing lever or hypothesis)
- A miscalibration of one of the named causes (= over- or
  underestimating its contribution)
- A bug or wrong assumption masquerading as something else

**Investigate the residual first**, before re-investigating the named
causes you're already arguing about.

### Step 3: Predict per-cause measurements

For each named cause, predict an empirical signature:
- "If WSB is the cause, then specific pair X should benefit by ~Y kg when
  we apply manifold targeting"
- "If solver bug is the cause, then per-instance check on pair Z should
  show actual << theoretical"

These predictions must be SPECIFIC enough to falsify. Vague predictions
("WSB will help") don't break the oscillation.

### Step 4: Run the predictions, measure, decide

For each cause:
- Run the predicted experiment
- Measure
- Compare to prediction
- If actual ≈ prediction within an order of magnitude: cause confirmed
- If actual << prediction: cause is partially right (some piece is missing)
- If actual = 0 or far below prediction: cause is wrong OR an unaccounted
  bug is in the way

### Step 5: Update the decomposition

After measurements, update the gap decomposition. Some causes may shrink,
others grow, the residual may shift. Pick the next investigation target
based on largest remaining gap component.

### Step 6: Do NOT add new "structural insights" without checking the table

A common failure mode after Step 1-2: you find a partial explanation,
get excited, and propose ANOTHER structural insight that should explain
the gap. This is the oscillation re-asserting itself.

Rule: every proposed new lever must specify which part of the
quantitative decomposition it addresses. If you can't fit it into the
table, you're still arguing the wrong frame.

## Why this works

The oscillation persists because **each story has confirming evidence**.
You can't break out by arguing harder for one story — you need to model
both stories together AND identify what's NOT covered by either.

The quantitative decomposition does three things at once:
1. Forces you to commit to magnitudes (not vibes)
2. Reveals what the named stories DON'T cover (the residual)
3. Makes per-story predictions specific enough to falsify

Once the decomposition exists, oscillation becomes impossible —
arguments about A vs B reduce to disputes about magnitudes within the
table, which are settled by measurement.

## When to use it

The discipline applies to any investigation that has:
- An observable gap between expected and actual outcomes
- Two or more competing explanations, each partially supported
- Aggregate-level evidence that ambiguously supports both
- Multiple cycles of "Story A → investigate → Story B → investigate → ..."

Common settings:
- Debugging numerical / scientific code
- Optimization solver investigation ("why doesn't this method work?")
- Business / strategic analyses ("why are conversions low?")
- Scientific hypothesis selection between two paradigms

## When it's NOT the right tool

This discipline assumes the gap is decomposable into named magnitudes.
If you're investigating something where:
- The observable isn't a single scalar
- The competing explanations operate on different "currencies"
- The data is too thin to support quantitative estimates

...then the discipline degrades to "build a model" without the quantitative
grounding. Still useful but less sharp.

## The trigger case (one example among many)

In a trajectory optimization investigation (ESA SpOC 2026 Ch1), I
oscillated for 3 days between:
- "WSB / manifold-theoretic transfers are the lever to R3"
- "Proper apolune-plane-change (B1) implementation alone reaches R3"

Each story had partial confirming evidence. Each implementation attempt
gave marginal gains that I attributed to "needing the OTHER lever". The
oscillation continued until I noticed it.

Applying the discipline:
- Step 1: built the quantitative decomposition. Impulsive ceiling ≈ 371k.
  +WSB ≈ +60k. Sum = ~431k. R3 = 453k. **Unexplained residual = ~22k.**
- Step 2: 22k residual stood out as "neither story explains this"
- Step 3-4: per-instance physics check (predict 320 kg for pair (313,
  156) from theory; solver returns 0.9 kg). Per-instance check surfaced
  a SILENT BUG in the solver — the actual cause of part of the gap.

The bug had silently corrupted every solver run for 3+ days. Without
the discipline, I would have continued the oscillation indefinitely.

## Where this document lives

Project-local copy: `vault/methodology/M-general-anti-oscillation-discipline.md`

Companion documents:
- `vault/methodology/M-general-bug-surfacing-for-scientific-code.md` — the
  bug-surfacing principles (includes anti-oscillation as Principle 5)
- `vault/methodology/M-2026-05-29-systematic-bug-surfacing.md` — the
  Ch1-specific trigger case

If extracting for blog post / external sharing: this file is the
canonical text. The trigger case is illustrative but not required for the
discipline to stand.
