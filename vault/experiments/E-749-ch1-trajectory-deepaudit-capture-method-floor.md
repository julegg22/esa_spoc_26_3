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

## Further exploration paths (3 ranked by information gain)
1. **Capture-ΔV-vs-TOF map on 5 circular pairs (cheapest, ~1–2 h).** Violates "single-impulse short-TOF is the
   only capture." For 5 circular pairs (eL<0.05, DV2~1139) sweep capture TOF 2→80 d under the bicircular
   propagator (reuse E-036 WSB + a 2–3-impulse bi-elliptic variant), record min DV2(TOF). **Binary:** any point
   with DV2<700 at TOF<60 d ⇒ method lever OPEN (rank-2 path); DV2 stuck ~1139 ∀TOF ⇒ genuinely floored.
2. **Sun-assisted capture-phase scan (cheap-medium).** Violates "capture epoch/phase is fixed by the row." The
   dynamics ARE bicircular (Sun-perturbed); scan arrival phase for 5 circular pairs at TOF 20–60 d for
   Sun-perturbation-assisted low-energy windows. **Binary:** any phase with DV2<700 ⇒ free epoch DOF we never
   exploited; else no.
3. **Targeted WSB on high-cld transfers only (medium).** Violates "WSB's TOF penalty kills it everywhere." Land
   the E-036 WSB only on the subset where cap@dt=100 still exceeds the cheap WSB rocket_mass. **Binary:** that
   subset nets positive ⇒ partial WSB lever (+X kg, a down-payment toward rank-3); else WSB dominated.

## Bank impact
None (diagnostic). Bank unchanged at 364,932 (held). Per §5b, taking experiment #1 now.
