---
date: 2026-06-15
tags: [methodology, meta, search, architecture-change, gap-magnitude, exploration-floor, ch1-trajectory-case, ch2-small-case]
status: ACTIVE — user-stated 2026-06-15 during the Ch1-trajectory joint-architecture decision; generalizes [[M-general-basin-overarching-search]]
---
# Reopen the exploration floor on large gaps: gap magnitude as an architecture-change signal

## The lesson (one paragraph, user-stated 2026-06-15)

When a set of experiments is **exhausted within an architecture**, that
is NOT a stopping condition — it is a trigger to **reopen the
exploration floor** one level up and search for the *most plausible
solution architecture*, not the next incremental tweak. The decision
rule that tells you *when* to do this is the **magnitude of the
remaining gap**. Our target is to **win** (rank 1 on every task), so a
**large performance gap** — equivalently, a **large required step that
is provably impossible to reach by continuous (within-architecture)
improvement** — is itself the indicator that an **architecture change
is necessary**. Small residuals can be chased with better local search;
large ones cannot, and continuing to grind within the exhausted
architecture is wasted compute that masquerades as progress.

## Why gap magnitude is the right discriminator

Two different situations both look like "our methods stopped improving":

- **Small gap (continuous-improvement regime).** The leader/optimum
  sits a few % above us, and each method family chips a little off.
  Here the right move is *more/better local search within the current
  architecture* (tuning, restarts, longer runs, a sharper evaluator).
- **Large gap / large discrete step (architecture-change regime).** The
  target requires a jump that no sequence of local moves can bridge —
  a factor-2×, a multi-rank staircase, a step that would need a
  *qualitatively different* solution structure. Here local search is
  **strictly weaker than what's required by construction**, so grinding
  it is futile. The size of the gap is the evidence: if closing it
  demands a step far larger than any single within-architecture lever
  has ever produced, the architecture — not the search effort — is the
  binding constraint.

The trap is treating the second case as if it were the first:
"our 7 methods converged ⇒ ceiling" silently assumes the gap is small
enough that convergence implies exhaustion-of-problem. It usually means
exhaustion-of-*architecture*. (See the flaw shape in
[[M-general-deep-single-prompt-audit]]: *exhausted-within-(architecture
| basin | probe-resolution) ≠ exhausted-of-problem*.)

## The procedure

1. **Confirm within-architecture exhaustion, not just one null.** Several
   structurally-different methods *that share a substrate* converge to
   the same incumbent with zero improving moves (per
   [[M-004-convergence-watchdog-across-families]] and
   [[M-general-basin-overarching-search]]). Convergence of a *family*
   that shares an architecture is evidence about the architecture, not
   the problem.
2. **Quantify the gap as a required step.** Express the distance to the
   winning target in the same units as your levers (Δ-mass, Δ-days,
   Δ-rank, ×-factor). Compare it to the *largest step any single
   within-architecture lever has ever delivered.* If the required step
   ≫ the best realized lever, you are in the architecture-change regime.
3. **Decompose the gap before naming a new architecture.** A large gap
   is often a **product of coupled sub-levers** that looks like one
   separable lever until the arithmetic is corrected (Ch1-trajectory:
   the "2734 m/s/pair" artifact hid that the 2× = Lever A [per-pair dv]
   × Lever B [fill], a *coupled* matching×trajectory problem). Per
   [[M-applying-methodology-triggers]], a new-architecture proposal must
   fit a row of the quantitative gap decomposition or explain the
   residual — this guards against jumping to a shiny rewrite that
   doesn't actually target the gap.
4. **Reopen the exploration floor: enumerate candidate architectures.**
   List the qualitatively-different solution structures that *could*
   produce a step of the required magnitude (e.g. joint sequence+epoch
   global search with free timing; basin-crossing acceptance
   metaheuristics; a different physical regime). Prefer the *most
   plausible* one given external intel ([[M-005-external-intel-survey]])
   and the gap decomposition.
5. **Gate the build by ROI against the realized-points goal.** An
   architecture change is expensive. Fund it when (a) the within-arch
   lever is *decisively* closed on a *searched* floor (not assumed), AND
   (b) the payoff is a real rank gain weighted by task difficulty. The
   *same* architecture lesson can be worth building on one instance and
   shelving on another purely on payoff (see the two cases below).

## The architecture-change candidate set (user-identified 2026-06-15)

The campaign's architecture-change candidates are **exactly the three
instances whose banks sit a large discrepancy below the leader** — the
gap-magnitude rule applied across all six instances picks out these
three and excludes the other three:

| instance | our bank | leader r1 | gap | rank | candidate architecture |
|---|---|---|---|---|---|
| **Ch1 trajectory** | 236,420 kg | 473,333 kg | **~2.0×** | 6 | joint matching+trajectory+epoch global opt w/ feasible-manifold seeding |
| **Ch2 large** | 932.53 d | 424.62 d | **~2.2×** | 2 | cluster-decomposition + time-expanded LKH/Concorde over joint route+epoch |
| **Ch2 small** | 112.996 d | 101.65 d | ~11% (11.3 d) | 6 | joint sequence+epoch / time-expanded LKH (epochs free) |

Excluded as a *points* target (gap small or already won): **Ch2 medium**
(bank 192.90 d = rank 1 already), **Ch1 matching-i/ii** (closed across 7
families, gap is not an architecture-sized step).

