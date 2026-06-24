---
id: E-704
type: experiment
status: REFUTED (no bank change) — the trajectory Earth↔Moon ASSIGNMENT re-match lever (toward rank-5)
  does NOT help. Headroom check confirmed the bank matching is inclination-suboptimal (mean |iE-iL|
  18.63° vs Hungarian-optimal 13.45°, 391/400 re-matchable), but a sample realization of the
  inclination-optimal re-match is a NET LOSS (3/3 sampled pairs worse-or-equal: −236, −17, −1 kg). The
  |iE-iL| proxy is refuted: realized ΔV is non-separable (Moon-capture geometry dominates plane change),
  and the correct realized-ΔV cost matrix is computationally infeasible (400×400 × ~6min/solve).
date: 2026-06-23
tags: [ch1, trajectory, assignment, matching, refuted, headroom-check, proxy-failure]
related: [[E-701-ch1-eccentric-departure-solver-fix]], [[T-009-ch1-trajectory-architectural-plateau]], ch1-iL-matching-breakthrough
---
# E-704 — Ch1 trajectory: ΔV-cost assignment re-match (lever a) — REFUTED

## Mandate
User greenlit lever (a): re-assign the Earth↔Moon matching by realized ΔV to push trajectory toward
rank-5 (+42k from the banked 330,861), the one architecturally-different trajectory lever left after
the eccentric-departure fix (E-701) realized the capture+fill gains.

## Headroom check (cheap, first) — POSITIVE
`scipy.linear_sum_assignment` on the |iE-iL| cost matrix over the 400 used orbits:
- current Σ|iE-iL| = 130.03 rad (mean **18.63°/pair**)
- Hungarian-optimal = 93.91 rad (mean **13.45°/pair**) — **−27.8%**, **391/400 pairs re-matchable**.
So the bank's matching IS inclination-suboptimal (the 326 historical pairs were never globally
re-assigned; the 74 fills were matched only locally). Unlike the Ch2 Tier-0 check, headroom exists.

## Sample realization (the decisive test before the ~13h full build) — NEGATIVE
`ch1_assign_sample.py`: take the inclination-optimal re-match, realize a sample of re-matched pairs
with the eccentric backward-shoot solver, compare to the bank's realized mass for that Earth orbit:
| Earth | bank pairing | re-match pairing | Δmass |
|---|---|---|---|
| E392 | l394 = 796 kg | l391 = 560 kg | **−236** |
| E7 | l155 = 747 kg | l40 = 729 kg | **−17** |
| E241 | l50 = 663 kg | l188 = 662 kg | **−1** |
**3/3 ≤ 0** (mean ~−85/pair). The inclination-optimal Moon partner is consistently *worse* on realized
mass.

## Why the |iE-iL| proxy fails
Plane change at lunar apogee is cheap (~3 m/s/deg), so the ~5°/pair inclination reduction buys almost
nothing — while the **Moon-capture cost (eccentricity/geometry) and the specific Earth-Moon transfer
geometry dominate** the realized ΔV and are NOT captured by |iE-iL|. The bank's matching, though
inclination-suboptimal, already implicitly pairs each Earth orbit with a Moon orbit that's *cheap to
reach/capture for that geometry*. Minimizing |iE-iL| breaks those good geometric pairings.

## Verdict
Lever (a) is **closed**. The cheap proxy (|iE-iL|) is refuted; the *correct* objective (realized-ΔV
cost matrix) requires ~160k solver runs (400×400 × ~6min ≈ 280 CPU-hours) — infeasible. The
departure-energy wall (apogee-floored ΔV0 = 66%) holds; re-matching cannot move it. Trajectory stays
banked at **330,861 kg (rank 6)**, the +67,742 from E-701 secure.

## Remaining open lever (campaign)
Only **Ch2-small tof>8d table-coverage test** (E-703) is untested. Otherwise the campaign is at its
ceiling for available methods; the session's headline win — the E-701 eccentric-departure fix
(+67,742 kg) — stands. Methodology note: the headroom check (positive) → sample realization (negative)
sequence is the correct discipline — a proxy showing "headroom" must be validated on the true objective
before a multi-hour build (the proxy was misleading here, as the +5.5d DP proxy was for Ch2-small).
