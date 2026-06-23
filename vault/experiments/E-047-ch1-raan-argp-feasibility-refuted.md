---
id: E-047
type: experiment
tags: [experiment, ch1, trajectory, raan-argp, free-dof, evaluator-audit, refuted]
date: 2026-06-13
status: REFUTED — free RAAN/argp does NOT unlock stranded high-incl Earth→Moon pairs; the 99 unfilled slots are assignment leftovers or genuinely infeasible, not raan-pinned
instance: trajectory (Ch1 hard)
script: scripts/ch1_e577_raan_verdict.py, scripts/ch1_e576_bank_inspect.py
log: runs/ch1/83_e577_raan_verdict.log, runs/ch1/82_e576_bank_inspect.log
related: [[E-039-ch1-matching-evaluator-audit]], [[M-general-foundation-then-search]], [[M-applying-methodology-triggers]], [[ch1-coherent-model-r3]]
---

# E-047 — Ch1 trajectory: free RAAN/argp feasibility lead REFUTED

## Lead (highest-EV on the board entering this session)

The official validator `_match_orbit` (ch1_trajectory.py:162) checks ONLY
(a,e,i); RAAN and argp of both the Earth-departure and Moon-arrival orbit
are FREE. Every solver was believed to hardcode raan=argp=0. The bank fills
~301/400 slots; the 99 unfilled are systematically high-incl Earth (unused
median i≈74° vs used ≈24°). Premise: sweeping the free RAAN/argp would flip
stranded high-incl pairs infeasible→feasible → fill up to 99 slots → a
trajectory rank step on the HARD problem (×1.78/rank).

## Why this took a self-validating harness (methodology)

Two earlier attempts gave a FALSE "REFUTED":
- **E-571** (raan-only sweep on 3 near-90° pairs): too weak, timed out after
  1 pair — INCONCLUSIVE, not a refutation.
- **E-572** (split=0.5 6-D DC, tof grid {6,9,13}d, max_nfev=40): "REFUTED
  0/8" — but **E-573 caught it failing its own positive control**: the
  harness returned FAIL on E0→L0, a coplanar banked pair worth 819 kg. A
  feasibility test yielding a NEGATIVE verdict MUST first reproduce known-
  POSITIVE cases, or the negative is a grid/budget artifact (audit-the-
  evaluator trigger). Root cause: bank tofs are CONTINUOUS (median 4.7d)
  and splits run 0.24–1.0 (many =1.0, single-burn-to-LOI) — the coarse
  grid + split=0.5 missed the feasible region entirely.

## The trustworthy test (E-576 + E-577, faithful apogee solver)

`src/esa_spoc_26/ch1_apogee_plane_change.py` is the bank's real architecture.

- **E-576 bank element recovery:** filled high-incl pairs DO store nonzero
  departure raan (E252 raan=270°, E100 raan=90°); low-incl E0/E69/E54 are
  raan=0. So whatever built the bank ALREADY un-pins raan where it fills —
  the lead's founding premise ("every solver hardcodes raan=0") is FALSE.
- **E-577 Phase A1 gate (full raan/argp sweep): 5/5** reproduced
  {E0,E69,E54,E252,E100} feasibly.
- **E-577 Phase A2 (raan=argp=0 ONLY): 5/5, FAILS=[]** — including the two
  high-incl pairs E252 (i=55.7°) and E100 (i=89.4°). ⟹ **RAAN is a MASS
  lever, not a feasibility lever** (E100: raan=90 →619 kg vs raan=0 →10 kg,
  ≈60×); pinning raan=0 reaches the SAME matches at lower mass.

This passing 5/5 positive control directly **refutes the parallel OLD-agent
verdict ("my tester fails its own positive control / E0→L0 = FAIL")** — that
agent's split=0.5 6-D DC was the weak tester; the apogee solver is correct.

## Phase B — decisive test on 6 stranded unfilled high-incl pairs

| pair | iE | baseline raan=0 | full sweep | classification |
|------|----|-----------------|-----------|----------------|
| E59→L4   | 69.6° | FAIL | FAIL | infeasible even with free DoF |
| E367→L5  | 74.2° | FAIL | FAIL | infeasible even with free DoF |
| E189→L99 | 55.4° | 1 kg | n/a  | baseline-feasible → ASSIGNMENT |
| E238→L141| 89.3° | 1 kg | n/a  | baseline-feasible → ASSIGNMENT |
| E321→L97 | 83.1° | 1 kg | n/a  | baseline-feasible → ASSIGNMENT |
| E352→L149| 78.5° | 1 kg | n/a  | baseline-feasible → ASSIGNMENT |

**0/6 unlocked by free raan.** 4 are already feasible at raan=0 (unfilled by
the 1:1 ASSIGNMENT/matching, not by infeasibility) but yield only ~1 kg each
vs 350–820 kg for typical bank pairs; 2 are genuinely unreachable even with
the full sweep.

## Verdict & consequences

**REFUTED.** The "free-RAAN sweep of 99 slots unlocks thousands of kg" lead
is dead as a feasibility play. The residual headroom is a tiny ASSIGNMENT
question (~1 kg/slot, ≤~99 kg total against a bank of hundreds of thousands
of kg) — negligible point-EV. **Do NOT pursue a raan-sweep re-solve.** The
real Ch1 trajectory rank gap is the coherent impulsive-perfection + WSB model
(see [[ch1-coherent-model-r3]]), a multi-week build, not free DoF.

Lesson reinforced: a NEGATIVE feasibility verdict is only trustworthy once
the harness reproduces known-POSITIVE controls — here it took three harness
iterations (E-571/E-572/E-574) before E-577's faithful apogee solver passed
5/5 and made Phase B's REFUTED trustworthy.
