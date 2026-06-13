---
id: M-general-deep-single-prompt-audit
type: methodology
tags: [methodology, general, assumption-audit, anti-oscillation, ceiling-claim, exhaustion, single-prompt, publication-bound]
date: 2026-06-13
scope: project-agnostic (blog-post-ready)
related: [[M-general-anti-oscillation-discipline]], [[M-applying-methodology-triggers]], [[M-general-foundation-then-search]], [[M-002-stuck-triggers-ultrathink-reframe]], [[M-003-approach-family-inventory]], [[E-602-ch1-trajectory-gap-anatomy]], [[E-603-ch2-small-gap-anatomy]], [[E-591-ch2-large-epoch-connectivity]]
---

# M — The deep single-prompt audit (break a false "exhausted" verdict)

## What it is

A **single, structured prompt** you fire at any sub-problem that has been
declared "saturated / plateaued / ceiling / no further gains expected" **while
an external signal proves a better solution exists** (a leaderboard number, a
published result, a competitor's score, a theoretical bound). Instead of asking
the optimizer to try harder, it forces a *diagnostic*: treat the external signal
as ground truth, and hunt for the **flaw in our own reasoning** that produced the
false "exhausted" verdict.

It is the operational counterpart to the project's core lesson:

> **Exhaustion WITHIN an architecture / basin / model is not exhaustion of the
> problem.** Almost every "ceiling" verdict is conditional on an *unexamined
> assumption*. The audit's job is to name that assumption and measure past it.

It complements [[M-applying-methodology-triggers]] (which says *when* to stop and
audit) and [[M-general-anti-oscillation-discipline]] (which says *how* to stop
flip-flopping). This note is the **prompt** that does the work in one shot.

## When to fire it

- A sub-problem has ≥1 "saturated/ceiling/plateau/exhausted" verdict on record,
  **and**
- an external reference proves the achievable region extends past our best, **and**
- the instinct in the room is "throw more compute / another solver variant at it."

That instinct is the tell. The gap is almost never raw search effort; it is an
assumption shared by *every* branch we tried.

## The prompt (verbatim template — reusable)

> We are NOT done. Per [leaderboard / published result / bound], better solutions
> are known to exist. Therefore "no further gains expected" is a **false
> conclusion**, and your task is to **find the flaw in our reasoning, not to
> optimize further.**
>
> **Phase 1 — Assumption audit.** Read the whole exploration tree for this
> sub-problem. List *every* implicit assumption shared across ALL branches:
> representation/encoding, how the objective is computed, the moves/operators,
> what was held fixed, and what was *never measured*. For each assumption, state
> concretely **what a solution that violates it would look like.**
>
> **Phase 2 — Gap accounting.** Derive or estimate a theoretical bound. Decompose
> the gap between our best Y and the known-better X into named, additive pieces.
> Say **where the loss is concentrated** (which legs / pairs / nodes / layers),
> using cheap arithmetic on the banked artifact — not new search.
>
> **Phase 3 — Paradigm inventory.** List the solution paradigms for this problem.
> Mark which ones the tree actually touched. For each *untouched* paradigm,
> explain why it was skipped and whether that reason **survives Phase-1
> scrutiny** (i.e. was it skipped for a real constraint, or because of the flawed
> assumption?).
>
> **Phase 4 — Plan.** Propose exactly 3 experiment lines, **each violating ≥1
> core assumption** from Phase 1, ranked by expected **INFORMATION gain (not
> score gain)** — cheapest assumption-falsifying probe first. **No refinements of
> existing branches.**

### Why each phase is shaped this way

- **Phase 1 forces the assumptions to be *named and falsifiable*** ("what would a
  violating solution look like") so they stop being invisible.
- **Phase 2 forbids hand-waving**: the gap must reconcile to a number, computed on
  the existing banked solution (no propagation/search), so it bounds *structure*
  cheaply and honestly. This is where the decisive measurement usually lands.
- **Phase 3 catches the skipped paradigm** that was discarded *because of* the
  flawed assumption — the most common hiding place for the real lever.
- **Phase 4 ranks by INFORMATION, not score**, and bans refinements — so the
  output is the cheapest experiment that *decides whether we are trapped*, not the
  next incremental tweak. Cheap-first means you can run it without a big bet.

### Operating rules that make it work

- **Measure, don't assert.** Every Phase-2 claim is a probe on the banked
  artifact (orbit tables, edge matrices, the decision vector), reconstructing the
  banked objective *exactly* as a correctness check before trusting any delta.
- **Self-correct mid-audit.** The first mechanism you reach for is often wrong;
  the arithmetic corrects it (see Ch1 case below). Let the number overrule the
  story.
- **Diagnostic, not productive.** The deliverable is a *verdict + 3 ranked
  experiments*, not a bank change. Writing nothing to the bank is the expected
  outcome.

## Three case studies (this campaign, 2026-06-13)

All three overturned a standing "exhausted/ceiling" verdict by naming an
unexamined assumption and measuring past it. The recurring flaw pattern:
**a prior verdict was conditional on (architecture | search basin | probe
resolution), never on the problem.**

### 1. Ch1 trajectory — "exhausted" was *architecture*-conditional ([[E-602-ch1-trajectory-gap-anatomy]])
- **Standing verdict:** per-pair impulsive polish saturated; "no further gains."
- **Flaw found:** every saturation result (E-047/E-049, the 371k impulsive
  ceiling) is conditional on **A1 = impulsive patched-conic**, which the official
  BCP (Sun-perturbed) validator *never imposes*. The leaders' sub-impulsive-floor
  Δv is a proof the achievable region extends past A1.
- **Decisive measurement (Phase 2):** idD layer closed (+0.13%); matching closed
  (1.6° headroom, 65/65 stranded high-incl Earth orbits have a Moon orbit within
  0.2°); residual cost is **lunar capture, not plane change** — corr(dv, eL) =
  −0.71, and 131 near-coplanar pairs still average 4927 m/s. **Self-correction:**
  the audit first blamed plane-change-via-Sun; the arithmetic showed plane change
  is cheap (272 m/s) and re-pointed the lever to eL-stratified ballistic capture.
- **Lever (Phase 4 #1):** WSB / Sun-assisted ballistic capture at fleet scale,
  re-targeted by Moon eccentricity. Proven +17% on n=1, mis-deprioritized as
  "multi-week." → became a running probe.

### 2. Ch2 small — "DP-optimal" was *basin*-conditional ([[E-603-ch2-small-gap-anatomy]])
- **Standing verdict:** 116.38 d is the time-coupled DP optimum; exhausted.
- **Flaw found:** the DP is optimal only **within one topology basin** (a fixed
  exception-allocation + comp0 cut). The local-move ALNS was *structurally
  confined* there — its topology-changing operators produced **0/10 bankings**
  (all DP-infeasible), so every path to a different basin passed through
  infeasible intermediates.
- **Decisive measurement (Phase 2):** **flight-only (zero idle) = 109.99 d is
  already below R3 = 110.88 d** ⇒ the entire R3 gap is phasing idle the DP can't
  remove *for this perm*. 5 exceptions = 4 required bridges + 1 *chosen* shortcut;
  comp0 has no degree-1 nodes ⇒ not forced to split.
- **Lever (Phase 4 #1):** exception-allocation DP basin sweep — enumerate
  alternative bridge assignments, re-run the *existing* DP per basin (no Lambert
  recompute). Cheapest, most decisive.

### 3. Ch2 large — "connectivity wall" was *probe-resolution*-conditional ([[E-591-ch2-large-epoch-connectivity]])
- **Standing verdict:** 22 nodes "intrinsically" lack cheap transfers ⇒ rebuild
  hopeless; accept the floor.
- **Flaw found:** the "intrinsic" verdict rested on a **25-random-target sample
  (2.4%) + 0.5 d tof grid + 30 d window — all three biased toward false-intrinsic.**
  The all-1050-target, fine-grid re-scan overturned it: flagged nodes have 10–30
  cheap neighbors at every epoch.
- **Decisive measurement (Phase 2):** 932.53 d = 0.86 d/leg vs r1's 0.40; gap is
  *global* (whole tour ~2× too long per leg), with rich cheap-edge supply ⇒
  reachable only by a from-scratch global time-dependent constructor, not
  within-topology polish.
- **Lever:** re-opened the multi-day global TD rebuild as a justified (if
  point-EV-0-until-sub-r1) lever; killed the "give up, it's intrinsic" reading.

## The general takeaway (publication-bound)

> When a hard sub-problem is declared finished but an external oracle says
> otherwise, **the bug is in the verdict, not the search.** Spend one structured
> prompt to (1) name the assumption every branch shares, (2) reconcile the gap to
> an exact number on the banked artifact, (3) find the paradigm that assumption
> made you skip, and (4) propose the cheapest experiment that *violates* the
> assumption and thereby decides whether you were trapped. In three independent
> cases the flaw was the same shape — **"exhausted within (architecture | basin |
> probe resolution)" masquerading as "exhausted of the problem"** — and in each
> the decisive evidence was a cheap arithmetic measurement that the prior
> "ceiling" verdict had never bothered to take.
