---
id: E-749
type: experiment
tags: [ch1, trajectory, deep-audit, capture, dv2, wsb, multi-impulse, rank-2, lever]
date: 2026-06-28
status: DONE — /deepaudit ch1-trajectory; the residual ~118k-kg gap is CIRCULAR-ORBIT CAPTURE, floored by our single-impulse METHOD (not physics, not matching)
reframes: [E-733, E-602]
corrects: "E-733 'capture is PHYSICS-floored (circular Moon orbits)' + 'one expensive JOINT-matching lever open' — both refuted below"
related: ["[[M-general-deep-single-prompt-audit]]", "[[E-733-ch1-trajectory-deepaudit-capture-floor]]", "[[E-036-ch1-wsb-ballistic-capture-prototype]]", "[[E-701-ch1-eccentric-departure-solver-fix]]", "[[ch1-trajectory-udp-floor-confirmed]]", "[[C-023-wsb-low-energy-transfers]]"]
---
# E-749 — /deepaudit ch1-trajectory: the gap is circular-orbit capture, floored by our METHOD

**Y = 364,932 kg (rank 6).** X: rank-5 **372,729** (+7,797), rank-3 ~472k, rank-1 **488,011** (+123k). Standing
verdict (E-733): "per-pair tooling near-floor; one expensive JOINT-matching lever open; capture PHYSICS-floored
for circular Moon orbits." This audit **refutes all three** with measurement on the banked artifact.

## Phase 2 — measured (faithful: official `min(rocket_mass, (200−dt)·cld)`, round-trips exact)
- **Per-transfer ΔV 3835 m/s: DV0 dep 2761 (p10 2462/p90 3063) + DV1 90 + DV2 capture 984 (median 1097).**
- **Competitor edge is 100% capture.** rank-1 mass 1220/transfer ⇒ implied total ΔV 3254 m/s. Departure is
  floored at ~2761 **for both** (E-701 fixed it) ⇒ their entire 581 m/s edge is DV2: **their ~490 vs our 984.**
- **Matching can't help — idE, idL, idD are FORCED PERMUTATIONS** (400 distinct each; assigned-idL eL = pool eL
  = 0.233). We MUST capture all **250 circular Moon orbits** (eL<0.05) — captured at **1139 m/s**; the 150
  eccentric ones at 727. corr(DV2,eL) = −0.71. → **E-733's "JOINT-matching lever" REFUTED** (a permutation cannot
  dodge the circular orbits; DV2≈f(eL_idL) so total is ~assignment-invariant).
- **DV-bound, not cargo-capped.** delivered/rocket_mass = 0.949 (38/400 cap-bound); cld mean 12.6 ⇒ cap mean 2481
  ≫ delivered 956; **ceiling if DV→0 at current short TOF = 853k kg.** So ΔV is the only binding constraint.
- **The prize: if DV2 → 490 at current TOF → 483,143 kg (+118,210) ≈ rank-2.**
- **Self-correction (cargo-cap math):** WSB at full ~100 d TOF is a **wash** — `(200−dt)` halves the cap to ~1261,
  so cheap-but-slow capture nets 359,897 kg (≤ bank). The lever is therefore cheap capture at **short–moderate
  TOF** (cap@dt=50 ≈ 1891 ≫ the 1220/transfer rank-1 needs), NOT long-TOF WSB across the board.

