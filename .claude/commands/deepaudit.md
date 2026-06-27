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

## Step 0 — Orient (do this first, with tools)

1. **Identify the target X (ground truth that beats us).** Recall or fetch the
   live leaderboard / bound for $ARGUMENTS: read-only
   `micromamba run -n spoc26 python scripts/fetch_leaderboards.py` (GraphQL
   `query` only — never submit). State our best **Y** (the bank) and the
   known-better **X**, and the gap.
2. **Read the whole exploration tree for $ARGUMENTS** — the relevant
   `vault/experiments/E-*.md`, `vault/analysis/A-*.md`, session notes, and the
   banked artifact (decision vector / order / edge tables in `cache/`). Treat any
   "exhausted/walled" conclusion as a **false conclusion to be diagnosed**, per
   the discipline in `vault/methodology/M-general-anti-oscillation-discipline.md`.

## The four phases (run all four, in order)

**Phase 1 — Assumption audit.** List *every* implicit assumption shared across
ALL branches: representation/encoding, how the objective is computed, the
moves/operators, what was held fixed, and what was **never measured**. For each,
state concretely **what a solution that violates it would look like**. (Make the
assumptions named and falsifiable so they stop being invisible.)

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
  **(architecture | search basin | probe resolution)**, never on the problem —
  "exhausted WITHIN an architecture/basin/model is not exhausted OF the problem."
- If the audit instead concludes — *with explicit measured evidence* — that the
  admissible optimum is genuinely reached, say so plainly; that is the one
  legitimate "done."

## Deliverable (end your run with this)

1. **Verdict** — one paragraph: is the "exhausted/walled" claim false? What
   single unexamined assumption, named in Phase 1 and measured in Phase 2, is the
   load-bearing flaw (or, with evidence, why it genuinely holds)?
2. **The 3 ranked experiments** (cheapest information-gain first), each naming the
   assumption it violates and the binary outcome that would falsify it.
3. **Record it**: write the audit as a new `vault/experiments/E-NNN-*.md` node
   (next free E-number) with `corrects:`/`reframes:` links to the verdicts it
   overturns, and add a one-line `vault/index.md` / session-note pointer. Commit
   (no push, no AI-attribution trailer, stage files by name).

Then, per CLAUDE.md §5b, if Phase 4 surfaces a live lever, **take its cheapest
step** — build and run the #1 experiment — rather than stopping at the writeup.
