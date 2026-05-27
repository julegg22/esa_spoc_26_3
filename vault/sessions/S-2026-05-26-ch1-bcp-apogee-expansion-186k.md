---
date: 2026-05-26
tags: [session, ch1, trajectory, bcp-apogee, expansion, pair-selection]
---
# S-2026-05-26 — Ch1 BCP-apogee expansion: 120,794 → 186,636 kg

## TL;DR
Single autonomous session **+65,842 kg / +136 transfers** (158 → 294)
by systematically widening (idE, idL) pair selection while reusing the
already-banked C-022 BCP-tracked apogee 3-impulse architecture. We hit
a hard ceiling at 294 transfers — the remaining 106 unused (idE, idL)
pairs return 0% feasibility under our current architecture even with
extended t_max=40d and raan_l sweep, so further progress requires a
genuinely different transfer architecture, not more sweeping.

## Pair-selection heuristics (this session's main lever)

The C-022 architecture (banked in fec0f68) was capable of solving far
more pairs than its initial sweep tried. Each cycle below changed only
the **scoring function** that picks which (idE, idL) candidates to test:

| Cycle | Scoring | Bank | Δ kg | Δ transfers | Why it worked / saturated |
|---|---|---|---|---|---|
| start | (baseline from prior session) | 120,794 | — | 158 | C-022 first polish |
| v2 | per-idE: top-K idL by `m·(1+eL)` (eL-biased) | 128,020 | +7.2k | +3 | eL-bias makes all unused idEs converge on 3 high-eL idLs (152, 275, 225 → 225 fails). uL=3 caps Hungarian. |
| v3 | per-idL: top-K idE by raw Hohmann | 130,451 | +2.4k | +3 | smallest-aE unused idEs (GEO!) win for every idL → uE=3, uL=40 but only 3 idLs new |
| v6 | cross-product 236 LEO × 42 "favorable" Moon idLs (aL>4.5e6, eL>0.4) | 157,982 | +27.5k | +56 | matches BCP-apogee's natural sweet spot (Earth-Hohmann apogee at Moon distance, high-eL Moon orbit puts arrival at low velocity). 100% valid rate on first 400 |
| v7 | per-idL: top-K idE by smallest `\|iE − iL\|` | 183,591 | +25.6k | +88 | **breakthrough scoring**: high-iE LEO needs iL-matched Moon orbit to minimize plane-change at apogee. Final uE=160, uL=138 |
| v8 | per-idE: top-K idL by smallest `\|iE − iL\|` (complement) | 186,636 | +3.0k | +10 | covers the corner v7 missed; 6% valid rate (the hard pairs) |
| v9 | extended t_max=40d + raan_l sweep on 106 leftover | 186,636 | +0 | +0 | **0% valid** in 100 pairs — confirms architectural ceiling |

## Key insights

### 1. C-022's natural sweet spot is a 4-D corner, not a hyperplane
BCP-apogee 3-impulse with Hohmann burn from LEO targets:
- aL ≈ 4.5–5.3 × 10⁶ m (Earth-Hohmann apogee = Moon distance for LEO)
- eL > 0.4 (Moon orbit's apoapsis matches transfer apogee)
- iL ≈ iE (minimizes plane-change cost paid at apogee)

42 unused Moon idLs satisfy the (aL, eL) criterion. v6 + v7 + v8 together
banked transfers in 95+ of them. The other ~10 in the favorable cluster
have unfavorable iL geometry for the remaining unused idEs.

### 2. iE distribution in unused idEs explains why scoring matters
Of 242 unused idEs at session start, **all are LEO (aE 6.6–8e6 m), 200+
are high-inclination (iE > 0.6 rad)**. The original 2-impulse solver
banked low-iE LEO + low-iE GEO. The high-iE LEO band requires C-022's
plane-change-at-apogee architecture — which works fine, but only if you
pair it with an idL whose plane geometry matches.

### 3. iL-matching scoring dominates Hohmann-mass scoring
v2/v3's Hohmann-driven scoring picked the same handful of "high-mass"
idLs for every idE, capping Hungarian. v7's `|iE − iL|` scoring spread
candidates across 138 distinct idLs while still producing 800+ kg
top-mass transfers. **Lesson**: for plane-change-paid-at-Moon
architectures, geometric compatibility (|iE − iL|) is a far stronger
selector than departure-burn-mass estimate.

### 4. Reduced grid is enough for cross-product screening
v6 used a 24-eval reduced grid (4 raan_e × 3 ea_arr × 2 t2_d). Polish
test on a v6-banked transfer showed 576-eval full grid gives **identical
mass** (659 kg → 659 kg). The grid local optimum is found by the
3-impulse DC; broader sweep doesn't escape the basin.

### 5. The 106 leftover pairs are architecturally infeasible (under C-022)
v9's extended t_max=40d + raan_l sweep on the iL-matched top-5
candidates for each of 106 unused idEs returned **0 valid** in 100
pairs. These pairs need a different mechanism — likely:
- bi-elliptic / 4-impulse for plane changes too large for single-apogee
- low-energy / WSB transfers (Moon-Sun-Earth manifold)
- DRO insertion as intermediate target

## Bank state at session end

- **186,636 kg** validated by UDP
- **294 transfers** of 400 capacity (73.5%)
- 106 unused idE, 106 unused idL, all high-iE LEO / LMO / mid-aL Moon
- Avg mass per transfer: 635 kg (Rank 3 leaders: ~1,130 kg/transfer)

## Gap to leaderboard
- Rank 1: 473,332 kg (need +286k kg)
- Rank 3: ~453,000 kg (need +266k kg)
- Filling 106 remaining slots at the current 635 kg/transfer rate gives only +67k → 254k kg
- Closing the gap requires *both* (a) cracking the unsolvable 106 with new architecture AND (b) raising per-transfer mass by ~80%

## Files added this session
- `scripts/ch1_bcp_apogee_expand_v3..v9.py` — pair-selection variants
- `runs/ch1/52_..59_*.log` + corresponding `*_results.json`

## Open questions
1. Can a 4-impulse architecture (intermediate-apogee plane change, then
   re-entry to Hohmann) unlock the leftover 106 pairs?
2. Is NLP polish on the 18 continuous chromosome vars (per banked
   transfer) worth the ~20 hours of compute for the ~50–100 kg/transfer
   gain it likely brings?
3. Are the leaderboard leaders using a fundamentally different transfer
   (low-energy / WSB)? Their per-transfer mass (~1,130 kg) is achievable
   with 2-impulse for some pairs — they may simply have a better
   *initial-guess generation* for the 21-var NLP rather than a different
   physics model.
