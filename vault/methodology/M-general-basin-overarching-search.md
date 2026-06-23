---
date: 2026-06-14
tags: [methodology, meta, search, local-optima, basin-crossing, acceptance-metaheuristics, ch1-matching-case, ch1-trajectory, ch2-large]
status: ACTIVE — distilled from the 2026-06-14 Ch1-matching basin-lock diagnosis (E-578 SCIP null + E-579 LAHC development); user-flagged as a cross-challenge lesson
---
# Basin-overarching search: when locally-optimal is not enough

## The pattern (one paragraph)

Some problems have a search landscape with **many local optima
separated by ridges/valleys**, where the global optimum (or even a
better rank) lives in a *different basin* than the one every one of our
methods settles into. When that is the case, **no amount of local
optimization closes the gap** — exact re-optimization of a sub-window
is *strictly weaker* than basin-crossing, because it returns the best
solution reachable **without leaving the current basin**, which is
exactly where we are already stuck. The decisive capability is a
**basin-overarching search**: a method that can deliberately move
*downhill* (accept a worse intermediate solution) or *rebuild the
discrete structure* in order to reach a different basin, then re-climb.
The user's hypothesis (2026-06-14) — and our evidence — is that this
is a *general* blocker across the campaign, not a matching quirk.

## When this applies — the diagnostic signature

You are basin-locked (NOT at a problem ceiling) when **all** of these hold:

1. **Many independent, structurally-different methods converge to the
   SAME incumbent** and find zero improving moves — including methods
   that are *exact within a window* (CP-SAT / HiGHS / Gurobi solving a
   sub-region to **proven OPTIMAL with 0 gain**). Exact-window-optimal
   means: *every neighbourhood reachable without a downhill step is
   already optimal* = a local optimum, by definition not necessarily
   global.
2. **A target above your value is provably reachable by someone.** A
   leaderboard incumbent above your bank proves the optimum is higher.
   The *fingerprint* of a competitor using basin-crossing: a **ladder /
   staircase of distinct incumbents from a single team** (73714 → 73709
   → 73697×3 → … — repeated time-limited runs each parking at a
   different incumbent), as opposed to one **identical** value every run
   (= a proven optimum). A staircase ⇒ someone is ratcheting across
   basins with an acceptance metaheuristic; the optimum is unknown and
   above r1.
3. **Headroom demonstrably exists** yet no single move captures it
   (e.g. matching: 536 unused Earth/Moon/dest nodes per type, yet no
   profitable single swap — the bank is a *single-swap local optimum*).
4. **Our search architecture is uniformly improvement-only with
   non-diversifying moves.** If every engine accepts only `m >= best`
   and resets otherwise, and destroys randomly, then by construction
   none of them can cross a ridge. The convergence is an artifact of a
   *shared architectural limitation*, not of the problem.

The trap (see also `M-general-anti-oscillation-discipline.md` and
`M-general-foundation-then-search.md`): **mistaking architectural
basin-confinement for a problem ceiling.** "N methods agree" is NOT
proof of optimality if all N share the same confinement (improvement-
only acceptance, or all seeded from the same incumbent, or all polishing
the same fixed discrete structure). Before declaring "exhausted", audit
the **search architecture**: *does any method accept a worsening move?
does any method rebuild the structure from scratch?* If the honest
answer is no, the lever is untried.

## Why local optimization fails here (the load-bearing distinction)

- **Improvement-only LNS / hill-climbing** (`lns`, `mip_lns`,
  `coop_mip_lns`): accept `m >= best`, else reset to best. Cannot take
  a lateral or worsening step → cannot cross a ridge.
- **Exact sub-window re-optimization is the *strongest possible* local
  move and still basin-locked.** This is the counter-intuitive part:
  proving a 6000-variable window optimal does not help, because the
  *partition into windows* and the *fixed surrounding structure* keep
  you in the basin. CP-SAT-to-OPTIMAL with 0 gain is the proof you are
  locked, not the proof you are done.
- **The missing capability is not "a hotter local search."** A better
  local optimizer is strictly weaker than basin-crossing. The missing
  capability is *acceptance of worse states* or *structural rebuild*.

## E-579 sub-lesson — acceptance and operator must BOTH change

Discovered while building the matching LAHC engine (2026-06-14): the
acceptance rule and the neighbourhood operator are *coupled*; changing
one without the other is inert.

- **Acceptance rule alone is inert if the operator can't reach a
  different basin.** LAHC over a strong (ejection) repair gave *zero*
  worsening-accepts: the repair always re-climbs the same basin, so
  there is nothing worse to accept. → the destroy operator was the real
  bottleneck (random-only destroy never reaches a new basin).
- **A diversifying operator alone is inert under improvement-only
  acceptance** — it generates a different basin but the acceptance rule
  immediately rejects it.
