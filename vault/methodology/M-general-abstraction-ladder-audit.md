---
title: "The Abstraction-Ladder Audit — sweep levels top-down when stuck"
tags: [methodology, general, audit, abstraction, encoding, when-stuck]
created: 2026-07-01
type: methodology
status: ACTIVE — the spine that sequences the other audit lessons into a forced checklist
---

# The Abstraction-Ladder Audit

When an optimization path looks exhausted, the wall can sit at any of
several **levels of abstraction** — not just "search harder." A mismatch at
a high level makes *all* effort below it futile. This node defines the
levels, and a **top-down sweep** that finds the highest mismatched one.

## Motivating failure — why our audits missed "encoding" (2026-07-01)

The deep audit on **Ch2-small** correctly named the missing lever — *joint
sequence+epoch global search*. We built it as a time-expanded GTSP solved by
**GLKH**; GLKH cannot express the hard "≤5 exception legs" constraint, so it
either abused exceptions (75.2 d tour, infeasible) or stranded; we filed
**"GTSP lever closed for small."** But the same campaign's **medium** engine
— an exact continuous-time labeling DP + LNS that enforces ≤5 *natively* — is
*exactly* the tool that realizes small's lever. The encoding/solver mismatch
was discoverable at the time. Our audit didn't surface it. **Four compounding
causes:**

1. **Flat assumption list.** The audit listed "representation/encoding" among
   many items, but a flat list gets *uneven* coverage: you enumerate a few
   (usually low-level) assumptions, feel thorough, and never pressure-test the
   encoding or structure levels. Nothing forced a rung-by-rung pass.
2. **Lever/implementation conflation.** "Joint search walled" was really
   "GLKH-GTSP walled." We didn't separate the **abstraction** (what to search)
   from the **tool** (how). A tool wall got mis-attributed to the whole lever.
3. **Per-instance silos.** Audits were scoped to one instance. The tool that
   solves small lived in the *medium* subtree. No step asked "does a sibling
   instance's machinery apply here?"
4. **Cost-asymmetry bias.** Reconsidering high levels (re-model, re-encode) is
   expensive; low levels (tune params, add compute/restarts, swap to another
   solver *variant*) are cheap. Under any pressure we default to the cheap low
   rungs — the opposite of where large gaps live.

**Root cause:** we had the individual lessons — evaluator fidelity
([[foundation-then-search-methodology]]), structure
([[architecture-change-on-large-gaps]]), basin
([[basin-overarching-search]]), proxy-skew
([[root-objective-and-proxy-skew]]) — as *separate* nodes, but no unifying,
ordered **checklist** forcing us to test each level *every* time we're stuck.
The toolbox existed; the systematic sweep did not.

## The ladder — 8 levels in 3 tiers (audit TOP-DOWN)

A candidate solution and the search that produces it rest on a stack of
choices. A wall can sit on any rung; the higher the rung, the more futile all
effort below it.

**TIER A — Are we solving the right problem, and do we see its structure?**
- **L1 Objective** — optimizing the true root goal, or a proxy?
  ([[root-objective-and-proxy-skew]])
- **L2 Model / Formulation** — does our model faithfully capture the real
  problem's constraints / physics / feasibility? (idD=0 bug; eccentric-
  departure bug; official-UDP feasibility)
- **L3 Structure** — have we identified the native exploitable structure
  (narrow windows, clusters, components) and are we decomposing along it, or
  treating a decomposable problem as monolithic? (HRI: narrow basins / clusters)

**TIER B — Can we even represent and score the optimum?**
- **L4 Encoding / Representation** — can our encoding *represent* a solution
  as good as the target, at the structure's scale? (uniform time grid vs
  window-indexed vs continuous clock; 0.002 d bands vs 0.1 d grid; the
  epoch-shift trap)
- **L5 Evaluator / Oracle** — is fitness/feasibility faithful and at the right
  resolution? Does it tell the truth? (coarse evaluators blind to narrow
  windows; the 8-probe cheap-graph undercount; [[foundation-then-search-methodology]])

**TIER C — Can our search find it?**
- **L6 Solver / Algorithm family** — right paradigm for this structure? Can it
  express **all** constraints natively? (GLKH can't express ≤5-exception; the
  exact-DP + LNS can)
- **L7 Operators / Neighborhood / Acceptance** — can the moves reach the
  optimum's basin? ([[basin-overarching-search]]: destroy+rebuild vs local moves)
- **L8 Parameters / Resolution / Compute** — tuning, grid resolution,
  iterations, restarts, budget. (Usually **not** where big gaps live — but
  where we habitually reach first.)

## The procedure

Fires when any "stuck / walled / plateau / ceiling / exhausted" verdict forms,
**or** the instinct is "more compute / another solver variant."

1. **Sweep the ladder TOP-DOWN.** For each level: state the current choice;
   name what a mismatch here would *look like*; run the **cheapest probe** that
   would reveal a mismatch (often arithmetic on the banked artifact or a tiny
   experiment); mark the level **ruled-out (by measurement)** or **SUSPECT**.
2. **The wall is at the HIGHEST level whose probe returns "mismatch."** Fix
   there. Effort below a mismatched rung is wasted.
3. **Complete the pass** — don't stop at the first convenient (low) mismatch;
   find the *highest* one.

## Five rules that operationalize it

- **R1 — Name the level of every wall.** No "exhausted / walled / closed"
  verdict is admissible unless it states *"exhausted at level L, with levels
  1..L-1 ruled out by measurement M."* Exhausted *within* a level ≠ exhausted
  *of* the problem.
- **R2 — A tool wall is an L6 fact, not lever death.** When a specific
  solver/tool fails, that is evidence about *that rung only*. Before abandoning
  the lever (L3/L4), try the **minimal level-changing swap** (e.g. a different
  solver that expresses the constraint). Separate ABSTRACTION from
  IMPLEMENTATION in writing.
- **R3 — Sibling-transfer scan.** If the problem belongs to a family
  (sizes/variants), ask explicitly: does a tool or insight from a *sibling*
  instance realize this lever? Search siblings' subtrees, not just this one's.
- **R4 — Relaxation-beats-target ⇒ constraint-handling gap.** If relaxing a
  constraint yields an objective far *past* the target (small's 75.2 d with 25
  exceptions vs target 100.4 with ≤5), the structure **contains** the solution;
  the gap is **constraint-handling** (L4/L6), not search. Next step = a tool
  that enforces the constraint natively. Never file this as "capped."
- **R5 — Cost-asymmetry counter-bias.** High rungs are expensive to
  reconsider, low rungs cheap — so you are biased to grind L7/L8. The top-down
  order exists to counter exactly this. Reaching for "more compute / restarts /
  another solver variant" *without a completed ladder sweep* is the tell: STOP
  and sweep.

## Relation to existing methodology

This ladder is the **spine** that sequences the previously-scattered lessons
into one forced checklist: L1 = [[root-objective-and-proxy-skew]], L2 =
[[M-general-bug-surfacing-for-scientific-code]], L3 =
[[architecture-change-on-large-gaps]], L4/L5 =
[[foundation-then-search-methodology]] + the epoch-shift trap, L7 =
[[basin-overarching-search]]; the whole is the systematic form of
[[M-general-deep-single-prompt-audit]] and
[[M-general-exhaustion-is-a-transition]]. It does not replace them; it orders
them so none is skipped.

## When NOT to run the full ladder

A genuinely trivial/mechanical task, or a wall already localized to one rung
by a recent measurement (then act on that rung). The ladder is for the
"seemingly stuck, tempted to grind the bottom" moment.
