---
id: E-604
type: experiment
corrected_by: [E-700, E-697]
tags: [experiment, ch1, trajectory, wsb, ballistic-capture, eL-stratified, fleet-lever, assumption-falsification, refutation, narrowed]
date: 2026-06-13
status: REFUTES the E-602 low-eL WSB lever (no bank change). WSB ballistic capture does NOT close the low-eL/circular-Moon-orbit gap: 14/16 LOW-eL pairs FAIL_no_valid_capture (the eccentric capture window [a(1−e),a(1+e)] of a near-circular orbit is too narrow for bound returns to thread), and the 2 successes are a wash (median LOW Δmass −46 kg). WSB only wins on HIGH-eL pairs (9/9 capture) and there only on the subset whose impulsive baseline was already poor (5/9, median +154 kg). Realistic fleet upside ≈ +15–25 k kg, confined to already-cheap high-eL targets — NOT the +62–128 k kg that motivated the probe. The Ch1 R3 "WSB fleet-scale" lever (E-602's reopened question) is therefore largely CLOSED; the residual is a small, low-priority guarded-bank opportunity, not a multi-day build.
instance: Ch1 trajectory (hard ×16/9), official BCP LtlTrajectory.fitness
scripts: scripts/ch1_e603_wsb_eL_probe.py (probe; results /tmp/ch1_e603_results.json — 25 pairs, /tmp only, nothing banked)
related: [[E-602-ch1-trajectory-gap-anatomy]], [[E-049-ch1-trajectory-filled-pair-dof-exhausted]], [[A-2026-05-29-coherent-physics-model]], ch1-b1b2b3-deferred, [[M-general-deep-single-prompt-audit]], [[M-general-deep-single-prompt-audit]]
---

> ⚠️ **NARROWED 2026-06-22 by E-700 / E-697.** This correctly refutes **one specific pipeline**
> (apogee-midcourse *eccentric-window ballistic capture* forced onto near-circular targets — that
> window is genuinely too narrow). But the conclusion *"the circular-capture fleet lever is largely
> CLOSED"* over-generalized from that one pipeline to the whole lever. The circular-capture lever is
> **real and ≈+117k** — a global smooth-penalty search (E-697) finds feasible sub-bank circular
> captures; the realization is a *solver-capability* matter (basin-overarching global search), not the
> ballistic-capture pipeline this probe tested. The per-pipeline falsification stands; the
> lever-is-closed extrapolation is retracted. → see E-700, E-697.

# E-604 — Ch1 trajectory: WSB capture cost, eL-stratified (falsifies E-602's lever)

## Mandate
E-602 (deep single-prompt audit of Ch1 trajectory) reopened the instance: it
localized the residual cost to **lunar capture, not plane change** (corr(dv,eL)
= −0.71) and named **eL-stratified WSB ballistic capture** as the open R3 fleet
lever, estimated +62–128 k kg. This probe TESTS that hypothesis on the banked
fleet — the decisive falsification experiment, not a build.

## Design
25 FILLED bank pairs, eL-stratified. WSB pipeline reused verbatim from the
banked prototype (`ch1_e565_wsb_prototype.py`: apogee-midcourse + eccentric
arrival dv2, Phase B3); each candidate scored under official
`LtlTrajectory.fitness`. Impulsive baseline recomputed per pair from its banked
vector. **Control pair (118,171) reproduced the bank solution to ~1e-10 kg** —
the generalized pipeline is correct. Nothing written to bank/upload/git.

Catalog is 250 LOW (eL<0.2, actually collapses to eL∈[0.0,0.021] — circular)
+ 150 HIGH (eL≥0.5, here [0.598,0.645]) + **zero MID by construction**, so the
LOW sample IS the high-value unproven circular-orbit class E-602 flagged.

## Result (measured on /tmp/ch1_e603_results.json, 25 pairs)
| Band (eL) | n | WSB capture rate | med dv_imp | med Δmass (WSB−imp) | pairs Δmass>0 |
|---|---|---|---|---|---|
| **LOW** (≈circular, eL≤0.021) | 16 | **2/16 (12.5%)** | 5007 m/s | **−46 kg** | 1/2 (+10 kg) |
| **HIGH** (eL≈0.6) | 9 | **9/9 (100%)** | 3774 m/s | **+154 kg** | 5/9 |

Status breakdown (raw): LOW = {FAIL_no_valid_capture: 14, SUCCESS: 2};
HIGH = {SUCCESS: 9}. Hohmann floor 3940 m/s: LOW sits *above* it (capture is
the cost), HIGH *below* it.

## The flaw in E-602's lever (Phase-1 self-correction, now measured)
**The predicted prime class is exactly where WSB FAILS.** 14/16 LOW pairs had
bound lunar returns (median **114** per pair) but **none landed inside the
narrow eccentric capture window `[a(1−e), a(1+e)]`** of a near-circular Moon
orbit. The 2 LOW successes paid a costly insertion (median dv2 ≈ 2050 m/s) and
net to a wash (E182→L340 −101 kg, E46→L144 +10 kg). By contrast HIGH captures
are cheap (median dv2 ≈ 473 m/s) — the **wide apolune window** is what makes WSB
work, and that is the opposite of where the gap lives.

**Where the HIGH wins come from (not eccentricity per se):** the 5 positive
HIGH pairs are precisely those whose *impulsive* baseline was already poor
(dv_imp 4172/2375/3899/4316/4158 m/s, at/above Hohmann): E262→L254 +707,
E49→L162 +326, E24→L250 +256, E57→L218 +165, E5→L192 +154 kg (Σ≈+1.6 t over 5).
HIGH pairs whose impulsive baseline was already excellent (1508–2171 m/s) all
LOSE to WSB (−396 to −821 kg). So WSB helps only where the *impulsive solver did
badly*, much of which an impulsive re-polish could also recover.

## Verdict / lever repricing
- **E-602's low-eL WSB lever: REFUTED.** The mechanism (ballistic capture into
  circular Moon orbits) is physically obstructed by the narrow capture window.
- **Residual WSB upside ≈ +15–25 k kg**, confined to high-eL pairs the impulsive
  solver left poor (and partly double-counting impulsive-polish-recoverable
  mass). On a 236,420 kg bank at rank 6 this is ~+0.7% — unlikely to move rank.
- **Do NOT fund a multi-day LOW-eL WSB sweep.** This was E-036 risk #1
  ("lo-eL/LMO capture window too narrow") — now confirmed by measurement.
- **Small open opportunity:** the 5 HIGH winners (+1.6 t) are real and recorded
  in /tmp/ch1_e603_results.json (full decision rows). A future *guarded* bank
  step can re-verify + bank them if the marginal mass is ever rank-relevant.
  Low priority — parked, not chased.

## Honesty / caveats
- Probe only, no bank change. Small samples (16 LOW / 9 HIGH); MID band
  physically absent from the catalog, so the eL→capture-cost curve is sampled at
  its two extremes only.
- Closes the *reopened* E-602 question with a measurement rather than an
  assumption — the deep-audit loop self-correcting: the lever named in Phase 3
  was falsified in execution, which is the expected and healthy outcome.