**But Ch2-medium IS a worthwhile architecture target for non-rank
reasons (user, 2026-06-15):** it's the *same KTTSP class* as small/large,
so the shared joint seq+epoch machinery runs on it directly, and it is
our **only rank-1 KTTSP** — i.e. the one instance with a known-good,
field-best bank (192.90, found by our *current* greedy+sub-tour-bridge
architecture). That makes it the ideal **calibration positive-control**:
if the new architecture reproduces/beats 192.90 on medium it validates
the machinery before we trust it on small/large (where no known-good
answer exists to check against — exactly the role the 4 bank controls
played in the Ch1 Stage-0 fill probe); if it *fails* to reach 192.90 we
catch an architecture bug cheaply. Secondary benefit: rank-1 rests on a
thin ~2.8 d cushion over the live r1board, so any absolute headroom the
architecture finds *defends* the most valuable thing we hold. ⇒ medium =
**near-free calibration/defensive run** of the shared core, NOT a
funded points build, and the natural FIRST instance to point the new
machinery at (cheap validation) before the high-step large build. Note:
we have no external oracle proving medium is far from optimal, and our
current architecture already produced the field-best there, so expected
*absolute* gain is lower than on small/large.

**Shared-machinery insight (the reason to treat these as one
investment).** All three want the *same class* of capability — a
**global search over a precomputed cost/ΔV–ToF tensor that jointly
optimizes discrete structure AND continuous timing/epochs**, with
basin-crossing acceptance. Ch1-traj adds the assignment (matching) layer
on top; Ch2-small/large are the time-dependent orbital-TSP form (large
also needs cluster-decomposition to scale n=1051). So building reusable
joint seq/assignment+epoch + time-expanded-LKH infrastructure
**amortizes across all three** — which strengthens the ROI case for the
first build (Ch1-traj) and turns the others into lower-marginal-cost
retrofits.

### Per-instance status

- **Ch1-trajectory — FUNDED (build underway).** Per-pair lever closed on
  a *globally-searched* floor (E-619: 0/3 winners beat ~3851 m/s; Lever A
  caps ~1.1×, not the 1.69× the corrected decomposition hoped). The 2×
  gap (and the +136k-kg / multi-rank step to rank-5) is far larger than
  any per-pair lever can yield ⇒ architecture-change regime. Reopened the
  floor → joint matching+trajectory+epoch optimizer. High payoff
  (hard-weighted, multi-rank) ⇒ user greenlit; Stage 0 (empty-slot fill
  feasibility) gating the build now.
- **Ch2-large — CANDIDATE (highest-weight prize, hardest step).** Bank
  932.53 d = SECURE rank 2; r1 424.62 d is a ~2.2× step (more than
  halving makespan), and competitor inference attributes TGMA's
  1143→424 jump to **cluster-decomposition + LKH/Concorde** — an
  architecture we don't have. Prior "search EV≈0" verdict was under the
  *intermediate-rank* lens (no rank between our r2 and r1); under the
  *win = rank-1* goal it is the single most valuable point swing in the
  campaign (hard ×16/9), but the largest required step ⇒ fund only after
  the shared joint-search machinery exists and Ch1 validates it.
- **Ch2-small — CANDIDATE (cheapest retrofit).** Three orthogonal nulls
  (E-616/617/618) confirm everything *within* our
  construction+local-moves-on-fixed-graph architecture floors at
  112.996 d; the competitor band sits inside the unreachable zone ⇒
  basin-locked, needs the joint sequence+epoch / time-expanded LKH we
  never built. Easy (×1) task, crowded band above ⇒ best case +1 wpt in
  isolation, but it is the **lowest-marginal-cost** instance once the
  Ch1/large machinery exists ⇒ revisit as a near-free byproduct. Verdict
  correctly scoped: *"search frontier CLOSED — do not reopen without
  joint sequence+epoch global search."*

## Anti-patterns this prevents

- **Grinding an exhausted architecture** because "the runs are still
  going" — compute spent inside a basin that provably cannot reach the
  target is not progress.
- **Calling a large gap a "ceiling."** Convergence of a same-substrate
  method family is not proof the problem is solved to its floor.
- **Jumping to a rewrite without decomposing the gap** — the new
  architecture must target a quantified row of the gap, not a hunch.
- **Funding every architecture change the lesson surfaces** — gate by
  difficulty-weighted rank payoff; defer low-ROI instances.

## Relationship to neighbouring methodology

- [[M-general-basin-overarching-search]] — the *mechanism* (basins,
  downhill acceptance, structural rebuild) for one common kind of needed
  architecture change. This node is the *decision rule* (gap magnitude)
  for *when* to invoke it or any other architecture change.
- [[M-general-deep-single-prompt-audit]] — the audit that breaks a false
  "exhausted/ceiling" verdict; supplies the *flaw shape*
  (exhausted-within-X ≠ exhausted-of-problem).
- [[M-general-anti-oscillation-discipline]] — guards the *other* failure
  mode: don't declare "new architecture needed!" on every plateau;
  require decisive within-arch closure + a gap-decomposition fit first.
- [[M-002-stuck-triggers-ultrathink-reframe]],
  [[M-003-approach-family-inventory]] — upstream triggers that surface
  the candidate-architecture inventory.
