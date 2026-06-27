---
id: E-733
type: experiment
tags: [ch1, trajectory, deep-audit, capture, dv2, rank-5, lever]
date: 2026-06-27
status: ACTIVE — /deepaudit ch1-trajectory; locates the residual gap in the CAPTURE burn (DV2), not departure
reframes: [E-706, E-707, E-708]
related: ["[[M-general-deep-single-prompt-audit]]", "[[ch1-trajectory-udp-floor-confirmed]]", "[[ch1-trajectory-mass-lever-exhausted]]", "[[E-701...]]"]
---
# E-733 — /deepaudit ch1-trajectory: the residual gap is CAPTURE (DV2), not departure or tof

User ran `/deepaudit ch1 trajectory` (while Ch2-medium precompute grinds). Bank **Y = 356,550 kg (rank 6)**;
**X = rank-5 372,729 (+16,179)**, rank-3 ~472k, rank-1 488,011. The session left this paused with open levers.

## Step 0 — questioned the recorded verdicts

The subtree is a chain of false "exhausted/floored" verdicts, most overturned by the **B9 eccentric-departure
asymmetry bug (E-701, +67,742 kg)** — "the wall was in the evaluator, not the search." Two recent stories needed
re-checking on the *current* (post-E-708) bank: (a) "departure-dominated is a red herring / longer-tof re-solve
is the lever" (E-707/708); (b) "idd cld-cap is recoverable" (E-706).

## Phase 2 — measured on the banked artifact (faithful: udp.fitness<0, round-trips exact)

bank 356,550 = **Σrocket_mass 377,057 − 20,507 (cld cap)**. Per-transfer ΔV mean **3870 m/s**:
- **DV0 departure: 2772 (72 %), p10 2462 / p90 3075** — tightly clustered, NEAR our tooling's floor (E-701
  eccentric fix worked). Not the lever.
- **DV1 mid-burn: 116** — small. **DV2 capture: 982, median 1096, p10 462, p90 1265, max 1770.**
- **tof: median 0.51 d; short-tof (<3d) meanDV 3859 ≈ longer [3,10)d 3935** → the E-707/708 "214 short-tof at
  4303 vs longer 2902 → longer-tof re-solve" premise is **STALE/REFUTED on the current bank** (longer is NOT
  cheaper now). REFRAMES E-707/708.
- **cld cap (20,507 kg):** `cap = (200−dt)·cld[idl,idd]`; dt≈0.5 d so (200−dt)≈200 is **maxed** — the cap is
  bound by the **(idl,idd) pairing**, with **idd already Hungarian-OPTIMAL (E-706)** and **idl re-opt REFUTED
  (E-704)**. So the cld cap is matching-bound, ~closed. REFRAMES the "idd recoverable" framing.

### The decisive finding
- **Competitor edge ≈ 550 m/s** (our mean 3870 vs rank-1-implied ~3320 = 1183 kg/transfer). **Departure is
  floored for BOTH** of us → their win must be elsewhere.
- **Our DV2 capture (median 1096) is ~2.4× the achievable floor (p10 462); 46/400 transfers already capture
  for <500 m/s — proving cheap capture IS achievable on this problem.** Closing DV2 982→~430 saves ~552 m/s =
  **almost exactly the whole gap to the rank-1-tier ΔV.** The 81-transfer high-total tail is elevated in BOTH
  departure (+387) and capture (+203).

## Phase 1 — the load-bearing unexamined assumption

**A-CAPTURE: "the per-transfer 3-impulse capture burn DV2 is near-optimal."** Never measured against an
achievable floor. Phase 2: DV2 median 1096 vs p10 462; 46 transfers achieve <500. A solution violating it = a
transfer re-solved with a low-energy capture at ~half the DV2. This is the EXACT shape of the departure B9 bug
(a whole burn left un-optimized by a feasibility/solver artifact), one leg downstream. Capture-side bugs are on
record (solve_arrival v1 rejected 150/400; B7 acceptance-window too tight; WSB "refuted" for circular targets).

## Phase 3 — paradigm inventory

| paradigm | touched? | survives Phase-1 scrutiny? |
|---|---|---|
| 3-impulse capture (current) | YES — DV2 median 1096 | the lever: 2.4× the 462 floor, untested for optimality |
| low-energy / WSB ballistic capture | refuted for circular (E-604) | **the refutation may be the SAME bug-class as departure B9** (a pipeline artifact, not physics) — 46 cheap-capture transfers prove it's reachable |
| idd assignment | Hungarian-OPTIMAL (E-706) | closed (genuine) |
| idl matching re-opt | refuted on |iE−iL| proxy (E-704); true matrix 280 CPU-h "infeasible" | the cost-scope ("all 400²") may be the artifact — restricting to the ~100 worst is cheap |
| longer-tof re-solve (E-707/708) | partial (88 swept) | **refuted on current bank** (short-tof not more expensive) |

## Verdict

**The "356,550 is near our tooling's floor" verdict is only TRUE for departure + idd; it is FALSE for capture.**
The residual ~550 m/s gap to the rank-1-tier ΔV lives almost entirely in the **capture burn DV2 (median 1096 vs
an achievable 462)**, and 46/400 transfers prove cheap capture is reachable on this very problem. Given the
campaign's history of capture-side solver/feasibility bugs (the exact shape that hid the departure B9 lever for
8 methods), **DV2 is the prime suspect for being solver-floored, not physics-floored.**

## Further exploration paths (3, cheapest info-gain first)

1. **Capture-floor probe (cheapest, decisive)** — violates A-CAPTURE. Take ~10 high-DV2 transfers (DV2>1200),
   re-solve ONLY the capture (vary capture geometry / coast / apolune-plane-change) on the official BCP fitness.
   **Binary:** any meaningful fraction drops DV2 toward ~462 ⇒ capture is *solver-floored* (departure-B9 analog)
   ⇒ a fleet-scale capture lever ≈ the whole +rank-3/rank-1 gap. Holds firm ⇒ capture is physics-floored, gap
   real. ~minutes (10 pair solves on `ch1_pair_udp.py` / the eccentric backshoot).
2. **B1 apolune-plane-change on the 81 high-total tail** — violates "3-impulse geometry fixed"; the deferred
   B1 fix whose "~350k revisit trigger" is now MET. Plane change at apolune (cheap) vs perilune. **Binary:**
   tail ΔV drops (dep+cap) ⇒ +up-to-11.5 k toward rank-5. Skeleton exists (`ch1_bcp_apolune.py`).
3. **Matching (idl) re-opt restricted to the ~100 worst transfers via the FAST eccentric solver** — violates
   "matching closed (E-704)". E-704 refuted the |iE−iL| proxy and called the true 400² matrix infeasible
   (280 CPU-h); restricting to the cld-capped 65 + high-DV2 ~50 transfers' *alternative* idl is ~1 % of that.
   **Binary:** any re-match improves total ⇒ E-704's "infeasible" was a cost-scope artifact, matching reopens.

Diagnostic only — no bank change, nothing submitted (user-gated). Per CLAUDE.md §5b, taking probe #1 next.
