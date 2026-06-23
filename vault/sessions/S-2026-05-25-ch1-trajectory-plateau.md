---
id: S-2026-05-25
type: session
tags: [session, ch1, trajectory, plateau, gap-analysis, methodology]
date: 2026-05-25
created: 2026-05-25
participants: [JJ, Claude Code]
claude_model: claude-opus-4-7[1m]
commits: 5+
created_nodes:
  - "[[observations/O-013-plane-change-at-earth-bug]]"
banked_changes:
  - "Ch1 trajectory: 14.82 → 109,739 kg (7,400x baseline; ~23% of rank-3)"
---

# S-2026-05-25 — Ch1 trajectory hits plateau at 109k kg

## Scope

Continuation of yesterday's eccentric-orbit breakthrough. Today's work
ran multiple expansion strategies trying to push bank toward rank-3
(453k kg) and beyond, hitting a natural plateau around 110k kg.

## Pipeline executed

| Phase | Bank | Δ | Notes |
|---|---|---|---|
| Yesterday's end | 14.82 kg | — | 1 transfer (0,0,0) |
| Production sweep (500 GEO+ec-Moon) | 42,719 kg | +42,704 | 20 transfers, ALL GEO |
| Hungarian-seeded sweep (1200) | 91,732 kg | +49,013 | 153 transfers, idL diversity |
| Tier 1A polish | 105,377 kg | +13,645 | +14.9% per-pair refinement |
| Tier 1B 3-impulse | 106,362 kg | +985 | Marginal — at 2-impulse optimum |
| raan_e sweep (partial) | 109,571 kg | +3,209 | 200/723 pairs done, killed |
| Unused-pool sweep (partial) | 109,739 kg | +168 | 60/732 pairs, only 10% feasibility |
| Super-polish (Tier 1A++) | killed | — | Slow, partial gains not banked |

**Final: 109,739 kg, 158 transfers (7,400x baseline).**

Position: ~23% of rank-3 (452,820 kg). ~23% of rank-1 (473,332 kg).

## The plateau diagnosis

### Per-pair mass ceiling analysis (today's ultrathink)

For our 158 banked transfers, median mass is 347 kg, mean 698 kg. This
is actually close to per-pair Hohmann theoretical for our specific
(idE, idL) selection:

- 41 high-altitude Earth orbits (GEO + eccentric, apo > 30 Mm): up to
  2300 kg/transfer (we achieve this).
- 21 MEO: ~1500 kg theoretical, we get similar.
- 359 LEO: 200-800 kg theoretical depending on iL (we get ~400 median).

The "missing" mass for rank-3 (343k kg gap) is from:
1. **Only 158/400 transfers used** — need 200+ more
2. **LEO+highly-inclined-Moon pairs have low theoretical** (~200-400 kg)
3. **Standard plane-change at Earth costs 1500+ m/s** vs at-SOI alternative

### O-013: plane-change-at-Earth bug

LEO+inclined-Moon pairs in bank have dv0 = 4500-6000 m/s (vs Hohmann
3242). The 1500 m/s excess is plane change at Earth velocity. The fix
(plane change at SOI) is classical mission design but our SOI 3-impulse
implementation gave bugs in the BCP propagation handoff.

### Expansion attempts hit diminishing returns

- **raan_e sweep** (Tier 2): unlocked some new idLs but mass ~700-900 kg,
  most lost to Hungarian conflicts. +3k kg total / 8h compute. KILLED.
- **Unused-pool sweep** (244 unused idEs × top-3): only 10% feasibility,
  +168 kg / 30min. KILLED.
- **Super-polish** (per-pair joint angular DOF opt): one +113 kg find,
  rest marginal. Polish too slow (~30s/transfer per start × 5 starts).
  KILLED before banking.

## What the leaders likely have (still hypothesized)

For rank-1 (473k = 4× our bank), the leaders must achieve:
- 200-400 valid transfers (we have 158)
- Per-transfer avg ~1180 kg (we have 698)

The 2× gap on transfers AND 1.7× gap on per-transfer combine to 3.5×
total. Achievable with:
1. **Proper 3-impulse with plane-change at lunar SOI** (fixes ~1000-1500 m/s
   dv inflation per LEO+inclined-Moon pair)
2. **Joint per-pair optimization with global solver** (pl2pl_N_impulses-style)
   — multi-start CMA-ES or differential evolution on full 11-var chromosome
3. **Larger sweep coverage** (~3000-5000 pair candidates) for full Hungarian

Combined effort estimate: 2-5 days of focused engineering. Beyond the
single-session window we've spent.

## Decision point

Bank at 109k kg is solid (rank 4-5 territory) given the techniques
we've successfully implemented. Going further requires:
- Days of additional dev, OR
- Accepting rank 4-5 as the realistic outcome for Ch1 trajectory

Combined with Ch2 (medium banked at projected R1) and Ch1-matching
(banked rank 5-6), the campaign aggregate is competitive even without
Ch1 trajectory at rank 3.

## Open paths preserved

[[H-008-ch1-tier2-raan-t0-sweep]] (raan/argp/t0 sweep), [[H-009-ch1-tier3-wsb-sun-assisted]] (WSB), [[H-010-ch1-tier3-backward-shooting-fix]] (backward
shooting), [[H-011-ch1-tier3-stm-based-dc]] (STM-based DC) — all documented for later pickup.
The plane-change-at-SOI implementation (O-013) is partially built in
`src/esa_spoc_26/ch1_soi_three_impulse.py` for future iteration.

## Today's commits

- Bug fix annotations: O-002, O-012 reframed post-eccentric-fix
- L-012: Solver-Assumption Audit Protocol methodology lesson
- Production sweep pipeline (8 scripts in scripts/ch1_*.py)
- Tier 2/3 hypotheses (H-008..H-011)
- O-013: plane-change-at-Earth diagnosis
