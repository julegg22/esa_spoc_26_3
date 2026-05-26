---
id: T-009
type: takeaway
status: confirmed
tags: [ch1, trajectory, plateau, gap-analysis, methodology]
parent: "[[hypotheses/H-002-ch1-trajectory-greedy]]"
created: 2026-05-26
---

# T-009 — Ch1 trajectory plateaus at ~120k kg with Lambert+DC architecture

## Bottom line

After exhaustive polish, sweep, and 3-impulse experimentation:
- **Bank: 120,194 kg, 158 transfers**
- **26.5% of rank-3 (453k)**, 25.4% of rank-1 (473k)
- Each polish iteration yields diminishing returns (10k → 3k → 0.7k kg)

## Where the gap is

For 400 transfers averaging 1183 kg = R1, leaders achieve:
- 158 transfers (vs our 158) AND
- ~1180 kg per transfer (vs our 760 kg)

We're at per-transfer Hohmann-theoretical ceiling for our specific
(idE, idL) selection. To grow further requires either:
1. **More transfers** — 200+ — requires expanding pair pool to MEO/LEO
   with feasibility for INCLINED Earth orbits (iE > 1.0 rad), where
   our solver fundamentally fails
2. **Higher per-transfer mass** — requires either:
   - WSB / Sun-assisted capture (research-grade, days to implement)
   - STM-based DC for cleaner convergence on hard pairs
   - Proper phasing-aware 3-impulse plane-change-at-apogee

## What we tried that didn't break the plateau

- Lambert + 3-D DC: gets ~700 kg for LEO+inclined, theoretical ceiling
- Long-TOF (15-25d): +10k kg (BCP Sun-assist for some pairs)
- Apogee plane change: +1k kg (works for ~3% of pairs)
- 6-D DC (force velocity match): NON-Hohmann physics, fails
- Random multi-start: too many ICs, doesn't break basin
- Expansion sweep for unused Earth orbits: 10% feasibility (iE > 1.0
  is killing field)

## Methodology takeaways

1. **The "missing physics" wasn't physics — it was solver assumptions.**
   We fixed solve_arrival_dv eccentric bug (L-012), extended TOF
   grid (C-021), tried apogee plane change (C-022). Each gave +10%
   or less.

2. **The leaders' ceiling is the SAME as ours** for our pair-set.
   They must select 400 different pairs (more LEO + circular-Moon),
   averaging 1183 kg via near-Hohmann optimization.

3. **The remaining gap is in pair selection + per-pair convergence,
   not exotic physics.** Most LEO pairs SHOULD give ~700-1000 kg
   if our DC converged to Hohmann-optimal. We're 30-50% below.

## Decision

The realistic ceiling for OUR solver as currently architected is
~120-140k kg. Further work requires:
- Day-scale dev on proper Wiesel-style 3-impulse with phasing
- Or pivot to research-grade WSB (H-009)

For the campaign:
- Bank 120,194 kg as Ch1 trajectory contribution (~rank 4-5)
- Combine with Ch1 matching, Ch2, Ch3 ranks
- Total campaign ranking determined by aggregate
