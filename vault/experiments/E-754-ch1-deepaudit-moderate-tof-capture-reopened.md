---
id: E-754
type: experiment
tags: [ch1, trajectory, deep-audit, capture, v-infinity, moderate-tof, closed-path-error, rank-3]
date: 2026-06-29
status: DONE — /deepaudit ch1 (user framing: competitors use STANDARD methods). FINDING: the ~1138 circular-capture floor is NOT physics - it is our FAST ARRIVAL (v_inf~1553). Moderate-TOF (30-60d) transfers arrive slow (v_inf~300) -> capture ~620 m/s (the standard periapsis floor), cargo cap does NOT bind at 50d -> +~60k kg toward rank-3/4. ERRONEOUSLY CLOSED by the PairUDP TOF cap (~43d) + a convergence-failed extended-TOF test (E-682).
corrects: [E-749, E-733]
reframes: [E-682]
related: ["[[E-749-ch1-trajectory-deepaudit-capture-method-floor]]", "[[E-682-ch1-circular-capture-probe]]", "[[ch1-trajectory-udp-floor-confirmed]]", "[[M-general-deep-single-prompt-audit]]"]
---
# E-754 — /deepaudit ch1: circular capture is FAST-ARRIVAL-bound, not floored. Moderate-TOF reopens ~+60k kg

User framing: **competitors use only STANDARD methods** → any gap = our bug / overlooked angle / wrongly-closed
path, NOT a research-grade competitor edge. This reframes the E-749 "circular capture impulsively-floored ~1080,
rank-3 research-grade" verdict as a **false conclusion to diagnose**.

## Phase 2 — measured on the banked artifact (decisive)
For the 250 circular Moon orbits (eL<0.05):
- **Our capture DV2: mean 1138 m/s.**
- **Standard single-impulse periapsis-insertion floor (v∞=0): mean 609 m/s** (`ΔV=√(v∞²+2μ/a)−√(μ/a)`, range 518-677).
- **The 529 m/s gap is ENTIRELY arrival speed:** back-solving our DV2 ⇒ **implied arrival v∞ ≈ 1553 m/s** — our
  transfers arrive FAST (short-TOF, mean 2.6d, max 35.6d).
- **Moderate-TOF arrival at v∞≈300 ⇒ DV2 ≈ 618 m/s** (essentially the floor).
- **Cargo cap @ dt=50d = mean 1891 kg — does NOT bind** (rank-1 needs 1220). So moderate-TOF delivers full mass.
- **Mass headroom: +59,621 kg → ~442,000 kg** (rank-4/approaching rank-3 at 472k), keeping dv0/dv1 fixed
  (conservative; the competitor's 1220/transfer proves the *total* ~3254 is reachable with standard methods).

## Verdict — the load-bearing flaw
The shared assumption across EVERY ch1-trajectory branch: **TOF is short (PairUDP cap T1≤30d/T2≤13d ≈ 43d)** ⇒
transfers arrive fast (high v∞) ⇒ capture is expensive. This was never violated, so the **v∞-vs-TOF tradeoff in the
moderate (30–60d) band was never measured.** The "1080 floor" (E-682/E-697/E-749) is real only *within the
short-TOF cap*. E-749's "long-TOF WSB is cargo-capped" was correct but mis-scoped: the lever is **MODERATE** TOF
(~50d), where the cargo cap is comfortably non-binding (1891 ≫ 1220). The one extended-TOF test (E-682) returned
`best_dv=1e6` = **convergence failure (cold-start), not a physics floor** — and we misread that bug as evidence
the lever was closed. **User's intuition vindicated: erroneously-closed path, standard method, ~+60k kg — the
single largest realizable ch1 lever, far above the matching gaps (+1k each) or the STM grind (+170).**

## Paradigm inventory
Lunar-transfer paradigms: (a) direct/Hohmann short-TOF — OURS, fast arrival; (b) **bi-elliptic / moderate-TOF
(30–60d), low v∞** — UNTOUCHED, excluded by the TOF cap + the E-682 convergence failure = THE LEVER; (c) WSB/3-body
long-TOF (~100d) — cargo-capped, correctly ruled out. (b) is standard astrodynamics, not research-grade.

## Further exploration paths (3 ranked by information gain)
1. **v∞-vs-TOF Lambert scan on 5 circular pairs (cheapest, pure physics, ~min).** Violates "short-TOF only."
   Scan transfer TOF 5→70d, compute arrival v∞ via Lambert to the Moon. BINARY: v∞ drops to <500 m/s at TOF
   30–60d ⇒ moderate-TOF cheap capture is REAL (the floor was fast-arrival); v∞ stays >1200 ∀TOF ⇒ geometry
   forbids it.
2. **Moderate-TOF per-pair re-solve, SEEDED (not cold-start) — the fix for E-682's bug.** Extend PairUDP T1→60d,
   seed from the #1 Lambert low-v∞ solution, DC/CMA refine, score official udp.fitness. BINARY: total ΔV drops
   toward ~3300 + mass rises at TOF<60d with cargo OK ⇒ +tens-of-k lever realized; no convergence ⇒ deeper issue.
3. **Full-fleet moderate-TOF re-solve** (if 1/2 confirm) → realize the +~60k toward rank-3.

## Bank impact
None (diagnostic). Bank 365,103 (rank 6). The cheapest step (#1 Lambert v∞ scan) is being taken now.
