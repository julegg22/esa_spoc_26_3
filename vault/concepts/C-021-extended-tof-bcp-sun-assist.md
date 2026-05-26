---
id: C-021
type: concept
status: confirmed
tags: [ch1, trajectory, tof, bcp, sun-assist, optimization]
parent: "[[lessons/L-012-solver-assumption-audit-before-research-grade-verdict]]"
created: 2026-05-26
---

# C-021 — Extended-TOF (~15-25 days) unlocks BCP Sun-assist

## Pattern

Our original Lambert+3D-DC solver swept TOF in {5, 8, 11} days
(Hohmann-region). Pure 2-body Hohmann LEO→Moon is ~5 days, so this
seemed sufficient.

**Empirical finding (S-2026-05-26):** sweeping TOF up to 25-40 days
improved 68 of 158 banked transfers, +10,086 kg total (+9.2% bank).
Optimal TOF for many inclined pairs was 15d (just 4d longer than
our prior maximum).

## Why this works

In BCP, the Sun's gravity acts as a small but non-trivial perturbation.
Over a Hohmann TOF (5d), Sun's effect is tiny. Over 15-25d, the
trajectory has time to:
- Drift in Sun's gravity gradient (small plane-change "for free")
- Pass closer to L1/L2 region, allowing weak captures
- Phase better with Moon's position for a different geometry

This is a milder form of Belbruno's Weak Stability Boundary capture.
The BCP solver finds these "for free" once the TOF grid extends
beyond pure 2-body Hohmann.

## Per-pair gain distribution

After applying this insight to all 158 banked transfers:
- 68/158 improved
- Gains: 1-400 kg per transfer
- Largest gains: low-mass LEO+inclined-Moon pairs (300-500 kg jumps)
- Top GEO transfers: marginal (1-50 kg)

## When to apply

- Always include TOF up to ~25 days in the initial sweep grid.
- For inclined-Moon pairs (iL > 0.3), include TOF up to 40 days.
- Beyond 40 days: diminishing returns and BCP integration becomes
  computationally expensive (Sun-gravity needs more steps).

## Implementation reference

`scripts/ch1_apply_long_tof.py` — applies long-TOF DC to all banked
transfers, banks improvements.
