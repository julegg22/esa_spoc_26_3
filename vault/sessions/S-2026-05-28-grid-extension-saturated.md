---
date: 2026-05-28
tags: [session, ch1, polish, phase-a, cmaes, tier1a, saturated, decision]
status: GRID EXTENSION SATURATED — pivot decision time
bank_start: 187,179 kg / 295 transfers (post-audit)
bank_end: 214,209 kg / 296 transfers
target_R3: 453,000 kg
---
# S-2026-05-28 — Ch1 grid extension reaches local optimum

## TL;DR
This 24h session ran four sequential lever attempts:

| Lever | Bank ⇒ | Δ |
|---|---|---|
| Polish (extended t2_d ∈ {2,3,5}) | 187k → 209k | **+22.4k** |
| Phase A v2 (12k new candidates) | 209k → 213k | +3k |
| CMA-ES on bottom 200 | 213k → 213k | +0.2k |
| Tier 1A v2 (long-TOF Sun-assist probe) | 213k → 214k | **+0.2k** |

**Total: +27k kg.** Each lever produced ~10× less than the previous. Final
state is a *local optimum* w.r.t. the candidate pool: even after adding
462 strict "better" pair-candidates from Tier 1A v2, **Hungarian could
not find any profitable swap chain.** Bank is saturated at 214,209 kg.

## Why the bank is locked at 214k

Diagnosed during the last rebank:
- Tier 1A v2 found 452 candidates where the *specific (idE, idL) mass*
  exceeds the bank's existing pair-mass.
- But the bipartite constraint means using a new pair displaces both
  the current idE-partner AND idL-partner. The displaced ones need
  alternative pairings *in our pool* to land profitably.
- **Those displacement-alternatives aren't in our pool** — they'd
  require evaluating (currently-banked-idE, alternative-idL) for
  almost every banked transfer. With 296 banked × ~50 unevaluated
  alternatives each = ~15k new evaluations, but the EXPECTED gain is
  small because the bank is already polish-optimized.

So the issue isn't "we need more samples" — it's that the IMPULSIVE
3-IMPULSE ARCHITECTURE is hitting its physical ceiling under this
candidate pool.

## Where this leaves us

**Bank: 214,209 kg / 296 transfers**
- Avg per transfer: 724 kg (R3 leaders: ~1130 kg)
- Median: 690 kg (was 560 pre-polish; polish raised median +130)
- Distribution: 41 transfers >1000 kg, 91 transfers <500 kg
- 104 unused (idE, idL) slots remaining

**R3 (453k kg) gap: -239k kg.** Cannot be closed by impulsive
3-impulse optimization. Requires either:
1. **WSB / manifold-theoretic transfers** (1-2 weeks R&D, +60-100k kg
   potential per C-024 design)
2. **Acceptance** — submit 214k and pivot to harvest gains on Ch2/Ch3
   (where our ranks may matter more for the total competition score)

## What I'd do next (recommendation)

**Stop autonomous grinding on Ch1 impulsive optimization.** Compelling
evidence:
- Every lever this session produced diminishing returns
- Bipartite Hungarian on current pool is at local optimum
- Top-rank average dv (3320 m/s) is below impulsive Hohmann minimum
  (3940 m/s) — direct evidence competitors use non-impulsive physics
- Grid extension found one big win (polish +22k via t2_d=5d), but
  subsequent extensions are dry

**Branch decision:**
- If competition score depends primarily on Ch1: invest in WSB/Tier 2
- If Ch2/Ch3 matter equally: submit Ch1 = 214k, focus elsewhere

## Cross-references
- C-024 — WSB design v2 (the structural lever)
- A-2026-05-27 — original audit (B1/B2/B3 deferred fallback)
- C-022 — current production architecture (BCP-apogee 3-impulse)
