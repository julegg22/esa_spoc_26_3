---
id: E-605
type: experiment
tags: [experiment, ch1, trajectory, assumption-audit, gap-anatomy, bcp, parallel-optimization, solver-architecture-flaw, refutes-own-prior]
date: 2026-06-13
status: DIAGNOSTIC (no bank change) — RE-AUDIT under new ground truth: Team HRI reached 463,513 kg (≈2× our 236,420) with HEAVY PARALLEL OPTIMIZATION, NOT WSB physics research nor a commercial solver. This FALSIFIES the E-602/E-604 chain ("we're at the impulsive floor → only WSB closes the gap → WSB refuted on low-eL → done"). Decisive measurement on the banked vector (pure arithmetic, exact reconstruction 236,420.5 kg): our median per-pair ΔV is 4333 m/s and 230/301 filled pairs are ABOVE the 3940 m/s "Hohmann floor" we declared exhausted; HRI's implied per-pair ΔV is ~2734 m/s (if 301 filled). The gap is ΔV the leaders extract by optimizing the TRUE BCP fitness directly with parallel global search — our patched-conic Lambert+DC solver structurally cannot represent Sun-assisted sub-Hohmann transfers, and our "exhausted" verdicts were measured against that weak solver's own floor (a positive-control failure).
instance: Ch1 trajectory (hard ×16/9), official BCP ltl.fitness (reference/spoc4_udp/trajectory-matching.py)
scripts: /tmp/ch1_e605_anatomy.py (pure-arithmetic per-pair decomposition; no heyoka, no search, no write)
related: [[E-602-ch1-trajectory-gap-anatomy]], [[E-604-ch1-wsb-eL-stratified-fleet-probe]], [[E-049-ch1-trajectory-filled-pair-dof-exhausted]], [[E-049-ch1-trajectory-filled-pair-dof-exhausted]], [[C-005-differential-correction-shooting]], [[A-2026-05-29-coherent-physics-model]], [[M-general-deep-single-prompt-audit]], [[O-014-2026-06-07-competitor-algorithm-inference]]
---

# E-605 — Ch1 trajectory RE-AUDIT (HRI = parallel compute, not physics research)

## New ground truth (user, 2026-06-13)
Solutions > 463,513 kg exist (Team HRI, rank 3 — verified live). HRI used
**neither a commercial solver nor multi-week research**; their strength is
**highly parallel, heavy-computation optimization algorithms.** ⇒ "no further
gains" is false; find the FLAW. This contradicts E-602/E-604, which concluded the
residual was intrinsic WSB capture physics (a multi-week lever) and then "refuted"
WSB on the low-eL class. If 2× is reachable by parallel search alone, that whole
chain is the flaw.

## The exact objective (re-read of the official validator)
Per pair: `mass = exp(-ΔV/311/G0)·5000 − 500` (Tsiolkovsky, cap 4500 kg at ΔV=0);
score += `min(mass, (200−DT)·c_ld)`. Decision vector = 400×21: per pair
`[idE,idL,idD,t0, r0(3),v0(3), ΔV0(3),ΔV1(3),ΔV2(3), T1,T2]` — **3 impulses + 2
free coast arcs**, propagated under **FULL bicircular (Sun-perturbed 3-body)**
heyoka dynamics (tol 1e-16). Only **(a,e,i) matched** at both ends ⇒ **RAAN, argp,
true-anomaly are FREE** at departure AND arrival. ΔV and DT are READABLE straight
from the vector (no propagation needed) ⇒ exact per-pair arithmetic.

## Decisive measurement (Phase 2 — /tmp/ch1_e605_anatomy.py, bank reconstructs to 236,420.5 exactly)
```
filled 301/400 (99 EMPTY) · avg 785.5 kg/pair · HRI 463,513 (≈1540/pair if 301 filled)
binding term: 291 MASS-bound / 10 TIME-bound  ⇒ the lever is ΔV (mass), not time
ΔV (m/s):  min 1430 · p25 3987 · med 4333 · p75 5170 · max 6991
   230/301 pairs ABOVE 3940 ("Hohmann floor")   ·   only 39/301 below leaders' 3320
mass/pair: med 708 · max 2628 (cap 4500) — huge headroom
loose ceiling (all pairs ΔV→0, time-capped) ≈ 712,000 kg
ΔV→mass: −1000 m/s ≈ +469/pair (+136k); −2000 m/s ≈ +1119/pair (+326k)
HRI 1540/pair ⇒ implied ΔV ≈ 2734 m/s  (≈ −1600 m/s vs our median)
```
**The entire 2× gap = ~1–1.6 km/s of per-pair ΔV (plus some of the 99 empty
slots).** No exotic objective, no time-term play (291/301 mass-bound), no
matching trick required.

