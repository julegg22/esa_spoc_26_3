---
date: 2026-05-27
tags: [session, ch1, audit, bugfix, B1, B2, B3, B4, B5, pivot]
status: bugfix-attempts-mostly-stalled — pivoting to WSB/Sun-assist
bank_start: 186,636 kg / 294 transfers
bank_end: 187,179 kg / 295 transfers (+543 / +1)
---
# S-2026-05-27 — Ch1 audit and bugfix attempts (B4+B5 only landed)

## Context
User pushed back on the slow 120k → 186k progress and the apparent
"single legacy bug" lever, asked me to write an audit prompt and execute
it. The audit (`vault/audits/A-2026-05-27-ch1-trajectory-audit.md`) found
6 bugs/risks. User directed: "go ahead with the plan as proposed and
afterwards lets tackle Sun-assisted / WSB / multi-rev transfers."

## What landed

### B4 + B5 — bipartite idD + m_l scoring (+543 kg)
File: `scripts/ch1_hungarian_rebank_v2.py`. Bank 186,636 → 187,179 kg.
Stage 1 Hungarian on (idE, idL) scored with `min(m_l, optimistic_cap)`
where `optimistic_cap = max_d c_ld[idL, d] · (200 − ΔT)`. Stage 2
Hungarian on (transfer, idD) with actual `min(m_l, cap)`. Optimistic
and actual sums matched (187,179) — bipartite found same assignment as
greedy could find. Gain MUCH smaller than the audit estimate (+5–15k).

**Why so small:** mean c_ld = 8.4, max = 75. For a typical 8-day transfer,
even the lowest c_ld gives cap = 192 × c_ld ≈ 200 kg per kg-of-c_ld. Most
m_l values are well below cap for ANY idD with c_ld > 5, and only c_ld=0
entries (rare) cause real losses. The greedy was already near-optimal.

## What I tried but didn't land

### B2 — drop pv_tgt over-constraint
Three attempted implementations:

1. **`src/esa_spoc_26/ch1_two_impulse.py`** (Lambert + solve_arrival).
   First version used pure Hohmann dv0 — failed because trajectory
   from `ea_dep=0` never gets close enough to Moon (perilune ~ 200,000
   km away for coplanar LEO Hohmann, way outside any target r-range).
   Second version: Lambert to Moon center. Failed because the rotation
   between Lambert's inertial frame and the synodic propagator wasn't
   handled correctly — even after adding R(t) rotations, the resulting
   dv0 magnitudes were 7 km/s+ for Moon-center targets (impactor-like
   trajectories). Only (277, 189) GEO+high-eL succeeded with 1507 kg
   vs bank 2628 — regression.

2. **`src/esa_spoc_26/ch1_nlp_solver.py`** (8-var joint NLP via Nelder-
   Mead). Too slow: each NLP step calls `propagate()`, which calls
   `_ta()` cache — but Nelder-Mead does ~200 steps × multiple restarts ×
   grid; 4 restarts × 32 configs = 128 NLP calls per pair, each ~30s.
   All test pairs FAIL in this implementation; objective seems to settle
   in infeasible regions.

3. **`scripts/ch1_b2_polish.py`** (extend existing solver sweep with
   `raan_l`/`argp_l`). 1024 ICs/pair × 295 pairs ≈ 3 hours wall on 8
   workers. Started but not run to completion in this session. The
   most likely path to actually validate B2; deferred.

### B1 — plane change at apolune of target orbit
File: `src/esa_spoc_26/ch1_bcp_apolune.py`. Replaces
`track_to_perilune` with `track_to_target_r(r_target = aL·(1+eL))`.
Quick test on (213, 19) LMO target showed B1 collapses to old behavior
when eL≈0 (correct — apolune = perilune for circular Moon orbits).
**Did NOT test on a high-eL pair where B1 should differ** — the full-
grid test timed out at 10 min. The implementation works conceptually
but a focused fast-validation harness is needed.

### B3 — joint dv NLP
Subsumed in the `ch1_nlp_solver.py` attempt above. Same failure mode:
too slow, doesn't converge.

### B6 — t0 rotation bug
Identified but not isolated. Most cycles used t0=0 where the bug is
silent. Low priority per audit estimate (<2k kg).

## Deeper insights learned during the attempts

### The bank's TOP transfers are *already at physics ceiling*
Top-5 by mass — (277,189) 2628 kg etc. — all have **dv1 = 0**. The 3-
impulse architecture collapsed to 2-impulse Hohmann + LOI at apoapsis.
These are near the rocket-equation ceiling for their (aE, eL) class
(GEO + high-eL). **No bugfix helps these.**

