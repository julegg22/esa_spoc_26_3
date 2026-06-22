---
id: E-602
type: experiment
corrected_by: [E-700, E-697]
tags: [experiment, ch1, trajectory, assumption-audit, gap-anatomy, wsb, lunar-capture, evaluator-metric, reframed]
date: 2026-06-13
status: DIAGNOSTIC (no bank change) — the Ch1-trajectory "no further gains expected" verdict is exhaustion WITHIN the impulsive patched-conic architecture, not exhaustion of the problem. Measured the gap to the leaders and isolated the lever: lunar CAPTURE Δv into low-eccentricity Moon orbits (corr(dv,eL)=−0.71), addressed by WSB/Sun-assisted ballistic capture — NOT plane change (cheap) and NOT the matching (near-optimal).
instance: ch1 trajectory (ltl, BCP-propagated official fitness)
scripts: scripts/ch1_e600_idd_lever_probe.py, scripts/ch1_e601_gap_anatomy.py, scripts/ch1_e602_rematch_probe.py
related: [[ch1-coherent-model-r3]], [[ch1-trajectory-mass-lever-exhausted]], [[ch1-iL-matching-breakthrough]], [[ch1-lambert-dc-solver]], [[E-036-ch1-wsb-ballistic-capture-prototype]], [[ch1-raan-feasibility-refuted]]
---

> ⚠️ **REFRAMED 2026-06-22 by E-700 / E-697** (interpretation wrong, measurements right). Two claims
> here are corrected: (1) *"lunar CAPTURE Δv … corr(dv,eL)=−0.71 ⇒ WSB is the lever"* — the
> correlation is real but a **symptom, not the cause**; the true driver is **departure energy** (ΔV0,
> Earth-orbit apogee; E-619/E-700) and ultimately **per-pair solver capability**, not capture physics.
> (2) *"the matching is near-optimal (A2 closed)"* — judged on the **inclination proxy**, which is
> uncorrelated with true circular-capture ΔV, so it does **not** bind. The gap-anatomy *numbers* are
> sound; the WSB-lever and matching-closed *interpretations* are retracted. → see E-700, E-697.

# E-602 — Ch1 trajectory: assumption audit + gap anatomy (user-requested deep exploration)

## Mandate
User (2026-06-13): treat "better solutions are known to exist per leaderboard"
as ground truth; "no further gains expected" is a FALSE conclusion — find the
FLAW in our reasoning, not optimize further. 4-phase audit.

## Ground truth re-read (official validator, reference/spoc4_udp/trajectory-matching.py)
Decision vector = N×21 rows `[idE,idL,idD,t0,state(6),DV0(3),DV1(3),DV2(3),T1,T2]`.
Each row is propagated under FULL **bicircular (Sun-perturbed) dynamics** (`bcp_dyn`
includes a Sun term); only `(a,e,i)` matched at both ends (RAAN/argp/ν FREE).
Objective per transfer = `min(rocket_mass, (200−DT)·c_ld)` under a 3-D (Earth,
Moon, Destination) matching, each index used once; 400 of each.

## The five shared assumptions (Phase 1)
- **A1 (architecture):** transfers are impulsive patched-conic (Hohmann / 3-impulse
  apogee). All 7 solvers impose this. The validator does NOT.
- **A2 (per-pair + fixed matching):** each (e,m) solved in isolation then assigned.
- **A3 (idD/cap is a thin layer):** destination + `(200−DT)·c_ld` cap secondary.
- **A4 (99 empty = infeasible):** E-047 said so, but tested only impulsive + raan.
- **A5 (Δv-minimized ⇒ pair exhausted):** true only inside A1.

## Measured gap anatomy (Phase 2) — 3 cheap arithmetic probes, bank reconstructs to 236,420.5 exactly
**A3 FALSIFIED as a lever (E-600):** only 10/301 transfers capacity-bound;
re-optimizing all destinations gains **+311 kg (0.13%)**. Banked ≈ uncapped
rocket-mass (236,732). Objective IS trajectory Δv; E-049 measured the right metric
inside A1. idD layer is ~closed.

**Gap is Δv-level, concentrated in inclination AND capture (E-601/602):**
bank 236,732 kg / 301 pairs / avg 786 kg / avg Δv **4346 m/s** (ABOVE the 3940
impulsive Hohmann floor). Leaders' implied ~3320 m/s → 1183 kg/pair × 400 = **473k
≈ R3**. Fill-99-empty at current avg → +78k → 315k.

