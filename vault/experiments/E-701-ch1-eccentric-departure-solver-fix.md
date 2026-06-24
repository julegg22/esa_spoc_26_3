---
id: E-701
type: experiment
status: BREAKTHROUGH — the Ch1-trajectory circular-capture lever is REALIZED (officially validated).
  The blocker was never precision/STM: solve_departure_dv was CIRCULAR-ONLY (required e_e≈0) and so
  failed all 399 eccentric Earth orbits — the exact analog of the 2026-05-24 arrival-side fix, never
  mirrored to the Earth end. With the eccentric departure solver, backward-shooting CMA finds
  official-valid SUB-BANK captures: (241,50) bank 6617 → 4315–4797 m/s (+592–715 kg/pair). Checkpointed
  fleet sweep over 289 expensive pairs running.
corrects: [E-697, E-700, E-619]
date: 2026-06-22
tags: [ch1, trajectory, breakthrough, eccentric-departure, bug-fix, circular-capture, backward-shooting, basin-overarching]
related: [[E-697-ch1-trajectory-global-smooth-breakthrough]], [[E-700-ch1-trajectory-bugfix-journal]],
  [[M-general-basin-overarching-search]], [[T-009-ch1-trajectory-architectural-plateau]]
---
# E-701 — Ch1 trajectory: the eccentric departure-solver fix realizes the lever

## The intended path, and the better thing it surfaced
The plan (E-697 follow-on) was an **STM (variational-equations) corrector** to close the official
384m/1e-6 window where finite-diff DCs stall at ~1km. Step 1 (validate the STM) succeeded — heyoka
`var_ode_sys`/`var_args` gives the analytic 6×6 Jacobian, machine-precision vs finite-diff. But driving
it on real pairs exposed that the seeds weren't at ~1km at all: the back-shot **natural** semi-major
axis was ~600,000 km off with e≈0.986. That was the tell.

## The actual bug (B9) — circular-only departure solver
`solve_departure_dv` (the Earth-side feasibility used by the backward-shoot official check) builds a
**circular** departure orbit: its residual targets `el[1]→0`, `el[0]→r`, and it then checks
`|el[1]-e_e|<1e-6`. Since **399/400 Earth orbits are eccentric** (e up to 0.74; idE 241 has e=3.3e-3),
that check can **never** pass → every backward-shot official validation was doomed *regardless of
corrector precision*. This is the **exact analog of the 2026-05-24 `solve_arrival_dv` fix** (eccentric
arrival window `[a(1-e),a(1+e)]`, +150/400 Moon orbits unlocked) — applied to the Moon end but **never
mirrored to the Earth end**. RAAN/argp/ν are free per the validator, so the true departure condition is
just: position radius in `[a_e(1-e_e), a_e(1+e_e)]`; the Earth-orbit velocity is then solved so
`(r_ef,v_orb)=(a_e,e_e,i_e)` and `dv0 = v_transfer − v_orb`. The window is ±a_e·e_e (km-scale), **not
384m** — so the eccentric majority needs **no STM corrector at all**.

## The fix + result
`scripts/ch1_departure_ecc.py::solve_departure_dv_ecc` — the exact eccentric mirror of
`solve_arrival_dv` (Earth μ). Dropped into the backward-shoot solver
(`scripts/ch1_backshoot_ecc.py`), CMA finds **officially-validated** (`udp.fitness<0`) sub-bank
captures immediately:
- **(241,50)** bank ΔV=6617 (mass ~71 kg) → official-valid **4315–4797 m/s** across restarts,
  **mass 537–715 kg, +592 kg** (fleet-guarded run). First from-scratch *official-valid* sub-bank
  capture in the whole investigation.

## Fleet realization (running)
`scripts/ch1_ecc_fleet.py` — per-pair drop-in replacement **keeping each pair's (idE,idL,idD)** so
fleet uniqueness holds and the swap is separable (single-row objective is the per-transfer term);
**strict guard** accepts only new single-row mass > bank mass. Checkpoints to
`cache/ch1_ecc_fleet.json` **every pair**, resumes on restart, startup positive-control. Sweeping the
289 expensive (bank_dv>3200) of 326 filled pairs, most-headroom first. Assemble + whole-fleet validate
+ guard-bank when enough pairs are in.

## What this corrects
- **E-697**: right diagnosis (basin-lock, lever real, global search the key), but it attributed the
  remaining gap to *precision* (→STM corrector). The real residual blocker was this **feasibility-
  function bug**, not precision. The STM tool is validated and shelved (not needed for the eccentric
  majority; may still help any genuinely circular Earth orbit — only 1/400).
- **E-700 (B-series)**: add **B9 — circular-only departure solver**, the highest-impact bug of the set
  (it alone gated every backward-shoot official validation).
- **E-619 / "per-pair floored"**: definitively retracted — the expensive captures are **not** floored;
  they were unreachable only because the Earth-side feasibility test rejected every eccentric orbit.

## Methodology
Canonical [[M-general-basin-overarching-search]] case AND a textbook "errors in the experiments we
tried" find (user's standing suspicion): the wall was an **asymmetry bug** — a known fix applied to one
symmetric half of the problem and silently not the other. The STM detour was not wasted: validating it
is what exposed the absurd back-shot orbit that pointed at the real bug.
