---
date: 2026-05-27
tags: [concept, ch1, wsb, sun-assist, low-energy, ballistic-capture, plan]
status: PROPOSAL — strategy for next session
---
# C-023 — Weak Stability Boundary / Sun-assisted low-energy transfers

## Why this is the next pivot

After the audit (A-2026-05-27) and bugfix attempts (S-2026-05-27), the
analysis is clear:

- Our bank's *top* transfers are at physical ceiling (2628 kg at 1430 m/s).
- Our bank's *bottom* transfers are pair-mismatched (Hungarian forced
  expensive plane changes onto 7 km/s trajectories).
- The leaderboard's **3320 m/s average dv per transfer is ~620 m/s
  BELOW impulsive Hohmann+LOI minimum**.
- The R1-R3 cluster within ~20k kg suggests a *common method* —
  almost certainly **ballistic capture** via Sun-Earth-Moon
  invariant manifolds.

The 265k kg gap to R3 is *physically un-bridgeable* by impulsive
trajectory optimization. Only non-Hohmann physics closes it.

## The physics: ballistic capture saves the LOI burn

Classical Hohmann + LOI from LEO (r_LEO = 6500 km):
- dv0 (Hohmann TLI) = 3.14 km/s
- dv2 (LOI to LMO) = 0.80 km/s
- Total = 3.94 km/s → m = 892 kg

WSB / ballistic capture from LEO:
- dv0 ≈ 3.15 km/s (similar, but tuned for manifold injection)
- TOF: 80-120 days (vs 5 days direct Hohmann)
- dv2 ≈ 0 (or 50-200 m/s, depending on target orbit eccentricity)
- Total ≈ 3.20 km/s → m ≈ 1300 kg

**Savings: ~400 kg per LEO transfer × 200 LEO transfers ≈ +80,000 kg
to bank.** Closes ~30% of the R3 gap.

## The mechanism

1. Apply dv0 to enter a high-energy Earth orbit (apogee near or beyond
   Moon's orbit, ~1.0–1.5 × R_Moon distance).
2. Over ~50–80 days, **Sun's gravity** in BCP perturbs the apogee
   altitude and orientation. Earth's gravitational well becomes weaker
   compared to Sun's at distances beyond ~1.5 million km — the
   spacecraft enters the *weak stability boundary*.
3. Either:
   - **Single-pass WSB**: trajectory threads through Sun-Earth L1/L2
     manifold, descends back onto an Earth-Moon L1/L2 manifold,
     captures around Moon ballistically.
   - **Multi-rev**: trajectory makes multiple lunar passes; each pass
     transfers energy via lunar gravity assist; eventually orbit
     becomes Moon-encountering at low relative velocity.
4. At lunar arrival, spacecraft has near-zero Moon-relative excess
   velocity. A tiny dv2 nudges it onto the target orbit.

## Why our naïve "long TOF" attempts failed

`runs/ch1/59_bcp_apogee_expand_v9.log` and the just-written
`ch1_wsb_explore.py` both attempted "long TOF" without success:

1. **TOF alone is not enough.** The dv0 *direction and magnitude* must
   be tuned to inject onto a manifold. Random dv0 just wanders.
2. **Our solvers use solve_arrival_eccentric, which expects spacecraft
   within [r_peri, r_apo] of target orbit.** For ballistic capture
   trajectories, the spacecraft enters Moon SOI on a *capture orbit*
   (typically high eccentricity around Moon). This may or may not
   align with the target (a, e, i) — usually we want capture into
   a *slightly different* orbit, then drift over time.

## Implementation plan (3-tiered)

### Tier 0 — confirmation experiment (1 day)
Verify WSB exists in our problem instance:
- Pick 5 LEO+LMO test pairs currently at ~500 kg
- For each, sweep (dv0_magnitude ∈ [3.10, 3.20] km/s, dv0_direction
  ∈ ±10°, TOF ∈ [60, 120] days)
- Propagate full BCP, find perilune passes, evaluate
  solve_arrival_eccentric at each
- **Success criterion**: at least one pair finds m > 1100 kg
- Confirms that the BCP dynamics support low-energy transfers in
  *this specific problem instance*

### Tier 1 — manifold-targeting (2 days)
Implement a manifold-targeting differential corrector:
- Target the Earth-Moon L1 or L2 *Lyapunov orbit* (in the BCP
  rotating frame)
- DC variables: dv0_3 + TOF
- Constraint: spacecraft state at TOF matches a state on the
  Lyapunov orbit
- Start with planar L1 orbits (lower-dimensional search)
- For each (idE, idL): find dv0 + TOF; from Lyapunov, "spiral in"
  to Moon along stable manifold; drift onto target orbit

### Tier 2 — multi-rev EGA/MGA (1 week)
Multi-revolution trajectories with multiple Moon passes:
- Each pass changes orbit energy via gravity assist
- Final pass captures into target orbit
- Belbruno-Miller WSB transfer
- Implementation needs careful BCP DC + multi-shooting

## Concrete first experiment to run

Create `scripts/ch1_wsb_tier0.py`:
1. Loop over 10 (LEO, LMO) bank transfers with current mass ∈ [300, 700] kg
2. For each:
   - For TOF in {60, 80, 100, 120} days:
     - For dv0_scale in {0.95, 0.97, 0.99, 1.0, 1.01, 1.03}:
       - For dv0_tilt in {0, ±5°, ±10°} (off-prograde):
         - Propagate BCP for TOF, find ALL perilune passes
         - At each pass, try solve_arrival_eccentric
3. If any candidate beats current bank by 100+ kg, it's evidence
   that WSB physics improves this pair

Per-pair compute: ~4 (TOF) × 6 (scale) × 5 (tilt) × scan = 120 BCP
propagations × 120 days, each ~10s heyoka = 20 min per pair.

## Risk and abandonment criteria

- **If Tier 0 shows ZERO improvement on any pair**: BCP dynamics in
  this problem instance don't support ballistic capture (would be
  surprising; would invalidate the leaderboard hypothesis). Pivot to
  alternative architectures (e.g., full NLP with pygmo BiteOpt).
- **If Tier 1 manifold DC doesn't converge in <10 hr/pair**: WSB
  is too compute-heavy for the scale we need (200+ pairs). Submit
  current bank.

## Cross-references
- A-2026-05-27 — the audit that motivated this pivot
- S-2026-05-27 — bugfix attempts session
- C-022 — the BCP-apogee 3-impulse architecture (current production)
- Belbruno & Miller 1993 — original WSB paper for Hiten mission
- Koon-Lo-Marsden-Ross — *Dynamical Systems, the Three-Body Problem and
  Space Mission Design*, the textbook reference for manifold methods
- Topputo 2013 — *Optimal control techniques for low-energy
  Earth-to-Moon transfers*