### The bank's BOTTOM transfers are *pair-mismatched, not solver-limited*
Bottom-10 by mass — (213,19) 5 kg, (24,308) 23 kg, etc. — all have
total dv ≈ 5–7 km/s. The cost is iE↔iL mismatch (e.g., iE=0.2 LEO
paired with iL=1.07 polar LMO requires ~60° plane change). At any
velocity, this rotation costs 1.5–2 km/s of dv. **No B1/B2/B3 fix
saves these — they're physically expensive pairs that Hungarian was
forced to include because nothing better was available for these
idE/idL slots.**

### dv1 distribution across the 295 banked transfers
- 120 transfers (41%) have `dv1 = 0` exactly (effectively 2-impulse, already optimal)
- 102 (35%) have `dv1 ∈ [500, 1000]` m/s (likely structural fix could trim these)
- 63 (21%) have `dv1 > 1000` m/s (largest implementation headroom)

So **headroom from B1/B2/B3 is concentrated in ~165 transfers**, and
the per-transfer kg gain depends on how much dv reduction the
architecture fix yields.

### The leaderboard's 1183 kg/transfer average implies non-Hohmann physics
The minimum impulsive dv for LEO → Moon orbit is ~3.94 km/s
(Hohmann + LOI). That gives 892 kg. Rank-1 averages **1183 kg/
transfer** → average dv ≈ 3.32 km/s. **620 m/s below the impulsive
Hohmann minimum.** That's a strong signal they exploit BCP's
solar/lunar gravity for ballistic capture (= WSB / multi-rev transfers).

## Pivot: WSB / Sun-assisted / multi-rev transfers

### Why this matters now
The audit-fix track has shown its ceiling: even if B1/B2/B3 are
implemented well and yield the full audit estimate (+70k kg), we
reach ~260k kg / R6 territory. The R1-R3 cluster at 450k+ kg is
unreachable without sub-impulsive-minimum transfers.

### Approach plan (next session)
1. **Survey** the WSB/low-energy-transfer literature for BCP
   formulations (Belbruno & Miller 1993; Koon-Lo-Marsden-Ross; Topputo
   2013; Yagasaki 2004). Identify the *invariant manifold* approach:
   weak-stability-boundary trajectories along Sun-Earth-Moon L1/L2
   manifolds give *ballistic capture* (essentially zero LOI burn).
2. **Identify which (idE, idL) pairs are WSB-amenable.** Likely
   condition: long TOF (~80-100 days), Moon-side perilune approach
   nearly tangent to the target orbit, prograde geometry.
3. **Implement** a low-energy transfer solver in BCP:
   - Heyoka-based BCP propagation (already in place)
   - Differential corrector targeting *capture* (= bounded distance
     from Moon for N days post-arrival), not classical orbital element
     match — then "drift" into target orbit.
   - Per-pair cost likely 5-30 min of compute; only worth doing for
     the worst-mass pairs (the 63 with dv1 > 1000 m/s).
4. **Hybrid bank**: keep current high-mass transfers, replace
   low-mass ones with WSB trajectories where they yield > 800 kg.

### Open questions before implementation
- The 200-day per-transfer limit is generous (allows 80-day WSB).
- Will UDP's `_match_orbit` tolerance (1e-6) accept WSB-captured
  states? Probably yes — capture states drift onto the target orbit
  asymptotically.
- Single-pass WSB or multi-rev (= multiple lunar passes before
  capture)? Multi-rev gives more dv savings but longer TOF.

## Files added this session
- `vault/audits/A-2026-05-27-ch1-trajectory-audit.md` — the audit
- `scripts/ch1_hungarian_rebank_v2.py` — B4+B5 landed
- `scripts/ch1_b2_polish.py` — B2 polish (raan_l/argp_l) — deferred
- `scripts/ch1_b2_test.py` — B2 quick validation harness
- `src/esa_spoc_26/ch1_two_impulse.py` — 2-impulse Lambert attempt
- `src/esa_spoc_26/ch1_nlp_solver.py` — 8-var NLP attempt
- `src/esa_spoc_26/ch1_arrival_scan.py` — trajectory r-scan attempt
- `src/esa_spoc_26/ch1_bcp_apolune.py` — B1 apolune-targeting
- `runs/ch1/60_b2_polish.log` — B2 polish run log (incomplete)

## Bank state at session end
- **187,179 kg** validated by UDP
- **295 transfers** of 400
- Avg per transfer: 634 kg (R3 leaders: ~1133)
- **R3 target: 453,000 kg; gap: +266,000 kg**
- The remaining 265k kg gap *requires* non-impulsive-Hohmann physics
  (WSB/low-energy transfers) — see analysis above.
