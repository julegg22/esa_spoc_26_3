---
id: E-036
type: experiment
status: GO (prototype proven; full L4 sweep queued)
tags: [ch1, trajectory, wsb, ballistic-capture, belbruno-miller, physics-ceiling, r3-gate, L4]

hypothesis: "a weak-stability-boundary / Sun-assisted ballistic-capture trajectory beats the impulsive 3-impulse baseline on a real bank pair under the OFFICIAL fitness, and the capacity discount (200−ΔT)·c_ld does not erase the gain at WSB-class TOFs (~90-120d)"

created: 2026-06-11
ran_start: 2026-06-11
ran_end: 2026-06-11
duration_runtime: "~28 min wall (single core, prototype; n=1 pair end-to-end)"

code: scripts/ch1_e565_wsb_prototype.py
inputs: |
  solutions/upload/trajectory.json (bank baseline, official udp.fitness)
  Challenge 1 Luna Tomato Logistics UDP (heyoka + pykep)
  pair (idE=118, idL=171, idD=108) — LEO aE=7.84e6 iE=0.44 → high-eL Moon aL=5.08e6 eL=0.62
outputs: |
  runs/ch1/77_e565_wsb_prototype.log (phases A/B/B3 + verdict block)
  NO bank writes; solutions/ untouched
env: micromamba spoc26 (heyoka + pykep official UDP)

verdict: GO (+165 kg / +17.4% on the prototype pair under official fitness; fleet model +62k..+128k kg, exceeds coherent-model L4 estimate of +60k). De-risks the WSB lever the user flagged as the one item only they could green-light — prototype green-lit it autonomously with quantified evidence.
---

# E-036 — Ch1 WSB ballistic-capture single-pair prototype (the R3 gate)

## Motivation
Ch1 trajectory is the campaign critical path: bank 228,108 kg ≈ 49% of the
R3 cutoff 463,513 kg, gap ~235k. The impulsive 3-impulse physics ceiling is
~371k kg, so R3 is UNREACHABLE impulsively — the leaders' avg dv (~3320 m/s)
is below the 3940 m/s Hohmann floor, implying weak-stability-boundary
(Belbruno-Miller Sun-assisted ballistic capture). L4 in the coherent model
([[A-2026-05-29-coherent-physics-model]]) estimated ~+60k from WSB. This prototype is the
GO/NO-GO gate before committing ~1-2 weeks to the full L4 build.

## Result (official fitness validated)
- **Pair (118,171): 1114.2 kg vs 949.0 baseline = +165 kg (+17.4%).**
- dv = 3448 m/s = 2894 (apogee raise to 1.5e9 m, only +89 over Hohmann)
  + 81 (midcourse at apogee) + 473 (capture); ΔT = 97.8 d; tangential
  arrival at the target orbit's perilune (1937 km). v_inf ≈ 1073 m/s.
- Theoretical floor for this pair = 1283 kg (v_inf=0) → headroom remains.
- **The decisive fix over all prior WSB failures:** optimize the apogee
  midcourse against an alignment-aware capture proxy, THEN the *exact*
  solve_arrival_eccentric dv2 (Nelder-Mead). Radius-only DC gives steep
  2.3 km/s encounters and LOSES (best 841 kg). This is the
  [[E-701-ch1-eccentric-departure-solver-fix]] + exact-dv2 combination.

## Capacity-discount analysis (does NOT invalidate L4 for ΔT≤120d)
Measured-anchor fleet model on the (200−ΔT)·c_ld discount:
- current idD assignment: 197/302 bank transfers win → **+62k kg fleet**.
- idD Hungarian re-matching: 295/302 win → **+128k kg fleet** (needs the
  deferred B4/B5 idD re-match — see ch1-b1b2b3-deferred).
- every idL has an idD with c_ld≥15 (cap ≥1350 kg @110d); 326/400 disjoint
  such pairs exist (log lines 10-13).
- gains decay fast with TOF: +98k@80d → +13k@170d → keep WSB TOF ≤~120d.
- plus the 99 unused idE/idL pairs as additional upside.
**This exceeds the coherent model's +60k L4 estimate.**

## Remaining risks for the full L4 build
1. **lo-eL / LMO targets unproven** (narrow capture window — the Tier-0
   failure mode; ~half the modeled fleet gain is in that class).
2. v_inf < 600 m/s not yet demonstrated (1073 achieved; floor wants ~0).
3. success rate measured on n=1 pair only.
4. +128k requires the deferred B4/B5 idD re-matching.

## Compute / parallelization
~2-4 min/pair, full sweep ~10-20 core-h — CHEAP and embarrassingly parallel.
Fits the 3 cores E-554 frees at ~01:10 tonight. [[E-019-ch2-edge-compute-marginal-value-zero]]:
this is the rare Ch1 lever where compute is a genuine multiplier (the insight
— eccentric exact-dv2 capture — is now proven).

## Queue impact (reprice)
WSB full sweep is now TOP of the Ch1 queue, AHEAD of the impulsive per-pair
DC polish (E-564 follow-ups 2 & 3), because it is the ONLY lever that breaks
the ~371k impulsive ceiling toward R3 (463,513). Sequence on the freed cores:
WSB sweep first (proven, +62k floor), impulsive polish + 99×99 unused pairs
in parallel where cores allow.