| iE band | filled | avg Δv | avg mass | unused |
|---|---|---|---|---|
| 0–10° | 73/76 | 3759 | 1083 | 3 |
| 10–40° | 125/131 | 4274 | 820 | 6 |
| 40–70° | 48/73 | 4802 | 553 | 25 |
| 70–200° | 55/120 | 4890 | 520 | **65** |

**A2 FALSIFIED as a lever (E-602):** current matching mean |iE−iL|=15.1° vs optimal
13.5° (only 1.6° on the table). **65/65 stranded high-incl Earth orbits have a
Moon orbit within 0.2° inclination** — the 99 empty slots are NOT plane-change-
incompatible. Re-matching is closed.

**★ The decisive finding (E-602B) — the cost is intrinsic to the impulsive
architecture, and it is lunar CAPTURE not plane change:**
- Plane change at lunar-dist apogee is cheap: v_apo≈193 m/s ⇒ dv_pc(90°)≈272 m/s.
- Strongest dv driver = **Moon eccentricity: corr(dv, eL) = −0.71** (low-eL/circular
  Moon orbits are EXPENSIVE to capture into; eccentric ⇒ arrive at apolune cheaply).
- **Smoking gun:** the 131 near-coplanar pairs (|iE−iL|<5°) STILL average **dv=4927
  m/s** — above the fleet mean, ~1600 m/s over the leaders' 3320. With nothing to
  plane-change and an optimal matching, dv is still far above the floor.

## Verdict (Phase 3 paradigm inventory + the flaw)
"No further gains expected" conflates **exhaustion within the impulsive
architecture (A1)** with exhaustion of the problem. Every saturated/ceiling/
exhausted verdict (E-049, E-047, the 371k impulsive ceiling) is conditional on A1,
which the BCP-propagated validator never imposes. The leaders' sub-floor Δv is a
PROOF the achievable region extends past A1 — they pay lunar capture (and some
plane change) with the Sun's gravity, not propellant. The one architecture-
breaking branch — **WSB / Sun-assisted ballistic capture (E-036, +17% on n=1)** —
was greenlit then reclassified "multi-week/deferred"; the loop then stopped pushing
Ch1 trajectory entirely. That EV-misclassification is the reasoning error.
Untouched paradigms that DON'T survive Phase-1 scrutiny: WSB at fleet scale;
template-free direct BCP transcription (CMA/collocation on the raw 15-DOF validator
interface). The matching MIP and idD layers ARE closed.

## Phase 4 — 3 assumption-falsifying experiments (ranked by information gain)
1. **WSB fleet-scale Δv probe (violates A1).** Run the E-036 ballistic-capture
   solver under official BCP fitness on ~30 pairs STRATIFIED BY eL (prioritize
   low-eL/circular Moon orbits — the real lever per E-602B), including filled-
   expensive and unused high-incl pairs. Measure realized capture Δv vs the
   impulsive baseline + the 3940 floor. Decides whether the impulsive-ceiling
   narrative is the flaw. **Heyoka-heavy — queued for when Ch2-large frees cores.**
2. **Plane-change-aware re-matching (violates A2).** DONE this experiment — REFUTED
   (matching near-optimal, 1.6°; stranded slots inclination-compatible).
3. **Template-free direct BCP optimization on ONE hard (low-eL) pair (violates
   A1+A5).** Global optimizer (CMA-ES/pygmo) on the raw 15-DOF validator interface,
   no Hohmann/apogee template, scored directly by `fitness`. Measures the true
   achievable Δv floor when our parametrization is removed.

## Caveats / honesty
- No bank change (diagnostic). Probes are pure arithmetic on the bank + orbit/LTL
  tables — no BCP propagation, so they bound the gap STRUCTURE, not a realized
  candidate. Building the actual WSB fleet is experiment 1 (queued).
- corr(dv, eL)=−0.71 is on the SELECTED 301 bank pairs (biased toward cheap picks);
  the eL→capture-cost mechanism is physically expected but experiment 1 must
  confirm WSB actually realizes the saving under the official validator.
- This reframes [[ch1-trajectory-mass-lever-exhausted]]: the IMPULSIVE per-pair
  polish is exhausted (correct), but that ≠ Ch1-trajectory exhausted.