- **Repair strength gates the ceiling.** Greedy repair lands *strictly
  below* a strong incumbent every time → an acceptance metaheuristic on
  greedy repair can drift but never *reaches*, let alone exceeds, the
  bank. To exceed a strong incumbent you need **exact repair (HiGHS/CP-
  SAT on the freed window) + an acceptance metaheuristic** — i.e. take
  the existing exact-LNS and swap its improvement-only acceptance for
  LAHC/SA. That combination (strong repair × lateral acceptance × targeted
  destroy) is the one no prior engine had.
- **Cold-start caveat:** seeding the acceptance history at an
  *exceptionally strong* incumbent (the bank) freezes the search (no
  neighbour clears the bar). Preserve `best` separately, seed `cur` and
  the history at the *operator-reachable* level.
- **Move granularity:** when the incumbent is a single-swap local
  optimum, the improving move is **a few COORDINATED changes** (drop k≈3
  blockers so one heavy excluded item enters), not a large random ruin.
  Large ruin + repair just loses mass it can't reconstruct.

## The basin-overarching toolkit (ideas to try, roughly increasing cost)

1. **Acceptance metaheuristics** — Late-Acceptance Hill Climbing (LAHC),
   Simulated Annealing, Threshold Accepting, Great Deluge, Record-to-
   Record Travel. They let the incumbent drift downhill to cross ridges.
   *Pair with a diversifying operator (see 2) or they are inert.*
2. **Diverse / targeted destroy operators (ALNS)** — worst-removal,
   Shaw/related-removal, blocking-removal (free exactly the
   resources a high-value excluded element needs). Adaptive roulette
   weights, rewarded on new-best. Changes *which* basin the repair
   reaches.
3. **Diverse construction / multi-start (GRASP)** — build many
   structurally different starting solutions (e.g. perturbed-weight
   randomized greedy) and locally optimize each; samples multiple
   basins independently. Cheap, embarrassingly parallel.
4. **Recombination — path-relinking, elite pools, genetic/memetic
   algorithms** — combine features of two good solutions to land in a
   basin *neither parent occupies*. The most powerful basin-crosser for
   combinatorial structure.
5. **Structural / partition rebuild** — when the basin is *defined by a
   discrete structure* (a routing partition, a bridge set, a clustering),
   the decisive move is to **rebuild that structure from scratch** under
   a global model, not polish within it. Cluster-decomposition + exact/
   near-exact subsolver (LKH, Concorde) + re-stitch. Within-structure
   polish is *provably* basin-locked here.
6. **Exact repair × lateral acceptance** — the synthesis for set-packing-
   / assignment-style problems: keep the exact-window subsolver but
   accept worsening reconstructions (LAHC/SA), so the search exact-
   repairs its way *across* basins instead of *within* one.

## Per-challenge application (where to revisit)

- **Ch1 matching-i/ii** (set-packing): the concrete originating case.
  E-579 = LAHC/ALNS engine, pivoting to **exact-repair × LAHC** +
  targeted (blocking) destroy. r1 is a beatable incumbent (+217 / +1510
  mass), not a proven cap (E-578 SCIP null + leaderboard staircase).
- **Ch1 trajectory** (user hypothesis, 2026-06-14): the gap to the top
  ranks is very likely basin-locked too — within-*pairing* polish vs.
  **global re-pairing**. The pairing of Earth↔Moon↔destination orbits is
  the discrete structure; our per-pair refinement (E-605 BCP descent)
  optimizes *within* a fixed assignment. Re-attempt with basin-
  overarching: **diverse pairing construction + recombination /
  assignment-level metaheuristic**, not just better per-pair physics.
  (Cross-check with `M-general-foundation-then-search.md`: first confirm
  the per-pair evaluator is faithful, *then* do assignment-level basin
  search.)
- **Ch2-large** (user hypothesis, 2026-06-14): the rank-2 → rank-1 jump
  (~2× makespan gap, 932→424 d) is the archetypal basin-overarching
  problem. Within-topology LNS / per-piece LKH / retime are **proven
  exhausted** (E-587/589/591); the bank's component partition + 5-bridge
  structure *is* the basin. The decisive move is a **from-scratch global
  TD constructor that rebuilds the partition** (cluster-decomp +
  LKH/Concorde + epoch-rebuild loop) — toolkit item 5. Multi-day build,
  but it is the *only* lever that can cross this basin.
- **Ch3 / future**: any plateau where many methods agree, a competitor
  staircase sits above us, and our architecture is improvement-only ⇒
  apply this doc before declaring a ceiling.

## What NOT to do

- Don't escalate *local-search sophistication* (bigger exact windows,
  more restarts of the same improvement-only engine) once the
  diagnostic signature is present. It is strictly weaker than basin-
  crossing and will keep returning 0.
