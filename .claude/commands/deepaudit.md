---
description: Fire the deep single-prompt audit on a challenge to break a false "exhausted/walled" verdict
argument-hint: <challenge> (e.g. "ch2 large", "ch1 matching-ii", "ch2 medium")
---

You are running the **deep single-prompt audit** (methodology:
`vault/methodology/M-general-deep-single-prompt-audit.md`) on: **$ARGUMENTS**

This fires when a sub-problem has a standing "saturated / plateau / ceiling /
exhausted / walled" verdict on record **while an external signal proves a better
solution exists**. The instinct "throw more compute / another solver variant at
it" is the tell. The gap is almost never raw search effort — it is an assumption
shared by *every* branch we tried. Your job is a **diagnostic: find the flaw in
our own reasoning, not to optimize further.**

## Step 0 — Orient: concentrate on THIS challenge's vault tree (do this first, with tools)

1. **Scope the vault tree to $ARGUMENTS and read it.** This audit is about
   **$ARGUMENTS only** — build the focused subtree first, don't skim the whole
   vault. Find the relevant nodes by keyword/tag, e.g.
   `git grep -il "$ARGUMENTS" vault/` and
   `ls vault/experiments/ | grep -i <challenge-keyword>`, then read the relevant
   `vault/experiments/E-*.md`, `vault/analysis/A-*.md`, the memory pointers
   (`MEMORY.md`), and the latest `vault/sessions/` entry that touches it. Build a
   short map: the bank/best, the chain of verdicts, and every node that recorded
   an "exhausted/walled/floored/ceiling" conclusion. Stay on this challenge's
   branch — ignore unrelated challenges.
2. **Identify the target X (ground truth that beats us).** Recall or fetch the
   live leaderboard / bound for $ARGUMENTS: read-only
   `micromamba run -n spoc26 python scripts/fetch_leaderboards.py` (GraphQL
   `query` only — never submit). State our best **Y** (the bank), the known-better
   **X**, and the gap.
