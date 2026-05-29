---
date: 2026-05-29
tags: [analysis, ch1, physics-ceiling, planning, anti-oscillation, model]
status: AUTHORITATIVE — single coherent model to stop the WSB/B1 oscillation
---
# A-2026-05-29 — Coherent physics model (anti-oscillation document)

## Why this document exists

Across the last 3 days I've oscillated between "WSB is the path to R3"
and "proper B1 implementation alone reaches R3". Both claims were
based on careless arithmetic and partial mental models. This document
commits to a SINGLE coherent model so I stop reinventing my own
estimates.

## The corrected per-pair physics

For a transfer from Earth orbit (aE, iE) to Moon orbit (aL, eL, iL),
the optimal IMPULSIVE 3-impulse architecture is:

1. **dv0**: Hohmann from aE to apogee at Moon distance (=R_Moon ≈ 384,400 km)
   - From LEO (aE ≈ 6.5×10⁶ m): dv0 ≈ 3137 m/s
   - From GEO (aE ≈ 4.3×10⁷ m): dv0 ≈ 1100 m/s

2. **Spacecraft arrives at distance r=r_apo from Moon** (= aL·(1+eL))
   - Earth-frame velocity at Earth-apogee: v_apo_E ≈ 181 m/s
   - Moon-frame velocity at far approach: v_inf = |v_apo_E − v_Moon| ≈ 837 m/s
   - At r=r_apo from Moon (Moon's gravity has accelerated spacecraft):
     **v_perilune = sqrt(v_inf² + 2μ_M/r)**
   - For r_apo = 8×10⁶ m: v_perilune ≈ 1388 m/s

3. **dv1 + dv2 combined** at trajectory perilune (best case: aligned with orbit):
   - Target velocity at orbit apoapsis: v_target = sqrt(μ_M·(1−e)/r_apo) ≈ 455 m/s
   - Coplanar: dv_LOI = v_perilune − v_target = 933 m/s
   - With plane change Δi: dv_LOI = sqrt(v_perilune² + v_target² − 2·v_perilune·v_target·cos(Δi))

Total impulsive dv:
| LEO + Moon target (smart pair) | dv0 | dv_LOI | total | mass |
|---|---|---|---|---|
| coplanar (Δi=0) | 3137 | 933 | 4070 | **826 kg** |
| 25° plane (smart match) | 3137 | 1000 | 4137 | 800 |
| 50° plane | 3137 | 1151 | 4288 | 706 |
| 90° plane | 3137 | 1463 | 4600 | 575 |

| GEO + Moon target | dv0 | dv_LOI | total | mass |
|---|---|---|---|---|
| coplanar (typical) | 1100 | 700 | 1800 | **2200 kg** |
| 25° plane | 1100 | 750 | 1850 | 2120 |

## The impulsive bank ceiling (with PERFECT pair matching)

Given the 400 Earth × 400 Moon dataset, and Hungarian-optimal pair
selection minimizing |iE − iL| while picking best mass:

| Class | n | Optimal pair partner | Realistic max | Subtotal |
|---|---|---|---|---|
| LEO low-iE (iE<0.3) | 92 | low-iL Moon (iL<0.3) | 900 kg | 83k |
| LEO mid-iE (0.3≤iE<0.7) | 74 | mid-iL Moon (matched) | 800 kg | 59k |
| LEO high-iE (iE≥0.7) | 193 | high-iL Moon (matched) | 720 kg | 139k |
| MEO/GEO low-iE | 41 | any (Hohmann dominates) | 2200 kg | 90k |
| **Impulsive total** | **400** | | | **~371k** |

## What WSB adds

Belbruno-Miller multi-rev ballistic capture: spacecraft makes 3-6 lunar
flybys over 60-100 days, using gravity assists to slowly modify orbit
until captured at low energy. Per-transfer savings:

| Pair type | Impulsive LOI | WSB LOI | Saving | Mass gain |
|---|---|---|---|---|
| LEO+LMO (eL≈0) | 800 m/s | 100 m/s | 700 m/s | +330 kg |
| LEO+high-eL Moon | 933 m/s | 300 m/s | 633 m/s | +300 kg |
| GEO+anything | 400 m/s | 200 m/s | 200 m/s | +180 kg |

If 200 LEO transfers are WSB-amenable (long TOF OK): 200×300 = **+60k**.

**Total ceiling with impulsive perfection + WSB: ~431k kg.**

That's CLOSE to R3 (453k) but still ~22k short. Either:
- My per-class estimates remain pessimistic by 5-10%
- R3 has tricks I haven't modeled (e.g., specific lucky pair geometries)
- R1 (473k) is essentially the physical ceiling and R3 (453k) is just below

## Current bank state vs ceiling (the gap to close)

| Class | n_in_bank | Bank avg | Ceiling avg | Gap per | Total gap |
|---|---|---|---|---|---|
| LEO low-iE | 92 | 457 | 900 | -443 | -41k |
| LEO mid-iE | 66 | 384 | 800 | -416 | -27k |
| LEO high-iE | 95 | 452 | 720 | -268 | -25k |
| MEO/GEO | 41 | 1900 | 2200 | -300 | -12k |
| **Unused** | 104 | 0 | 600 avg | -600 | -62k |
| **Total gap to impulsive ceiling** | | | | | **-167k** |
| **Plus WSB headroom** | | | | | **-60k** |
| **Gap to R3** | | | | | **-238k** |

## Lever-to-gap mapping (the disciplined plan)

| Lever | Closes which part of gap | Implementation cost | Risk |
|---|---|---|---|
| **L1: Smart pair matching via joint optimization** | -50k (Hungarian uses better candidate masses) | 2 days | Low |
| **L2: B1 done right (apolune plane change w/ multi-shoot DC)** | -80k (current architecture overstates LOI dv) | 1 week | Medium |
| **L3: Crack unused 104 pairs (combine L1 + L2)** | -60k | Included with L1+L2 | Med |
| **L4: WSB / multi-rev** | -60k | 2 weeks | High |
| **L5: NLP joint dv optimization (B3)** | -20k after L1-L3 | 4 days | Medium |
| **Total potential** | -270k → bank 485k → R3+ | **3-4 weeks** | |

## How to stay on track (anti-oscillation discipline)

1. **No new "structural insight" sprints** without measuring against this
   table's predictions first. If a sprint claims X kg gain, verify the
   pair-class it would help and check the table.

2. **Per-lever validation**: implement, measure on 10 representative pairs,
   compare against ceiling prediction:
   - If actual = ceiling: ship it
   - If actual << ceiling: the implementation has a bug; debug rather than
     conclude the lever doesn't work

3. **No "WSB vs B1" framing**: both are required. Order:
   - L1+L2 first (impulsive perfection) — 1-2 weeks
   - Measure bank, see what remains
   - L4 (WSB) only if gap remains after L1+L2

4. **Decision criterion to stop chasing R3 entirely**:
   - If after L1+L2 implementation bank is < 320k (= < 65% of ceiling
     prediction), the implementation is fundamentally broken and we
     should rebuild from scratch (1-2 weeks vs piecemeal patches).
   - If bank reaches 350-400k, WSB is the right next step.

## What this means for the next 1-2 weeks

**Recommendation: stop autonomous loop NOW.** Pick one of:

A. **Submit 215k Ch1, focus on Ch2/Ch3** (lowest-risk, immediate). The
   competition might reward total score better than chasing R3 on Ch1.

B. **Commit 1-2 weeks to L1+L2 careful implementation.** Multi-shooting
   DC with proper state continuity, joint optimization over the 9 free
   continuous dofs. This is publication-grade work — sustained focus,
   not autonomous chunks.

C. **Hybrid: B + skipping into L4 (WSB)** if L1+L2 land us at 350-400k.

Option A is the safe choice. Option B is the path to R3 but requires
the user to commit human attention to the work, not just compute time.

## Cross-references
- C-022 — current production (BCP-apogee 3-impulse)
- A-2026-05-27 — original audit (B6 found, but the audit-driven sprints
  fragmented the work; this document re-frames it)
- C-023, C-024 — WSB design docs