## Verdict
The "capture is **physics**-floored for circular orbits" claim (E-733's own self-correction) is **false** — it is a
**METHOD** floor of our single-impulse patched-conic / eccentric-backshoot tooling. Evidence: the competitor
delivers 1220 kg/transfer (circular DV2 ~490) at short TOF, and **42 of our own transfers already capture <500
m/s** — cheap capture is demonstrably achievable on *this* problem. The flaw shape is textbook
**exhausted-within-(our capture method)**, not of the problem. Matching is a red herring (forced permutation). The
single load-bearing lever: **a capture scheme that reduces circular-orbit DV2 from ~1139 to ~490 at affordable
(short–moderate) TOF** — worth **+118k kg ⇒ rank-2**, the largest single lever in the whole campaign.

## Prior method attempts ALL failed — but on CONVERGENCE, not physics (the decisive clue)
Cheap circular capture has been attacked ~4 ways and every one failed: WSB ballistic (E-604, refuted for
circular — one pipeline), perilune-targeting (E-694, **"NO-PERI" = no feasible capture found**), extended-TOF
global search (E-682, **best_dv = 1,000,000 / dt = nan = did not converge**), eccentric-backshoot (E-697/738,
works for *eccentric*, floors circular at 1139). **All four failures are convergence-shaped** (1e6 / NO-PERI /
nan), not physics-shaped (no run *proved* a high floor — they failed to *find* a solution). Combined with the
competitor's 1220 kg/transfer and our own 42 transfers <500, this is the campaign's signature pattern: a
**cold-start feasibility/convergence wall on the razor-thin circular-LLO target**, the same class as the E-701
eccentric-departure bug — not a real floor.

## Further exploration paths (3 ranked by information gain)
1. **CONTINUATION / homotopy from a working eccentric capture to circular (cheapest, ~2–3 h; the refined #1).**
   Violates the shared "cold-start the circular solve" assumption that defeated E-682/E-694. The 150 eccentric
   orbits capture cheaply and converge; the 250 circular ones cold-start-fail. Take a *converged* cheap eccentric
   capture and **homotope eL→0** (and a→target) in small steps, re-converging the DC/shooter each step, tracking
   the solution onto the circular target. **Binary:** if the path tracks to eL<0.05 with DV2<700 ⇒ the floor was
   cold-start convergence (lever OPEN, +118k/rank-2 realizable); if the branch *physically* turns back / DV2
   blows up as eL→0 ⇒ circular capture is genuinely energy-floored for impulsive schemes (lever closed, WSB-class
   long-TOF is the only door and it's cap-penalised).
2. **Sun-assisted capture-phase scan (cheap-medium).** Violates "capture epoch/phase is fixed by the row." The
   dynamics ARE bicircular (Sun-perturbed); scan arrival phase for 5 circular pairs at TOF 20–60 d for
   Sun-perturbation-assisted low-energy windows. **Binary:** any phase with DV2<700 ⇒ free epoch DOF we never
   exploited; else no.
3. **Targeted WSB on high-cld transfers only (medium).** Violates "WSB's TOF penalty kills it everywhere." Land
   the E-036 WSB only on the subset where cap@dt=100 still exceeds the cheap WSB rocket_mass. **Binary:** that
   subset nets positive ⇒ partial WSB lever (+X kg, a down-payment toward rank-3); else WSB dominated.

## Probe #1 RESULT — homotopy REFUTES the cold-start hypothesis (partly self-correcting the audit)
Ran the continuation/homotopy on the 5 worst circular captures (`ch1_capture_homotopy.py`). **0/5 reached
DV2<700**, and the reductions were partial + inconsistent:
- (291,364) 1812 → **1080** (−732), (382,67) 1523 → 1185 (−338), (366,132) 1469 → 1409 (−60),
  (40,21) 1388 → **1657** (got *worse*), (144,48) **lost the branch** (f=1.3e4).
So cold-start convergence was only a *partial* wall — homotopy helps the worst outlier but **circular capture has a
genuine impulsive floor ~1080+**, far above the competitor's implied ~490. **The audit's own mechanism hypothesis
(#1) is largely refuted by its own probe.** The GAP localization (capture, +118k, forced permutation) stands; the
*realizability* does not: our impulsive/patched-conic tooling cannot reach the competitor floor by any convergence
trick. The ~490 must come from a **fundamentally different method — true low-energy / WSB ballistic capture** —
which has now failed **5×** (E-604/E-036/E-682/E-694 + this homotopy). (Caveat: the `valid_row` print was a check
bug — official_row returns a 2/3-tuple, not a 21-list — so the modest reductions *may* be officially valid; a
careful "apply homotopy to worst outliers, keep only validated improvements" pass could net a *small* gain, but it
is NOT the +118k rank-2 lever.)

## Verdict (final)
**Ch1 is effectively capped near rank-5 with our current capture tooling.** The +118k/rank-2 lever is real but
**research-grade**: it requires a working low-energy (WSB / Sun-assisted / 3-body-manifold) capture into circular
LLOs — the one paradigm we have never landed, and the competitor's near-certain method. The remaining near-term
ch1 gains are the bounded STM/eccentric polish (toward rank-5), not rank-2.

## Bank impact
None (diagnostic). Bank unchanged at 364,932 (held). Nothing submitted.