3. **QUESTION the recorded results — do not trust them.** Every "exhausted/walled"
   verdict in this subtree is a **false conclusion to be diagnosed**, per
   `vault/methodology/M-general-anti-oscillation-discipline.md`. For each
   load-bearing claim (a floor number, a "all methods converge", a "no feasible
   X"), ask: on what artifact was it measured? was the evaluator faithful (this
   campaign's recurring bug — optimistic/partial evaluators)? could it be an
   artifact of architecture / search-basin / probe-resolution rather than the
   problem? Re-derive the decisive number yourself in Phase 2 before believing it.

## The abstraction ladder — the spine of Phase 1 (sweep TOP-DOWN)

Full procedure: `vault/methodology/M-general-abstraction-ladder-audit.md`. A
wall can sit at any level of abstraction; the higher it sits, the more futile
*all* effort below it. Sweep these rungs **top-down**; for each, state the
current choice + the cheapest probe that would reveal a mismatch:

- **L1 Objective** — right root goal, or a proxy?
- **L2 Model/Formulation** — model faithful to the real problem (feasibility, physics)?
- **L3 Structure** — native structure (windows/clusters/components) identified & decomposed along?
- **L4 Encoding** — can the representation even *express* a solution as good as X, at the structure's scale?
- **L5 Evaluator** — is fitness/feasibility faithful and at the right resolution?
- **L6 Solver** — right algorithm family; can it express ALL constraints natively?
- **L7 Operators** — can the moves/acceptance reach the optimum's basin?
- **L8 Parameters/Compute** — tuning, resolution, iterations, restarts.

The wall is the **highest** rung whose probe returns "mismatch." We habitually
grind L7/L8 (cheap) while the gap sits at L3/L4/L6 (expensive to reconsider) —
the top-down order exists to counter that bias.

## The four phases (run all four, in order)

**Phase 1 — Assumption audit, ladder-structured.** Walk the ladder above
rung-by-rung; for EACH level list the implicit assumptions and state concretely
**what a solution that violates it would look like**. Do not skip a rung
because it is expensive to change — mark it ruled-out (by measurement) or
SUSPECT. A flat, un-laddered list is exactly what let "encoding" hide last time.

**Phase 2 — Gap accounting.** Derive/estimate a theoretical bound. Decompose the
gap between Y and X into **named, additive pieces**, and say **where the loss is
concentrated** (which legs / pairs / nodes / epochs), using **cheap arithmetic on
the banked artifact — not new search**. Reconstruct the banked objective
*exactly* first as a correctness check before trusting any delta. **Let the number
overrule the story — self-correct mid-audit** (the first mechanism you reach for
is often wrong; the arithmetic corrects it).

**Phase 3 — Paradigm inventory.** List the solution paradigms for this problem.
Mark which the tree actually touched. For each **untouched** paradigm, explain why
it was skipped and whether that reason **survives Phase-1 scrutiny** (a real
constraint, or an artifact of the flawed assumption?). The skipped-because-of-the-
flawed-assumption paradigm is the most common hiding place for the real lever.

**Phase 4 — Plan.** Propose **exactly 3 experiment lines, each violating ≥1 core
assumption** from Phase 1, ranked by expected **INFORMATION gain (not score
gain)** — cheapest assumption-falsifying probe first. **No refinements of existing
branches.**

## Operating rules

- **Measure, don't assert.** Every Phase-2 claim is a probe on the banked
  artifact; reconstruct the banked objective exactly before trusting any delta.
- **Diagnostic, not productive.** The deliverable is a **verdict + 3 ranked
  experiments**, not a bank change. Writing nothing to the bank is the expected,
  correct outcome. Do NOT submit (user-gated) and do NOT alter banks.
- **Flaw shape to hunt:** the standing verdict is almost always conditional on
  a LEVEL of the abstraction ladder (objective | model | structure | encoding |
  evaluator | solver | operators | params), never on the problem — "exhausted
  WITHIN a level is not exhausted OF the problem."
- **R1 — name the level.** No "exhausted/walled/closed" verdict is admissible
  unless it states *"exhausted at level L, levels above ruled out by measurement M."*
- **R2 — a tool wall is a solver-level fact, not lever death.** Before
  abandoning a lever, try the minimal level-changing swap (e.g. a solver that
  expresses the constraint the last one couldn't). Separate abstraction from
  implementation.
- **R3 — sibling-transfer scan.** Ask whether a tool/insight from a
  structurally-similar *sibling* instance realizes this lever; search its subtree.
- **R4 — relaxation-beats-target ⇒ constraint-handling gap.** If relaxing a
  constraint blows past X, the structure CONTAINS the solution and the gap is
  constraint-handling (encoding/solver), not search — find a tool that enforces
  the constraint natively; never file "capped."
- If the audit instead concludes — *with explicit measured evidence* — that the
  admissible optimum is genuinely reached, say so plainly; that is the one
  legitimate "done."

## Deliverable (end your run with this)

1. **Verdict** — one paragraph: is the "exhausted/walled" claim false? Which
   single unexamined assumption, named in Phase 1 and *measured* in Phase 2, is the
   load-bearing flaw (or, with explicit evidence, why it genuinely holds)?
2. **Further exploration paths (the centerpiece)** — the 3 ranked experiment lines
   from Phase 4, cheapest information-gain first. For each: the assumption it
   violates, the concrete probe (what to build/measure, roughly how cheap), and
   the **binary outcome that would falsify the assumption** (what result reopens
   the lever vs. confirms the wall). These are *new directions that question the
   recorded results*, not refinements of branches already in the tree.
3. **Record it**: write the audit as a new `vault/experiments/E-NNN-*.md` node
   (next free E-number) with `corrects:`/`reframes:` links to the verdicts it
   overturns, and add a one-line `vault/index.md` / session-note pointer. Commit
   (no push, no AI-attribution trailer, stage files by name).

Then, per CLAUDE.md §5b, if Phase 4 surfaces a live lever, **take its cheapest
step** — build and run the #1 experiment — rather than stopping at the writeup.
