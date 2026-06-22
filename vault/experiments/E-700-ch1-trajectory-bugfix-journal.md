---
id: E-700
type: experiment
status: JOURNAL — the bugs that produced false "exhausted/floored" verdicts on Ch1 trajectory, and
  their fixes. The cumulative effect was a basin-lock that masqueraded as a problem ceiling for ~13
  solver methods, until a global smooth-penalty search (E-697) broke it and proved sub-bank captures exist.
corrects: [E-602, E-604, E-619]
date: 2026-06-22
tags: [ch1, trajectory, bug-surfacing, basin-lock, penalty-landscape, retraction, journal]
related: [[M-general-basin-overarching-search]], [[M-general-retraction-annotation]],
  [[M-general-bug-surfacing-for-scientific-code]], [[E-697-ch1-trajectory-global-smooth-breakthrough]]
---
# E-700 — Ch1 trajectory: the bugs that hid the lever, and their fixes

## Why this journal exists
For weeks the Ch1-trajectory gap (bank 263k vs leaderboard 488k) was read as a problem ceiling:
"per-pair ΔV is floored," "WSB refuted," "matching near-optimal." Every one of those verdicts was
produced by a **buggy or under-powered solver**, not the problem. The user's standing suspicion
("there may be errors in the experiments") was correct: surfacing the bugs below, then replacing the
solver with a **global, basin-overarching search**, found feasible sub-bank circular captures —
proving the lever (≈+117k) is real. This journals each bug, its symptom, and the fix, so the failure
mode (a basin-lock dressed as a ceiling) is recognizable next time.

## The bugs (symptom → root cause → fix)

**B1 — Circular pairs were never optimized by a working solver.**
- *Symptom:* "per-pair floored for circular" (the expensive, high-value pairs).
- *Root cause:* `PairUDP.fitness` uses `solve_arrival_eccentric`, which fails on near-circular Moon
  orbits (narrow window). The CMA-ES archipelago that "confirmed the floor" had a `eL>=0.1` filter —
  it **never ran the circular pairs at all**. So the floor verdict rested on solvers that could not
  even evaluate the pairs in question.
- *Fix:* `PairUDPCirc` using `solve_arrival_dv` (radius-window aware, works for circular);
  positive-control validated (reproduces the bank's (241,50) to 6617.14). (E-695)

**B2..B5 — Penalty-landscape basin-lock (the big one).** A constrained global search anchored to the
bank because the *infeasible* region carried no usable gradient. Four distinct penalty-design bugs,
each independently re-creating the lock (`ch1_global_smooth.py` history):
- **B2 flat/constant infeasible penalty** → zero gradient off the feasible manifold; the optimizer
  can only sit on the seeded feasible point (the bank). *Fix:* smooth penalty = distance to the
  target manifold.
- **B3 impact penalized worse than a far-miss** → search pushed *away* from the Moon. *Fix:* score by
  the trajectory's **closest approach** (an impact = "too close" reads as almost-there).
- **B4 capped penalty gradient** → flat for distant trajectories → no pull-in from afar. *Fix:* uncap.
- **B5 free T1/T2 ≠ closest approach** → the guided quantity (endpoint) was not the one that needs to
  reach the orbit. *Fix:* perilune-targeting (propagate to the natural closest approach).
- *Combined fix result:* with a smooth, uncapped, closest-approach + plane-aware penalty and diverse
  (non-bank) init, CMA-ES found **sub-bank circular captures (~6199–6310 vs bank 6617)** — the first
  from-scratch feasible circular solver in the whole investigation. (E-697)

**B6 — H-010 under-determined backward-shooting residual.**
- *Symptom:* "backward shooting fails on circular."
- *Root cause:* `solve_transfer_back`'s residual matched only the Earth *radius* (1 equation, 5
  unknowns) → the backward trajectory hit the radius with arbitrary (often retrograde) e,i →
  `solve_departure_dv` then needed a huge ΔV0. My E-693 backward test used the **unfixed** version.
- *Fix:* match the full (a,e,i) via `state2earth` (H-010 fix). (E-696)

