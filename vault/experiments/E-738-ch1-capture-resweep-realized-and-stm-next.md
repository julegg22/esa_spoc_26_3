---
id: E-738
type: experiment
tags: [ch1, trajectory, capture, basin-lock, realized, stm-corrector, next-build]
date: 2026-06-28
status: DONE — existing-solver re-sweep realized +897 kg (confirms E-737 lever real), plateaus short of rank-5; STM-corrector inner loop = the named rank-5 build
related: ["[[E-737-ch1-capture-lever-reopened-correction]]", "[[E-697-ch1-trajectory-global-smooth-breakthrough]]", "[[E-700-ch1-trajectory-bugfix-journal]]"]
---
# E-738 — Ch1 capture re-sweep: realized +897 kg (lever confirmed real), STM corrector is the rank-5 path

Following E-737 (which reopened the basin-locked circular-capture lever), I RE-RAN the eccentric backshoot fleet
sweep (`ch1_ecc_fleet.py`, E-697 global non-bank-init CMA) at **higher effort (restarts 5→8)** over the 21 worst
circular captures (bank_dv>4500), baselined against the CURRENT bank (361,014), guard-banking per-pair official
improvements (keep bank idD, `.bak` each).

## Result — lever is REAL and partially realized
- **Ch1 bank 361,014 → 361,910.4 kg (+897, officially feasible, guard-banked, NOT submitted).** Sample per-pair:
  (209,23) 5207→4114 m/s +249, (133,53) 5044→4334 +234, (220,44) 5257→4462 +123. **Confirms E-737: capture was
  basin-locked, not physics-floored** — more search escapes to cheaper feasible captures. **Decisively refutes the
  E-733/E-736 "physics-floored / Ch1 at floor" verdicts.**
- **But it plateaus:** per-pair realized gain ≈ HALF the checkpoint's recorded gain (the guard keeps the bank's
  E-706-optimal idD, not the sweep's idD), and the later pairs add ~0. The existing solver gets the worst pairs
  from 5000-5200 m/s down to ~4100-4800 — **not to the ~3763 m/s total / ~875 m/s DV2 energy floor** (E-697).
  Extrapolated ceiling for the existing solver over all ~90 circular pairs ≈ **+2-4k kg**, short of the **+10,819
  to rank-5** (372,729).

## The rank-5 build (named, per CLAUDE.md §5b) — STM corrector in the CMA inner loop
E-697 proved feasible captures exist at the ~875 m/s floor at SEARCH level (1e-12), but the **noisy CMA seed
cannot thread the official 384 m / 1e-6 window** on sensitive 3-body capture arcs — finite-difference correctors
stall at ~1 km. The fix is the **STM-based (variational-equations / analytic-Jacobian) differential corrector**
(`ch1_stm_corrector.py`, built + validated in E-700/E-701 but **shelved / never wired into the sweep** because the
eccentric *departure* fix made it unnecessary on the departure side). **Wiring the STM corrector as a refinement
step inside `solve_pair` (CMA finds the basin → STM polishes to 384 m) is the research-grade build that realizes
the full ~875 m/s floor on the ~90 circular captures ⇒ the +10k+ to rank-5 (and toward rank-3 ~472k).** This is
the single highest-value open Ch1 lever; it is a bounded, well-specified build (the corrector exists; it needs
integration + a fleet sweep), not a vague "research problem."

Banks unchanged except the guard-banked +897 (local, `.bak_*`); nothing submitted (user-gated). The existing
re-sweep continues to capture the residual worst pairs as low-priority core-fill.