## THE FLAW (Phase 1)
Every "exhausted" verdict shared an unstated representation assumption:

**A0 — the trajectory is solved by our patched-conic Lambert + 3-impulse DC
pipeline, and its ΔV floor IS the problem's floor.** Violating solution: a
trajectory optimized DIRECTLY against the heyoka BCP propagator, with long coast
arcs that let solar perturbation lower ΔV below the 2-body Hohmann floor, and with
RAAN/argp/ν chosen freely — i.e. exactly what HRI's parallel optimizer finds.

Consequences, each now measured:
1. **We are not even at the impulsive floor.** 230/301 pairs sit ABOVE 3940 m/s.
   E-049's "per-pair DoF exhausted" was a re-optimization by the SAME weak solver
   that failed to improve — a positive-control failure misread as a problem floor.
2. **The "3940 Hohmann floor → only WSB goes lower" claim is a 2-body artifact.**
   The validator never imposes patched-conic physics; the BCP dynamics give
   sub-Hohmann ΔV for free under direct optimization. WSB is one hand-derived
   instance of this; it is NOT the only way, and NOT required.
3. **E-604 "refuted WSB" against a straw man.** It compared ONE hand-crafted
   capture geometry (ch1_e565 prototype) to the bank's (bad, 4333 m/s) baseline on
   low-eL. It never tested "heavy parallel global optimization of the true
   fitness," which is the actual lever. E-604's low-eL capture-window failure is
   real for that prototype but does not bound what a BCP-native optimizer reaches.

## Paradigm inventory (Phase 3)
| Paradigm | Touched? | Survives Phase-1 scrutiny? |
|---|---|---|
| Patched-conic Lambert + DC per pair | YES (our whole pipeline) | NO — wrong physics; defines a false floor |
| Hand-derived WSB capture geometry | YES (E-036, E-604) | Partially — a single point, not the search |
| **Black-box global opt on TRUE BCP fitness (CMA-ES / DE / pagmo archipelago), per pair (21-dim) or jointly** | **NO** | **the untried lever; matches "HRI = heavy parallel optimization" exactly** |
| Direct/indirect optimal control on BCP (collocation, Pontryagin) | NO | open; heavier build, but exact ΔV-minimal |
| Joint matching+trajectory co-optimization (fill 99 empty) | NO (matching fixed by iL heuristic) | open; +value beyond per-pair ΔV |
| Free RAAN/argp/ν exploitation | NO (we fix orbital phase) | open; cheap extra DoF the validator allows |

## Plan (Phase 4 — 3 assumption-violating experiments, info-ranked, cheap first)
1. **★ Positive-control on ONE pair: parallel local+global opt of the 18 continuous
   DoF (t0,ΔV0..2,T1,T2) against the REAL `propagate`/`ltl.fitness`, seeded at a
   banked pair.** Violates A0 directly. Cheapest decisive falsifier: if a
   CMA-ES/DE run (or even scipy on the BCP propagator) drops a banked pair's ΔV
   meaningfully below its 4333-ish value, the "impulsive exhausted" verdict is
   dead and the lever is confirmed. Hours, 1–4 cores, /tmp only. **Run first.**
2. **Fleet-scale parallel BCP optimizer (pagmo archipelago / CMA-ES), per-pair,
   embarrassingly parallel across the 301 filled pairs**, warm-started from the
   bank, free RAAN/argp/ν, 2 coast arcs. This is literally HRI's described method.
   Guard-bank any pair that improves. Days of compute but trivially parallel; the
   highest-EV positive-point lever on the board if (1) confirms.
3. **Joint matching + trajectory fill of the 99 empty slots** under the BCP
   optimizer (the empty pairs our heuristic couldn't solve may be BCP-cheap).
   Adds count-value on top of per-pair ΔV; do after (1)/(2) prove the optimizer.

## Honesty / caveats
- Diagnostic only, no bank change. All numbers are exact arithmetic on the banked
  vector; the *reachable* ΔV floor is asserted from HRI's existence proof + BCP
  physics, not yet realized by us — experiment 1 is the falsifier.
- This SUPERSEDES the E-602/E-604 framing: the lever is not "WSB physics research"
  but "optimize the real BCP fitness with heavy parallel compute," which we never
  did because A0 hid it. WSB is a special case, not the gate.
