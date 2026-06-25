---
date: 2026-06-25
tags: [methodology, meta, exploration, never-stop, anti-giving-up, process]
status: ACTIVE — encodes the "exhaustion is a transition, not a stop" rule (CLAUDE.md §5b)
related: ["[[M-general-deep-single-prompt-audit]]", "[[M-general-architecture-change-on-large-gaps]]", "[[M-general-basin-overarching-search]]", "[[M-general-anti-oscillation-discipline]]"]
---
# Exhaustion is a transition, not a stop

## The failure this prevents

When a method *family* looks exhausted on the top goal, the tempting move is to **stop and redirect** —
hand back to the user, or keep cores busy on a *lower-value* lever — while telling yourself you're "not
idle." That is giving up in disguise. **Busy ≠ exploring the best lever.** The "no idle cores" rule does not
catch this: you can be 100% utilized and still have abandoned the highest-EV path.

The subtle variant (the one that named this rule): you **correctly name** the forward path, then use its
*difficulty* as the reason to stop — "that's a genuine research problem / multi-day / the competitor's
sophisticated method / beyond a quick fix." **The difficulty is the specification of what to build, not a
license to defer it.**

## The rule (mandatory sequence on "exhausted")

1. **Name** the next most plausible exploration step: a different method family, a relaxed assumption, a
   faster/different primitive, a sub-problem, or the bottleneck you just isolated.
2. **Take it.** Build and run it. "Heavy / research-grade / multi-day" → scope it and start; report progress,
   not a permission request. Long builds are normal; decompose and begin.
3. **If genuinely no next step exists,** run a deep audit ([[M-general-deep-single-prompt-audit]]) that
   questions the *results and assumptions* to **derive** one. The audit is itself the next step.

## Self-check trigger phrases

If you write any of these *as a reason to stop / defer / pivot*, that is the trigger to run the sequence
above instead — not a conclusion:
> "exhausted" · "plateau / ceiling / wall" · "genuine/real <X> problem" · "research-heavy" ·
> "multi-day / not a quick build" · "beyond a quick fix" · "the competitor's sophisticated method" ·
> "fundamental limit" · "I'll build it if you want".

## The only legitimate stops

- The **submission gate** (user-gated) and destructive/outward-facing actions.
- A **deep audit that explicitly, with evidence, concludes the admissible optimum is reached** (e.g., a proven
  bound met, or every assumption falsified). "It's hard" is never a legitimate stop.

## Why this keeps working (track record)

Every prior "exhausted" verdict in this project fell to the next step or a deep audit:
- Ch1 trajectory "per-pair CLOSED" → departure/arrival **asymmetry bug** (8 solver methods had been defeated
  by one downstream feasibility bug).
- Ch2-small "7 families converged → ceiling" → **0.002 d evaluator-resolution** artifact.
- Ch2-large "566 wall / algorithmic gap" → **8-sample-probe graph under-count** (+6200 edges, broke to 575),
  then the crux isolated to a **fast drift-free TD evaluator** (the named, unbuilt next step).

## One-line takeaway

**"This family is exhausted" is an instruction to name and take the next step — or to audit until one
appears — never a reason to stop or to substitute lower-value busywork.**
