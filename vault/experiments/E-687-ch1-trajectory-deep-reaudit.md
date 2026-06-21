---
id: E-687
type: experiment
tags: [experiment, ch1, trajectory, deep-audit, refutation, departure-energy, multiple-shooting, premise-reassessment]
date: 2026-06-21
status: DEEP RE-AUDIT (user override: "HRI used NO sophisticated physics; the gap is large so they use a STRUCTURALLY different approach; find the flaw in our reasoning"). Corrected the gap attribution from lunar-capture to EARTH-DEPARTURE ENERGY, then refuted FOUR successive per-pair conjectures. Net: per-pair trajectory is near OUR-tooling's floor; the 488k gap is NOT explained per-pair; premise reassessment OPEN.
instance: ch1 trajectory (ltl, BCP-propagated official fitness)
scripts: ch1_audit_measure.py, ch1_audit_apogee.py, ch1_2impulse_test.py, ch1_dv1_continuation.py, ch1_competent_resolve.py, ch1_nlp_pair.py, ch1_multishoot.py, ch1_circular_*.py
related: [[E-602-ch1-trajectory-gap-anatomy]], [[E-604-ch1-wsb-eL-stratified-fleet-probe]], [[E-605-ch1-trajectory-reaudit-parallel-bcp]], [[E-619-ch1-trajectory-global-search-gap-hypotheses]], [[ch1-trajectory-udp-floor-confirmed]], [[deep-single-prompt-audit]]
---

# E-687..691 — Ch1 trajectory: deep re-audit + four refuted per-pair conjectures

## Mandate (user, 2026-06-21)
"We are NOT done. The gap to leaders is LARGE → structurally different approach. HRI did NOT use
sophisticated research-level physics. 'No further gains expected' is FALSE; find the FLAW in our
reasoning or the missing direction. Previous conclusions may be wrong due to undiscovered mistakes."

## Ground truth (leaderboard-verified, fetch_leaderboards.py)
Ch1 Trajectory Matching: **R1 488,011** / R3 ~472k / R5 ~387k. Our bank **263,119** = **1.85×** gap.
Objective per transfer = min(rocket_mass(ΔV), (200−ΔT)·c_ld), 3-D matching (idE,idL,idD each ≤1×,
400 of each). Measured: **100% mass-bound** (cap never binds). So the gap is ΔV-driven.

## CORRECTED gap attribution (the one solid new finding)
- **ΔV is DEPARTURE-dominated:** ΔV₀ (departure burn) = **66%** of total, ΔV₀>ΔV₂ in **98%** of pairs.
- **ΔV₀ is set by Earth-orbit APOGEE: corr(ΔV₀, apogee) = −0.88.** All Earth orbits are LOW
  (apogee 0.017–0.112 of Moon distance); ~41 high-apogee orbits give cheap transfers (~2081 total),
  the other ~285 low-apogee give expensive (~4400).
- This CORRECTS E-602's "corr(dv,eL)=−0.71 ⇒ lunar capture is the lever" — that was a SYMPTOM
  (circular Moon orbits happen to pair with low-apogee Earth orbits), not the cause. E-619 had
  already found departure-dominance but closed it as "LEO-floored."
- Per-pair split: bank 2795(ΔV₀) + 620(ΔV₁ mid-burn) + 839(ΔV₂ capture). Leader-implied 3255 =
  2795 + 0 + ~460 IF the gap were per-pair (see refutations — it is NOT realizable).

