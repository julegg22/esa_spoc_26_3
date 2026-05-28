---
date: 2026-05-28
tags: [concept, ch1, wsb, manifold, design, implementation-plan]
status: PROPOSAL — concrete implementation plan after Tier 0 lessons
supersedes_parts_of: C-023-wsb-low-energy-transfers
---
# C-024 — WSB design v2: concrete implementation plan

## What Tier 0 taught us (so we don't repeat)

Tier 0 confirmation (S-2026-05-27, `runs/ch1/61_wsb_tier0.log`):
- 10 LMO target pairs, 1920+ configs each, **0 improvements**.
- Diagnostic: 1058 perilune events found across all configs; closest
  approach **55,830 km from Moon — 29× the target LMO altitude of
  ~1,900 km**.

**The lesson**: random Hohmann perturbation **cannot enter Moon's SOI
precisely** for LMO targets. WSB physics doesn't make *targeting*
easier — it only makes the *LOI burn* cheaper after arrival.

For LMO transfers under our 3-impulse spec limit, we need EITHER:
- precise direct targeting (current C-022 architecture, near-saturated)
- OR a *capture orbit* intermediate (e.g., enter high-eL orbit
  ballistically, then later drift to LMO — but our 3-impulse budget
  can't fund the second descent burn cleanly)

For high-eL Moon targets (r_apo up to 8M m), the SOI is geometrically
larger, so WSB-style approach is feasible.

## Where WSB *should* work in our problem

**Targets:** Moon orbits with r_apo > 5M m (= aL > 3M m AND eL > 0.4).
There are 150 such orbits, ~133 in bank (well-used). The 17 unused
ones plus repairings of the existing 133 are the WSB opportunity space.

**Earth orbits:** any. Lower aE (LEO) benefits more from WSB savings
because LOI burn is the dominant cost (less true for GEO where dv0
dominates).

**Pair feasibility filter:**
- aL > 3M m
- eL > 0.4
- |iE - iL| > 0.3 (= where current architecture struggles most)

## Three implementations from cheap to expensive

### Tier 1A — "long-TOF + extended grid" (low-risk, ~2h compute)
Extend C-022 sweep:
- `t_max_d = 60` (vs 20 default) — let BCP catch Sun-assisted perilune
- `t2_d ∈ {1, 3, 5, 8, 12, 20}` (longer coasts; up to 20-day drift)
- Run on the 150 high-eL targets × top-K LEO pairings

Expected gain: +10-30k kg if Sun-assist shows up at all. Compute: 150
pairs × ~30 grid points × 5-10 sec/pair ≈ 4-8 hours.

This is the *cheapest* WSB-adjacent experiment — just run the existing
solver with much bigger numbers. If results match the impulsive
ceiling (= no gain over current bank), we know WSB isn't accessible
via grid expansion.

### Tier 1B — "ballistic capture target" (medium-risk, ~5h to implement + 1d compute)
Instead of position-matching pv_tgt, optimize for **Moon-relative
velocity** at perilune:

1. Apply Hohmann-like dv0
2. Propagate full BCP
3. At perilune, **don't apply dv1 plane change**; instead apply a small
   dv1 designed to *reduce* Moon-relative speed (= "captured" state)
4. Continue propagating; if spacecraft makes 2-3 lunar passes
   (multi-rev capture), Moon's gravity does the work
5. Use solve_arrival_eccentric for final dv2 LOI

Implementation cost: 1 day. Then sweep over (dv0, t_max=80d). Per-pair
compute: 1-3 min. 1500 pairs = 75-225 min. Expected gain: +20-50k kg if
the multi-pass capture mechanism is accessible in our problem instance.

### Tier 2 — explicit manifold targeting (high-risk, ~1 week + 2d compute)
Full Belbruno-Miller manifold approach:

1. Compute Earth-Moon L1/L2 Lyapunov orbits in CR3BP (planar variant)
2. Find their stable invariant manifolds (= families of trajectories
   asymptotically approaching the Lyapunov orbit)
3. For each (idE, idL), find departure conditions on the LEO that
   intersect the stable manifold within feasible TOF
4. Spacecraft "rides" the manifold to L1/L2, then descends through
   the unstable manifold toward Moon, captured at near-zero relative
   energy

References:
- Koon, W. S., Lo, M. W., Marsden, J. E., & Ross, S. D. *Dynamical
  Systems, the Three-Body Problem and Space Mission Design.* §3-4.
- Topputo, F. (2013). *Optimal control techniques for low-energy
  Earth-to-Moon transfers*. Celestial Mechanics and Dynamical
  Astronomy, 116(2-3), 89-107.
- Yagasaki, K. (2004). *Computation of low energy Earth-to-Moon
  transfers with moderate flight time*. Physica D, 197(3-4), 313-331.

Implementation cost: ~1 week. Per-pair compute: 5-30 min. Subset
applicable: ~200 pairs. Expected gain: +40-100k kg.

## Recommended sequence

1. **Run Tier 1A FIRST** (cheap, validates WSB accessibility):
   - If +5k kg or more → Tier 1B worth doing
   - If +0 kg → WSB not accessible without manifold theory (skip to Tier 2 or stop)

2. **Tier 1B if Tier 1A positive**: medium implementation cost, big
   potential gain. The "small Δv at perilune for energy reduction"
   trick is a known WSB pattern; if our BCP supports it, we'll see it.

3. **Tier 2 only if needed** — i.e., only if Tier 1A+1B fall short of
   the bank target the user is willing to settle for.

## Concrete Tier 1A script (write next)

`scripts/ch1_tier1a_extended.py`:

```python
# For each (idE, idL) where aL > 3M & eL > 0.4 & |iE-iL| > 0.3:
#   For raan_e in (8 values), ea_dep in (4), t0 in (4):
#     For t_max in (30, 45, 60):
#       For t2_d in (1, 3, 5, 8, 12, 20):
#         try_bcp_apogee_3impulse(...)
#         Keep best
# Save → rebank
```

Estimate: 150 unfilled-or-replaceable pairs × 8×4×4×3×6 = 2304
ICs/pair = ~5 sec/pair × 2304 / 8 = 1440 sec/pair WALL × 150 / 8 = bah,
just write the math the right way.

Real estimate: 150 × 2304 × 1 sec / 8 workers = 43,200 sec = 12 hours.
Overnight job.

## Open questions

1. Does the BCP integrator's `_ta()` cache work for t_max > 30 days?
   (heyoka's Taylor series may need higher tolerance for long
   integrations.) Need to verify.
2. The `solve_arrival_eccentric` was designed for short-coast arrivals.
   For long-TOF trajectories with significant Sun perturbation, the
   "arrival point" may be outside the previously-tested regime. Will
   it still converge?
3. Can we instrument the existing solver to *log* the closest-approach
   distance, so we can see post-hoc whether long TOFs actually bring
   trajectories closer to high-eL Moon orbits?

## Decision criterion to stop pursuing WSB

If Tier 1A + Tier 1B together yield <10k kg gain, the structural
ceiling under impulsive 3-burn architecture is real and we should
either:
- accept current bank for Ch1
- pivot ALL Ch1 R&D compute toward Tier 2 (manifold theory)

If the gain is +20k+ kg from 1A+1B, continue with 1B aggressively.

## Cross-references
- C-023 — original WSB proposal (Tier 0 result is here)
- C-022 — current production architecture (BCP-apogee 3-impulse)
- A-2026-05-27 — audit; B1/B2/B3 deferred fallback
- S-2026-05-27 — bugfix attempts session
