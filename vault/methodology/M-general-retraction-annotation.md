---
date: 2026-06-22
tags: [methodology, meta, research-tree, retraction, correction, provenance, falsification]
status: ACTIVE — convention for annotating overturned conclusions; distilled from the Ch1-trajectory
  cascade where E-602/604/619 + several 2026-06-21 experiments reached WRONG "exhausted/floored"
  verdicts that a later basin-overarching breakthrough overturned.
---
# Annotating corrections & retractions in the research tree

## Principle: append, never erase

A research tree's value is the **record of what was tried and why a
conclusion was believed** — including the wrong turns. Deleting or
silently rewriting an overturned conclusion destroys exactly the
information that prevents repeating the mistake. So: **never delete a
superseded conclusion. Annotate it in place, and link it bidirectionally
to the experiment that overturned it.** A reader landing on the old node
must immediately see it is retracted and where the correction lives; a
reader on the new node must see what it corrected.

## The mechanics (4 marks per retraction)

1. **Retraction banner** — the FIRST line of the body (right after the
   frontmatter), a blockquote so it renders prominently:
   > ⚠️ **RETRACTED 2026-06-22 by E-700.** The verdict *"per-pair ΔV is
   > floored at 3851 m/s"* is WRONG — it was a weak-solver artifact
   > (basin-lock), not a problem floor. A global smooth-penalty search
   > found sub-bank captures. Body preserved below as the historical
   > record; do not act on its conclusion. → see E-700, E-697.

2. **Frontmatter fields** on the retracted node:
   `corrected_by: [E-700]` and prepend the `status:` with
   `[RETRACTED 2026-06-22] …` (keep the original status text after it).

3. **Inline pin at the exact wrong claim** — leave the sentence intact;
   add a trailing `**[‡ WRONG — see E-700]**` so a reader scanning the
   body hits the correction at the precise line, not just the top.

4. **Back-link from the correcting node** — the experiment that did the
   overturning lists `corrects: [E-602, E-604, E-619, …]` in its
   frontmatter and names them in its body. Bidirectional = navigable
   both ways.

## Severity vocabulary (use the precise word)

- **RETRACTED** — the conclusion is *false* (a later result contradicts
  it). The strongest mark; the reasoning had a flaw/bug.
- **SUPERSEDED** — not false, but a better/more-complete result replaces
  it (e.g. a tighter bound, a finer evaluator). The old result still
  holds in its narrower scope.
- **REFRAMED** — the *measurement* was right but the *interpretation*
  was wrong (e.g. E-602's `corr(dv,eL)=−0.71` was a real correlation but
  a symptom, not the cause). Pin the interpretation, keep the data.
- **NARROWED** — the conclusion holds only under an assumption later
  shown non-binding (note the assumption explicitly).

Pick by *what actually changed* — a wrong number is RETRACTED; a wrong
"why" behind a right number is REFRAMED. This distinction is itself
information (it says whether to distrust the data or the story).

## Why this beats the alternatives

- **vs. deleting:** deletion loses the falsification — the single most
  valuable artifact (someone will re-propose the dead idea otherwise).
- **vs. editing the conclusion in place:** rewrites history; a future
  reader can't tell the node ever said something else, and the *reason*
  it was believed (and what evidence overturned it) vanishes.
- **vs. a separate errata file only:** the reader on the old node never
  sees it. The in-place banner guarantees the correction travels with
  the claim.

## The pattern this most often annotates

On this campaign, the recurring retraction is the **false "exhausted /
ceiling / floored" verdict that was actually a basin-lock** (see
`M-general-basin-overarching-search.md` and
`M-general-anti-oscillation-discipline.md`). When you write *any*
"exhausted/floored" conclusion, pre-emptively note the assumption it
rests on (which solver, which architecture) so that if it is later
overturned, the retraction has a clean target.
