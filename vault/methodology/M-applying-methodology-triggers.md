---
date: 2026-05-29
tags: [methodology, meta, triggers, application, process]
status: ACTIVE — the meta-doc that ensures other methodology gets applied
---
# How to make methodology actually fire

Documenting methodology is necessary but **not sufficient**. The
methodology docs (`M-general-bug-surfacing-for-scientific-code.md`,
`M-general-anti-oscillation-discipline.md`) won't help unless they
actually get applied at the right moment. This document is the bridge.

## Failure modes of unapplied methodology

1. **Discovery failure** — future sessions don't see the docs
2. **Recall failure** — docs are seen but not remembered at the right moment
3. **Application failure** — remembered but procedure not actually followed
4. **Context failure** — followed but in the wrong context

Each failure mode needs its own intervention.

## Intervention table

| Failure mode | Intervention | Where it lives |
|---|---|---|
| Discovery | Auto-loaded memory pointers + CLAUDE.md reference | `MEMORY.md`, `CLAUDE.md` |
| Recall | Trigger-based reminders during work (not docs to look up) | This document's trigger table |
| Application | Concrete templates that EMBED the procedure | Analysis doc templates |
| Context | Decision criteria + "when NOT to apply" in each doc | Per-doc footer |

## The trigger table — what fires when

These are the moments when methodology MUST be applied. Each row says:
when X happens, do Y.