## FOUR refuted per-pair conjectures (the core of this audit)
1. **"WSB / lunar-capture is the lever" (E-602/604 reopened).** REFUTED — the 250 circular Moon
   targets are DEEP low LLO (a/SOI = 0.029, ~190 km alt); Sun-assist is negligible that deep, so
   ballistic capture is physically blocked (E-604's "narrow window" was correct physics). The
   geometry check killed it before any WSB rebuild.
2. **"The cheap 2-body Lambert seed (~3900 vs bank ~6000) proves the bank's circular captures are
   SOLVER failures, +74k" (E-684).** REFUTED (E-685) — the Lambert targets a KEPLERIAN MOVING Moon
   while the BCP synodic frame FIXES the Moon at (1−μ); the two models diverge ~6509 km over a 50d
   arc. The cheap seed is a CROSS-MODEL ARTIFACT, not a BCP lower bound.
3. **"The mid-burn ΔV₁ (median 667 on 203/326 pairs) is waste; killing it → +86k" (arithmetic).**
   REFUTED (E-688 continuation: drive ΔV₁→0 from the feasible bank) — removing the mid-burn breaks
   LLO feasibility (the trajectory can't reach the orbit). The mid-burn is ESSENTIAL geometry.
4. **"Our solvers are weak; a competent per-pair NLP realizes the cheap floor; never built one"
   (E-687/689/690/691).** REFUTED — built a multiple-shooting NLP. The CONVERGENCE FIX WORKS
   (constraint 3.26→1e-4, 3 orders, where single-shooting failed cold), BUT no validated win: the
   multi-shoot's optimistic 3612 is a CONTINUITY ARTIFACT (below the 2-body floor 3987 = impossible);
   the physically-realizable single coast = 7018 (worse than bank 5392) because the BCP arrival isn't
   tangential; constrained dv-minimization can't reduce ΔV while holding the on-orbit constraint.

## The recurring wall (now characterized across ~8 methods)
2-body Lambert says cheap (~3700–4100) transfers EXIST, but EVERY BCP solver we own — Lambert+DC,
6-DOF DC, synodic DC, continuation, competent-local SLSQP, black-box SADE, multiple-shooting — fails
to REALIZE them: they either miss the LLO (feasibility) or land with a huge non-tangential insertion
burn. The cheap 2-body transfers sit at LONG tof (50d) where BCP perturbation wrecks the arrival.
Two independent tests (E-688, E-691) now say the bank's 3-impulse per-pair solutions are near OUR
tooling's floor.

## Verdict + new concepts for the vault
- **Per-pair trajectory optimization is NOT the +172k lever** (high confidence after this battery).
  The bank's 3-impulse mid-burn solutions are good; clean 2-impulse is worse; the cheap 2-body
  numbers are model artifacts.
- **NEW CONCEPT — model-frame consistency trap:** 2-body Lambert (Keplerian moving Moon) and the
  BCP synodic frame (fixed Moon) diverge ~O(100 km/day); any cross-model lower bound is invalid for
  this problem. Validate ONLY under the official BCP fitness.
- **NEW CONCEPT — continuity-artifact trap in multiple-shooting:** a converged-but-loose (1e-4)
  multiple-shooting solution reports an objective for a NON-PHYSICAL jumpy path; always check the
  realized single-coast value, and flag any ΔV below the 2-body floor as an artifact.
- **NEW CONCEPT — positive-control floor failure (recurring):** every "per-pair exhausted" verdict
  (E-049, E-619, and four of ours) used a WEAK solver's inability-to-improve as the physics floor.
  We finally built a competent solver (multiple-shooting) — and it AGREES the bank is near-floor.
- **OPEN (premise reassessment, user-chosen next step):** if the gap is not per-pair, WHERE is it?
  Candidates not yet falsified: (a) the 3-D ASSIGNMENT on a true ΔV-cost matrix (NEVER built — all
  prior matching solvers used the SEPARATE matching-i/ii instances or partial caches); (b) FILLING
  all 400 slots (we fly 326; the 74 unused are circular Moon × low-apogee Earth); (c) a structurally
  different solution we have not conceived. Re-derive the leader's structure from first principles.

## Honesty / caveats
- No bank change. The convergence fix is real but unmonetized. The "departure-dominated, apogee-driven"
  finding is solid and reframes the whole problem. The per-pair-floor conclusion rests on ~8 solver
  methods all agreeing — strong but not a proof; a genuinely better optimizer could still surprise.
