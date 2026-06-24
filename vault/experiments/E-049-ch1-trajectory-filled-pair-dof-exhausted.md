---
id: E-049
type: experiment
tags: [experiment, ch1, trajectory, dof-reopt, mass-lever, apogee, exhausted]
date: 2026-06-13
status: EXHAUSTED — the 301 filled trajectory pairs are at their free-DoF (raan/argp/split/tof) mass optimum; independent 12-pair gate confirms prior apogee_polish + SADE polish. Trajectory rank gap closes only via the multi-week WSB / impulsive-perfection model, not per-pair polish.
instance: ch1-trajectory
script: scripts/ch1_e578_dof_reopt_gate.py (bg agent a10c1f95)
log: runs/ch1/84_e578_dof_gate.log
related: [[E-047-ch1-raan-argp-feasibility-refuted]], [[O-017-leaderboard-2026-06-13]], [[A-2026-05-29-coherent-physics-model]], [[C-005-differential-correction-shooting]]
---

# E-049 — Ch1 trajectory: per-pair free-DoF mass lever EXHAUSTED on filled pairs

## Context

E-047 refuted free-RAAN as a *feasibility* lever for the 99 empty slots but
established it as a ~60× *mass* lever. The untested orthogonal implication:
are the **301 already-filled** pairs each at their free-DoF-optimal mass, or
did the bank leave mass on the table? Bank = 236,420.5 kg.

## Method — 12-pair sample GATE (keep-best, never-loses)

`ch1_e578_dof_reopt_gate.py`: pick 12 filled pairs spanning Earth inclination
(iE 0.0°→89.4°, banked 223–1145 kg each), re-solve each with the faithful
apogee solver (`try_apogee_plane_change`) over a finer grid (RAAN_E=8,
ARGP_E=4, EA_DEP=8, EA_ARR=4, T0=2, T2_D=4 ≈ 1536 combos), 480 s/pair wall,
Pool(2). Keep-best vs bank per pair (re-opt can never lose). Gate: proceed to
full 301-pair re-opt only if extrapolated sample gain > 2%.

## Result — STOP (1.493% < 2% gate)

```
SAMPLE: bank=7967.4kg  keep-best=8086.3kg  gain=+118.9kg (1.493%)
VERDICT: STOP — bank is per-pair DoF-optimal, mass lever exhausted on filled pairs
```

Only **1 of 12** pairs improved (E140→L222 +118.9 kg). On **10 of 12** the
re-opt came in *below* the banked mass (bank kept) — i.e. the bank pairs
already carry more mass than this finer independent sweep finds. 1 pair
(E336→L66) failed to re-solve.

## Corroboration (git history)

- `e3fb9fd` apogee_polish FINAL: 129 improvements, **+23,139 kg** total — the
  per-pair free-DoF re-optimization was already run exhaustively (May 25–30).
- `32635e2` polish_to_theoretical: pygmo SADE (12-DoF) on the 176 highest-gap
  pairs → only **+14 kg**; "theoretical was over-optimistic."

Two independent prior passes + this fresh gate all agree: the filled pairs are
at their DoF optimum.

## Interpretation / EV

The single +118.9 kg real gain is **0.05% of the 236,420 kg bank** ⇒ zero rank
movement (trajectory is ~r10+; r5 worst shown −372,729 kg = a 136,000 kg / 58%
gap). A full 301-pair re-opt would capture ~1.5% (+3,500 kg) for **0 points**.
Not worth the multi-hour run.

**Trajectory rank headroom is architectural, not a polish:** closing it needs
the coherent impulsive-perfection (L1+L2) + WSB (L4) model ([[A-2026-05-29-coherent-physics-model]]),
a multi-week build. The patched-conic apogee architecture is saturated at
236,420 kg.

## Verdict

Ch1 trajectory mass-polish on filled pairs = **EXHAUSTED**. Combined with
matching-i/ii (E-048, open-source-solver exhausted) and the 99-slot
feasibility refutation (E-047), **all three Ch1 instances are now exhausted
under bounded autonomous methods**; their remaining headroom is either a
user license/$ decision (matching) or a multi-week physics model (trajectory).