- Don't read "exact subsolver proved this window optimal, 0 gain" as
  "problem solved." Read it as "confirmed basin-locked."
- Don't ship an acceptance metaheuristic without a diversifying operator,
  or vice versa — they are coupled (E-579 sub-lesson).
- Don't seed an acceptance-history at the bank value (freeze); don't use
  large random ruin against a sharp incumbent (irreconstructible).

## ★★ CONFIRMED AS THE OVERARCHING CAMPAIGN PATTERN (2026-06-22, user-flagged)

No longer a matching quirk or a hypothesis — this is **the single
recurring shape of every breakthrough** on this campaign. The 2026-06-14
predictions in "Per-challenge application" below (Ch1-traj and Ch2-large
basin-locked) BOTH verified. Whenever "every method converges to the same
incumbent" was read as a ceiling, it was a basin-lock, and the lever was
always a basin-overarching move:

| Instance | What we kept getting | The basin-overarching move that broke it | Result |
|---|---|---|---|
| **Ch1 matching-ii** | exact-repair LNS *from the bank* = clean null (E-048/615/677) | **different START basin**: seed from the LP-rounded solution (different, better basin), then exact-repair LNS climbs past the bank | +1,047 banked (72,206→73,253) |
| **Ch1 matching-i** | shallow LNS plateaus *below* bank | **deeper destroy** (0.60 vs 0.46) = larger neighbourhood escaping the shallow basin | +15.57; gap-to-rank-3 → 4.4 m |
| **Ch1 trajectory** | 13 solvers all return the bank value *exactly* / fail; "per-pair floored" | **global smooth-penalty CMA-ES, diverse non-bank init** found sub-bank circular captures — the "floor" was a basin artifact | feasibility wall BROKEN; +117k lever proven real |
| **Ch2 small** | construction + local-2opt on a fixed graph stalls at 112.996 | missing lever = joint sequence+epoch **global** search (LKH-time-expanded / GA), a different architecture | architecture gap, not ceiling |
| **Ch2 large** | greedy corner-paints, SA basin-locks at 913 | 913→424 is **global re-interleaving** over the time-ordered structure, not local moves | characterized; rank-1 = global constructor |

**Takeaway:** when several independent methods agree on a value, the
*default* hypothesis must be **basin-lock, not ceiling** — first response
is a basin-overarching move (different start / acceptance metaheuristic /
deeper or structural destroy / global metaheuristic), NOT more
local-search sophistication. Reaching for it earlier saves weeks.

## ★ The continuous-domain extension (Ch1 trajectory, E-697)

The principle is identical for **continuous** decision vectors. Per-pair
trajectory optimization seeded from the bank returned the bank exactly
under *every* local method (DC, multiple-shooting, bank-seeded CMA-ES).
Fix = same shape: a **global metaheuristic (CMA-ES restarts / SA) with
diverse, non-bank random init**, searching for *alternative basins* in
continuous space.

**Hidden-basin-lock-via-penalty (the bug that masked it for ~13
methods):** when the problem is *constrained* and you implement the
constraint as a **flat/constant penalty for infeasible points**, the
optimizer has **zero gradient off the feasible manifold** — so the only
feasible point it can sit on is the one you *seeded* (the bank). This
looks exactly like a "feasibility wall" / "ceiling" but is a
**penalty-landscape basin-lock**. Four specific penalty bugs each
re-created it (`ch1_global_smooth.py` history): (1) constant infeasible
penalty → no gradient; (2) impact penalized *worse* than a far-miss →
search pushed *away* from target; (3) capped penalty → flat for distant
points; (4) endpoint ≠ closest-approach → wrong quantity guided. **Fix:**
a *smooth, uncapped* feasibility gradient (distance of the trajectory's
closest approach to the target manifold, incl. plane/inclination) so a
global optimizer can navigate ONTO the thin feasible manifold *from
anywhere* and find OTHER feasible basins. Once smooth + diverse init,
sub-bank solutions appeared immediately.

**Generalized rule:** *if a constrained global search "can't find
anything but the seed," suspect the PENALTY landscape, not the problem.
Make the infeasible region smoothly informative (gradient toward
feasibility) before concluding the basin is unreachable.*

## Companion docs

- `M-general-anti-oscillation-discipline.md` — recognizing a false
  "ceiling" when investigation cycles between explanations.
- `M-general-foundation-then-search.md` — audit the *evaluator* before
  scaling search; complementary (faithful evaluator first, *then* basin-
  overarching search on top).
- `M-general-deep-single-prompt-audit.md` — the 4-phase prompt to break
  a false "exhausted" verdict using an oracle that proves better exists.
- `M-applying-methodology-triggers.md` — when each procedure fires.

## Memory pointer

Auto-loaded via [[M-general-basin-overarching-search]] in MEMORY.md.
