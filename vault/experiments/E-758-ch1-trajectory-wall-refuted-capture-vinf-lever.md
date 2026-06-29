# E-758 — Ch1 trajectory: "walled" REFUTED; the real lever is ARRIVAL V_INF (capture), +tens-of-thousands kg

**Date:** 2026-06-29
**Trigger:** user pushback — "I don't buy the wall; past walls were always a hard-coded assumption or
false conclusion. Reconsider every conclusion behind 'trajectory walled', attack the highest-uncertainty
one." Ground truth: competitors score better, so a lever exists.

corrects: [[E-757-ch1-moderate-tof-idd0-validation-bug]] (the "feasibility wall" sub-claim), [[ch1-moderate-tof-idd0-bug]]
relates: [[E-704-ch1-trajectory-assignment-rematch-refuted]], [[E-701-ch1-eccentric-departure-solver-fix]], [[E-749]]

## The chain of conclusions behind "trajectory walled @ 365,597 (r7)", attacked one by one
1. **"Moderate-TOF rows are officially infeasible (cold-start feasibility wall)"** — **FALSE.**
   `_validate_transfer` requires the forward-propagated end state to match the Moon orbit (a,e,i) to
   **1e-6**. Closure probe (`ch1_closure_residual_probe.py`) on the cached moderate rows: residuals are
   **1e-11 to 1e-14 on the Moon orbit, <1e-6 on Earth** — they CLOSE; they are **officially valid
   trajectories**. The v2 fleet's "0 valid wins" was NOT infeasibility — it sorted lowest-bank-mass
   (small-cld pairs that go cargo-limited at long dt), testing the wrong pairs. A false conclusion, as
   predicted.
2. **"The capture (moderate-TOF) lever helps"** — weak, and now explained: gap decomposition shows
   capture is only **26%** of ΔV; moderate-TOF buys a capture saving but RAISES departure more
   (headroom attack (180,27): valid but 717<869 — forcing tof=59d raised ΔV 3951→4310).
3. **"Departure is the gap"** — **NO, departure is FLOORED.** dv0 = **72%** of ΔV (mean 2823) and sits
   only **122 m/s mean** above the apogee-raise physical floor (324/400 within 100 m/s). Earth orbits
   run LEO(6545km)→GEO; the low ones force big departures = physics. E-704 correct here.

## Where the gap ACTUALLY is (gap decomposition on the banked artifact — cheap, no search)
- 400 transfers, 365,597 kg, mean ΔV 3919 (dv0 2823 / dv1 91 / dv2 1005).
- **Capture dv2 total 402,124 m/s vs v_inf=0 periapsis-floor 253,120 → 149,004 m/s "recoverable".**
- **Implied arrival v_inf: mean 1242 m/s** (max 2501). A min-energy (Hohmann-ish) lunar arrival is
  ~200–800 m/s. **We arrive FAST** → expensive capture.
- **Upper-bound mass upside if dv2 → v_inf=0 floor (departure held): +76,401 kg → 441,998.** v_inf=0 is
  unphysical (Moon moves ~1 km/s); realistic floor a few hundred m/s ⇒ true upside a large *fraction*
  of +76k (tens of thousands) — enough to move multiple ranks.

## The live lever (re-localized)
**Lower the arrival v_inf** (1242 → toward the transfer-achievable minimum) → cheaper capture → more
mass, WITHOUT the moderate-TOF departure penalty. Open question / highest uncertainty now: is v_inf=1242
a **basin miss** (cold-start CMA stuck in a fast-arrival basin → recoverable by better search at free /
intermediate TOF) or **BCP-coupled-optimal** (low v_inf genuinely costs departure, as the extreme
moderate-TOF showed)? The bank's short TOF (mean 11d) suggests a fast-arrival basin; an INTERMEDIATE-TOF
(15–30d) sweet spot between short (high v_inf) and forced-moderate (high departure) is **untested**.

## Decisive test (launched)
Re-solve the highest-v_inf transfers with the eccentric backward-shoot at **free TOF + heavy restarts**
(and an intermediate-TOF variant), minimize total ΔV, validate at the REAL idD (official udp.fitness<0),
compare mass to bank. **Binary:** total ΔV drops (mass up) → v_inf was a basin miss, lever REAL → scale
a fleet (potentially +tens-of-thousands → rank 6/5/…). No drop across restarts → v_inf is BCP-coupled,
capture genuinely floored-in-context.

## Status
"Trajectory walled" is **not established** — the feasibility sub-claim is refuted and the gap is
precisely localized to arrival v_inf (capture), quantified at up to +76k kg. Attack running.