| Trigger | Procedure to fire | Doc |
|---|---|---|
| Proposing a "new structural insight" / "real lever" / "what we missed" | Stop. Check: is there a quantitative gap decomposition? Does the proposed lever fit a named cause OR explain the residual? If neither, you're oscillating. | Anti-oscillation discipline |
| Investigation has cycled ≥3 times between two explanations without new evidence | Force quantitative gap decomposition. Investigate UNEXPLAINED RESIDUAL first. | Anti-oscillation discipline |
| Aggregate metric matches expectation but exact mechanism unclear | Per-instance check on 3-5 representative cases. Compare predicted vs actual. If any >2x off, investigate. | Bug-surfacing P2 |
| Solver / pipeline rejects > 30% of candidates | Instrument silent reject paths. Log which check fires + value distributions. | Bug-surfacing P6 |
| Architecture / solver seems "saturated" or "at ceiling" | Per-instance check BEFORE concluding. Aggregate ceilings can be wrong while every per-instance prediction looks right. | Bug-surfacing P2 |
| Adding a default value to chromosome / config / params | Hostile-default audit: what if this default were ADVERSARIAL? Does the function still work? | Bug-surfacing P4 |
| New project / new challenge starts | Run the bootstrap checklist (below) | This doc |
| Same computation done two ways | Diversity-of-method consistency check. They MUST agree. | Bug-surfacing P3 |
| Conclusions across ≥3 experiments converge on a "wall / plateau / moonshot" | AUDIT THE METRIC. Re-state the wall in the ROOT objective (points/rank), not a proxy (completeness, strand-count, ΔV-floor, d/leg). A correct result in the wrong metric steers the whole program. | Root-objective & proxy-skew |
| Writing any "wall / exhausted / moonshot" conclusion | Premise-tag it: name the proxy↔objective assumption it rests on, IN the conclusion, so a later premise correction has a clean propagation target. | Root-objective & proxy-skew |
| Any "stuck / walled / plateau / exhausted" verdict forms, OR the instinct is "more compute / another solver variant" | Run the ABSTRACTION-LADDER SWEEP top-down (L1 objective → L2 model → L3 structure → L4 encoding → L5 evaluator → L6 solver → L7 operators → L8 params). The wall is the HIGHEST rung a cheap probe flags as mismatch; fix there. Reaching for L7/L8 without a completed sweep is the tell. | Abstraction-ladder audit |
| Naming any "exhausted/walled/closed" verdict | R1: it is INADMISSIBLE unless it states "exhausted at level L, levels above ruled out by measurement M." Exhausted within a level ≠ exhausted of the problem. | Abstraction-ladder audit |
| A specific tool/solver walls (can't express a constraint, strands, times out) and you're about to abandon the LEVER | R2: a tool wall is an L6 fact, not lever death. Try the minimal level-changing swap (a solver that expresses the constraint). R3: sibling-transfer scan — does a structurally-similar sibling instance's machinery realize this lever? | Abstraction-ladder audit |
| A relaxed/unconstrained run achieves an objective far PAST the target | R4: the structure CONTAINS the solution; the gap is constraint-handling (encoding/solver), not search. Next step = a tool that enforces the constraint natively. Never file "capped." | Abstraction-ladder audit |

## Bootstrap checklist for a NEW challenge / project

When starting work on a new challenge or domain:

1. **Read** the active methodology docs (`vault/methodology/M-general-*.md`)
2. **Identify** the analogs in the new problem:
   - What's the analogue of the "gap" (R3 target − bank)?
   - What's the analogue of "per-instance" (per-pair in our case)?
   - What's the analogue of "first-principles theoretical prediction"
     (rocket equation in our case)?
   - What's the analogue of "silent reject paths" (filter conditions)?
   - What are the "default values" that could be adversarial?
3. **Build** the initial quantitative decomposition: what's the structure
   of the gap if the current approach plateaus? List 3-5 named candidate
   causes with rough magnitudes.
4. **Instrument** silent reject paths in your solver from day 1, not after
   you suspect a bug.
5. **Schedule** per-instance checks at every major milestone (e.g., when
   bank crosses a round number, when a lever lands), not just when you're
   stuck.

## Process pattern: the analysis doc template

Every "we hit a plateau, here's the analysis" doc should follow:

```
## What we observe (the gap)
- Current state: X
- Target / expected: Y
- Gap: -Z

## Quantitative decomposition
- Cause A: -a (estimate from <reasoning>)
- Cause B: -b
- Cause C: -c
- UNEXPLAINED: -(Z - a - b - c)

## Per-instance check (3-5 cases)
| Instance | Predicted | Actual | Ratio |
|---|---|---|---|
| ... | ... | ... | ... |

## Investigation priority
1. Largest cause in decomposition
2. (NEW RULE) Unexplained residual if >20% of gap
3. Any per-instance with actual << predicted

## Next lever
Must specify which decomposition row it addresses.
```

If you find yourself writing an analysis doc WITHOUT a quantitative
decomposition, you're skipping the discipline. Stop and add it.

## Process pattern: the "structural insight" guardrail

Before committing to a new structural insight / lever / hypothesis, write
ONE sentence that:
1. Names which decomposition row it explains
2. Predicts the empirical signature you'll see when you test it
3. Specifies the magnitude (>5k kg? <1k kg?)

If you can't write all three, you're in oscillation mode, not analysis
mode. Build the decomposition first.

## How CLAUDE.md should reference this

CLAUDE.md (or equivalent project-loaded context) should include:

```
## Investigation discipline
This project uses an anti-oscillation discipline. Before proposing new
"structural insights" or "real levers" to close an observed gap,
consult `vault/methodology/M-applying-methodology-triggers.md` and the
two general methodology docs it references. The trigger conditions
listed there should fire automatically — they're not optional.
```

This makes the discipline a default expectation, not a special practice.

## How memory entries should encode triggers

Memory entries with strong, action-oriented descriptions surface at
session start. They should:

- Be SHORT (3-5 lines summarizing the trigger and action)
- Name the trigger condition explicitly ("when investigation oscillates ≥3
  cycles" not "for difficult problems")
- Point to the canonical doc for procedure
- Use keywords that align with what you'd say when in the situation
  ("structural insight", "lever", "saturated", "ceiling", "plateau")

Example (already deployed):
- `anti-oscillation-discipline.md` description includes "flip-flop"
- `scientific-bug-surfacing-method.md` description includes "silent bug"

Both should auto-surface when these words appear in the user's prompts.

## How to evaluate whether methodology is being applied

At session end (or for retrospective analysis), check:

- [ ] Was a quantitative decomposition built when stuck?
- [ ] Was per-instance check done before aggregate conclusions?
- [ ] Were silent rejects instrumented if >30% rejection rate?
- [ ] Were hostile-default values considered?
- [ ] Did any "new lever" proposals include the 3-sentence guardrail?

If most boxes are unchecked, the methodology isn't being applied.
Diagnose: was discovery, recall, application, or context the failure?
Improve the corresponding intervention.

## What this document explicitly does NOT do

This is not "best practices" advice. It's specifically about ensuring
the OTHER methodology docs (anti-oscillation, bug-surfacing) get applied
when they're relevant. The actual principles are in those docs.

Treat this as the project's process spec for those principles.

## Where this document lives

Project-local: `vault/methodology/M-applying-methodology-triggers.md`

Companion docs:
- `M-general-anti-oscillation-discipline.md` — the discipline itself
- `M-general-bug-surfacing-for-scientific-code.md` — the bug-surfacing principles
- `M-2026-05-29-systematic-bug-surfacing.md` — Ch1 trigger case

If extracting for external sharing: this document is project-process-spec,
relevant only as a template. The general docs are the substance.