**B7 — Acceptance-window filter too tight.**
- *Symptom:* perilune solver reported "NO-PERI" (no feasible capture).
- *Root cause:* a hard `|r−a|<5 km` filter rejected valid captures that lie within the orbit's true
  eccentricity window (±~38 km for eL≈0.01); `solve_arrival_dv` would have accepted them.
- *Fix:* rely on `solve_arrival_dv`'s own window, not an ad-hoc 5 km gate.

**B8 — Search-vs-official precision mismatch.**
- *Symptom:* search finds feasible ΔV below the bank, but official validation rejects.
- *Root cause:* searching at heyoka tol 1e-12 vs the official 1e-16 → the trajectories diverge over a
  multi-day 3-body arc enough to miss the official 384 m / 1e-6 window.
- *Fix:* search fast (1e-12), then a final official-precision (1e-16) refinement; ~~open item: needs
  an STM corrector~~ → **CLOSED by B9 (E-701): the residual blocker was not precision at all.** The STM
  was built + validated (heyoka variational, machine-precision) and shelved — once B9 was fixed the
  eccentric majority validates from a km-scale window, no corrector needed.

**B9 — Circular-only Earth-side departure solver (the highest-impact bug; E-701).**
- *Symptom:* every *backward-shooting* official validation rejected, even when the search found
  sub-bank ΔV and the arrival was exact by construction. Misread as a *precision* gap (→ the STM
  detour).
- *Root cause:* `solve_departure_dv` builds a **circular** departure orbit — its least-squares
  residual targets `el[1]→0`, `el[0]→r` — and then checks `|el[1]−e_e|<1e-6`. Since **399/400 Earth
  orbits are eccentric** (e up to 0.74; idE 241 has e=3.3e-3), the check can *never* pass. This is the
  **exact analog of the 2026-05-24 `solve_arrival_dv` eccentric-window fix** (which unlocked +150/400
  Moon orbits) — applied to the Moon end but **never mirrored to the Earth end**. An asymmetry bug: a
  known fix lives on one symmetric half of the problem and silently not the other.
- *Why it dominated:* it sits *downstream* of every backward-shoot solver, so it defeated ~8 distinct
  per-pair methods (E-619/681/687..691) regardless of their quality — the canonical "the wall is in the
  evaluator, not the search" trap.
- *Fix:* `scripts/ch1_departure_ecc.py::solve_departure_dv_ecc`, the eccentric mirror (Earth μ, window
  `[a_e(1−e_e), a_e(1+e_e)]`, velocity solved to the full (a,e,i)). Backward-shoot CMA then finds
  **official-valid** sub-bank captures immediately: (241,50) 6617→4315–4797 (+592–715 kg), (139,31)
  6532→4254 (+652), (334,312) 5906→4928 (+248). Fleet sweep realizing it across 289 expensive pairs.

## Wrong conclusions corrected (see each node's retraction banner)
- **E-619** "per-pair ΔV floored at ~3851 m/s; departure at the LEO floor" → RETRACTED: floor was a
  basin/weak-solver artifact (B1+B2..B5); sub-bank captures exist.
- **E-602** "matching near-optimal (A2 closed)" and "WSB is the fleet lever" → REFRAMED: the gap is
  departure-energy then per-pair *solver capability*, not capture physics; `corr(dv,eL)` was a
  symptom not a cause.
- **E-604** "WSB refuted ⇒ the circular-capture lever is closed" → NARROWED: it refuted one *pipeline*
  (eccentric-window ballistic capture on circular targets); the lever lives, realizable by a global
  solver, not that pipeline.

## The transferable lesson
A "ceiling/floored/exhausted" verdict is only as trustworthy as the solver that produced it. Before
shipping such a verdict, **state the solver/architecture it assumes**, and run the
basin-lock diagnostic (`M-general-basin-overarching-search.md`): do any methods accept worse states /
rebuild structure / search globally from diverse seeds? If not — and especially if a constrained
search "only ever returns the seed" — the lever is untried, not absent.
