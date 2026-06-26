---
date: 2026-06-26
tags: [methodology, meta, research-tree, proxy-metric, frame-skew, reframe, root-objective, premise-tagging]
status: ACTIVE — names the failure mode where VALID experiments + a skewed success-metric premise produce a
  wrong DIRECTION; distilled from the Ch2-large "moonshot" cascade reframed by E-726.
related: ["[[M-general-retraction-annotation]]", "[[M-applying-methodology-triggers]]", "[[M-general-foundation-then-search]]", "[[M-002-stuck-triggers-ultrathink-reframe]]", "[[objective-optimal-not-points]]"]
---
# Root-objective discipline & proxy-metric skew (right results, wrong direction)

## The failure mode (distinct from REFUTED and from basin-lock)

A series of experiments each returns the **correct result under its assumptions**, yet the program drifts in
the **wrong direction** — because the *conclusions* were stated in a **proxy metric that silently diverged
from the root objective.** You cannot catch this by re-checking the results: the results are right. You catch
it only by **re-expressing each conclusion in the root objective.**

This is NOT:
- **REFUTED** — a wrong number / reasoning flaw (distrust the data). Here the data is sound.
- **basin-lock / false-"exhausted"** ([[M-general-basin-overarching-search]]) — a weak solver mistaking a
  local optimum for a floor. Here the search was fine; the *yardstick* was wrong.

It IS a **REFRAMED** case ([[M-general-retraction-annotation]]): right measurement, wrong interpretation —
but at the scale of a *cluster* of nodes sharing one premise.

## The canonical case (Ch2-large rank-1, 2026-06-26, E-726)

- **Root objective:** rank = makespan of a **complete** 1051-city tour (points).
- **Proxy we tracked:** *completeness* — "cities threaded by the beam" (558–575/601).
- **The skew:** we read 575/601 as "73% → a wall → rank-1 is a 2× moonshot" and pivoted to *compressing the
  932 d bank*. But in the **root objective** the beam was **already at rank-1 pace** (0.51 d/leg, 558 @ 283 d);
  its only deficit was completeness. The true task was *"complete the already-fast beam's last ~43 cities,"*
  far more tractable than "halve 932 d." ~9 experiments and 2 sessions followed the skewed direction
  (E-721d/f/g, E-722, E-723, E-724, E-725 all carry "moonshot/wall/cascade" conclusions that the **data never
  required** — only the proxy framing did).
- The data in every one of those nodes is still valid. Only the *direction they pointed* was wrong.

## The discipline

1. **State every "wall / plateau / exhausted / moonshot" conclusion in the ROOT objective** (points / rank),
   never only in a proxy (completeness, strand-count, ΔV-floor, d/leg). If you must use a proxy, **name it and
   the assumption linking it to the objective** in the same sentence.
2. **Premise-tag conclusions.** Each load-bearing conclusion records the premise it rests on (the
   proxy↔objective link, the solver, the architecture). When a premise is corrected, **propagate**: re-examine
   every conclusion tagged with it (one premise = one auditable object, not N scattered claims).
3. **New trigger (add to [[M-applying-methodology-triggers]]):** when conclusions across **≥3 experiments
   converge on a "wall," AUDIT THE METRIC** — is the wall in the root objective or a proxy? Re-derive the
   conclusion in the root objective *before* believing it. (Sibling of the foundation-audit and basin-lock
   triggers: foundation-then-search audits the *evaluator/graph*; this audits the *yardstick*.)

## Annotating a shared-premise cluster reframe (extends M-general-retraction-annotation)

When ONE premise correction reframes MANY nodes:
- The correcting node (here E-726) carries `reframes: [E-722, E-723, ...]` and states the **shared skewed
  premise P** and its **correction P'** as a single block — so the premise is the unit of record.
- Each affected node gets a **REFRAMED banner** (not RETRACTED): *"Result valid; conclusion REFRAMED by E-726.
  Skewed premise: P. Corrected: P'. Under P', this result instead means C'."* Data preserved; direction fixed.
- Severity word: **REFRAMED** (right data, wrong story) — reserve RETRACTED for genuinely false results.

## One-line takeaway

**A correct result reported in the wrong metric is more dangerous than a wrong result — it survives every
data check and quietly steers the whole program. Always re-state "we're walled" in the root objective before
you believe it.**

## Addendum (2026-06-26): the MIRROR — evaluator-optimism (re-verify FAVORABLE numbers too)

The same day this node was written, the Ch2-large reframe (E-726) fell to the *mirror* of its own lesson: it
correctly re-stated a *pessimistic* proxy (completeness 575/601) in the root objective — but then trusted an
*optimistic* evaluator (the sparse table's "558 @ 283 d = rank-1 pace") **without re-verifying the favorable
number under the faithful/official evaluator.** A faithful retime showed that order is ~1.8 d/leg (bank pace)
and strands its tail — the 283 d was a table-optimism artifact. **Discipline cuts both ways: re-verify the
numbers that *support* your new direction under the ground-truth evaluator, not only the ones that block it.**
A favorable result from a cheap/optimistic evaluator is exactly as misleading as an unfavorable result from a
proxy metric.
