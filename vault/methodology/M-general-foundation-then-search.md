---
date: 2026-06-05
tags: [methodology, meta, evaluator-substrate, search, scaling, ch2-small-case]
status: ACTIVE — distilled from the 2026-06-03/05 Ch2-small breakthrough (-17.8 d in one session after 3 weeks of plateau)
---
# Foundation-then-search: clarifying the substrate before scaling compute

## The pattern (one paragraph)

**Before scaling search budget, audit the evaluator.** When multiple
diverse search methods converge to the same value, the methodology
trigger says "common-substrate failure" — but the substrate could be
the **evaluator**, not just the construction algorithm. Once a
faithful, provably-optimal-within-discretization evaluator is built,
even small search budgets (minutes) can produce breakthroughs that
months of compute under the broken evaluator could not. THEN scale
the search with that good evaluator.

## The trap

Multiple solver families converging to a single value LOOKS LIKE a
true architecture ceiling. This is the trap. The convergence can come
from any shared component:
- A construction algorithm that all methods seed from
- A move generator that's incomplete
- An evaluator that systematically misses the global optimum on each
  candidate it scores
- A discretization that excludes the optimum

The last two are the worst — they're invisible to inspection of any
individual method, and the "saturated" reading reinforces itself with
every method tried.

## The Ch2-small case (concrete example, 2026-06-03/05)

| Phase | Bank | What happened |
|---|---|---|
| 2026-05-30 → 06-03 (4 days) | 142.9183 d | Plateau across **12 method families** (greedy, LNS, GA, CMA-ES, OR-Tools, CP-SAT, multi-day GA). All use `walk_perm_chrono` evaluator (greedy chronological walk + earliest-feasible tof per leg). |
| 2026-06-03 (1 day) | 142.92 → 142.29 d (−0.6 d) | E-519b: leg-level continuous refinement on bank's schedule found 0.055 d on a single leg. **Confirmed C6 bug**: walk_perm_chrono leaves d's on the table. E-521: SLSQP-polish-aware perm search found a different bank-adjacent perm with 0.55 d more headroom. |
| 2026-06-04 (1 day) | 142.29 d (plateau) | **6 sophisticated methods** (multi-start SLSQP, perm-adjacent search rounds 2-4, fresh greedy+insert_lns, exception-leg-swap, multi-start construct) all returned 0 improvement. Looked like a "real" local opt. |
| 2026-06-05 morning | 142.29 → 126.43 d (**−15.86 d**) | E-527: forward DP on a 0.05 d-quantum Lambert grid found the provable global optimum schedule on bank's perm. SLSQP had been stuck in a basin 15.86 d above the true optimum. |
| 2026-06-05 +3 min | 126.43 → 125.08 d | E-529: ALNS using the DP evaluator found −1.35 d in 3 minutes via a `segment_reverse` mutation. |
| (in progress) | 72 h DP-ALNS | Now searching with the faithful evaluator at scale. |

**The methodological lesson**: 24 h of GA in E-516 with the broken
evaluator produced 0 improvement. 3 min of ALNS with the right
evaluator produced 1.35 d. The compute ratio is 480×. The breakthrough
isn't in the search algorithm; it's in **what each evaluation
actually measures**.

## The two-phase protocol

### Phase 1 — Foundation diagnostic (cheap, hours)

1. **Single-perm DP probe.** For one trusted perm (the bank), build
   an evaluator on a discretized grid (fine enough to be near-exact)
   that finds the PROVABLE optimum schedule on that perm via dynamic
   programming. Compare to the current method's score. Per-evaluation
   delta = the evaluator's blind spot per perm.
2. **Per-instance sanity (Bug-Surfacing P2)**. Take 3–5
   representative legs/sub-tours from the bank. Compare predicted
   (from current evaluator) vs. actual (via direct probe / oracle).
   Any ratio > 2× is a signal.
3. **Discretization audit**. What grid does each method use? If
   discretizations differ between solver-internal and truth oracle
   (e.g., greedy uses tof step 0.1 d but spec allows 0.001 d), every
   method inherits the same blind spot.
4. **The "5 distinct methods, same answer" check.** Per methodology
   trigger: when ≥3 method families converge, demand the per-instance
   check on the converged value. If the gap to per-instance optima is
   structural, it's a real ceiling. If it's evaluator slack, scale the
   foundation work, not the search.

### Phase 2 — Scaled search with faithful evaluator

5. **Build the production evaluator.** This is heavy compute (12 h+
   precompute for Ch2's ultrafine table) but **runs once** and is
   reused across all subsequent experiments. Treat it as
   infrastructure.
6. **Drop search budget at it.** Use the same algorithms (LNS, ALNS,
   CMA-ES, etc.) — only the evaluator changes. Compute budget that
   was previously wasted re-finding the same local opt now explores
   genuinely new basins.
7. **Re-evaluate prior "negative" results.** Many of the 12 methods
   that "converged" may have had near-optimal perms in their pools.
   Re-run their candidate perms through the new evaluator before
   spinning up fresh searches.

## Triggers (when this protocol fires)

| Situation | Action |
|---|---|
| ≥3 method families converge to same value | Before declaring saturation, run Phase 1 diagnostic. Default to "common-substrate suspect" rather than "true ceiling". |
| Gap to target (R3, R1) exceeds 20% of bank value | The evaluator is suspect by default; the gap is too large to be explained by perm search alone. |
| Search algorithms increasingly sophisticated, returns increasingly diminishing | Stop optimizing search. Audit the evaluator. |
| A new method matches the converged value within 0.1% | Strong evidence the evaluator (not the search algorithm) is what's being measured. |
| Discretization smaller than spec floor is detected anywhere in pipeline | Audit immediately; cascade likely. |

## What NOT to do

- Don't keep escalating search-algorithm sophistication after 3+
  converged-to-same-value runs. The marginal returns are negative.
- Don't trust "X methods converge → architecture ceiling" without a
  Phase 1 diagnostic. The Ch2-small case shows this can be wrong by
  more than 10% of bank value.
- Don't skip the precompute investment. The 12 h for Ch2's ultrafine
  table unlocked −17.8 d in one session — a return ratio that no
  search algorithm refinement could match.
- Don't conflate "SLSQP-local-optimal" with "globally optimal on this
  perm". Continuous local optimization on a Lambert (or any
  discontinuous physics) objective doesn't reach global optima
  reliably. DP on a fine grid does.

## Transfer to other challenges

**Ch1**: the analog is the trajectory solver. If we're at a plateau,
audit:
- Does the BCP/Lambert physics evaluator have systematic blind spots?
- Are tof or time grids spec-floor-aligned?
- For the current bank, what does an exact (LP or DP) bound say about
  per-leg headroom?

**Ch3**: the analog is whatever scorer determines the tie-breaker
metric. Before scaling search, run a Phase 1 diagnostic on the scorer.

**General**: any time we have a converged plateau across diverse
methods, this protocol applies. The cost is hours (precompute +
single-perm DP probe). The upside is potentially large (≥ 10% of bank
value) jumps.

## Memory pointer

This methodology is auto-loaded via
[[foundation-then-search-methodology]] in MEMORY.md.

## Companion docs

- `M-applying-methodology-triggers.md` — when each procedure fires
- `M-general-bug-surfacing-for-scientific-code.md` — adjacent
  discipline (silent-reject audits, hostile defaults)
- `M-general-anti-oscillation-discipline.md` — what to do when
  investigation cycles between explanations
