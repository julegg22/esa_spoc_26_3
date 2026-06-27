---
id: E-733
type: experiment
tags: [ch1, trajectory, deep-audit, capture, dv2, rank-5, lever]
date: 2026-06-27
status: DONE — /deepaudit ch1-trajectory; per-pair tooling near-floor (dep+capture+idd), one expensive JOINT-matching lever open
reframes: [E-706, E-707, E-708]
self-corrected: "capture solver-floored" hypothesis REFUTED in-audit by corr(DV2,eL)=-0.71 → capture is PHYSICS-floored (circular Moon orbits)
related: ["[[M-general-deep-single-prompt-audit]]", "[[ch1-trajectory-udp-floor-confirmed]]", "[[ch1-trajectory-mass-lever-exhausted]]", "[[E-701-ch1-eccentric-departure-solver-fix]]"]
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

## Phase 2 SELF-CORRECTION — capture is PHYSICS-floored, not solver-floored (the number overruled the story)

The cheap probe for A-CAPTURE (no-solve correlation on the bank + Moon orbits) **refuted my own hypothesis**:
- **corr(DV2, Moon eL) = −0.715; corr(DV2, Moon a) = −0.688.** Expensive-capture transfers (DV2>1200, n=90)
  are **near-CIRCULAR low Moon orbits (eL≈0.028)**; cheap-capture (DV2<500, n=46) are **eccentric (eL≈0.616)**.
- So high DV2 is **causal physics**: capturing into a circular low LLO needs ~1000+ m/s (no slow apolune
  arrival, narrow WSB window) — *exactly* E-604's WSB-refuted-for-circular case, here confirmed causal (this is
  the real meaning of E-602's −0.71, for the capture leg specifically). The 46 cheap captures are simply the
  eccentric Moon orbits, not a solver advantage. **DV2 is physics-floored; the departure-B9 analog does NOT hold
  for capture.**

## Verdict (corrected)

**The bank IS near our per-transfer tooling's floor: departure floored (2772, eccentric fix), capture
physics-floored (circular Moon orbits, corr −0.71), idd Hungarian-optimal (E-706), longer-tof refuted.** My
in-audit hypothesis "capture is solver-floored" was overturned by the correlation. The residual ~550 m/s /
+16k-to-rank-5 therefore lives in the **JOINT layer** — *which* Earth orbit is matched to each unavoidable
circular Moon orbit, and to which high-cld destination — i.e. the **realized-ΔV (+cld) matching**, which E-704
refuted only on the `|iE−iL|` *proxy* and never ran on the true objective (deemed 280 CPU-h). This is a genuine
"near-floor for the per-pair tooling, one expensive joint lever open" state — not a false ceiling. NB this also
sharpens, not refutes, the standing record: the circular-capture penalty is real and shared (we and the
competitor both pay it), consistent with [[ch1-trajectory-udp-floor-confirmed]].

## Further exploration paths (re-ranked after the in-audit self-correction)

Probe #1 below (capture-floor) was the planned cheapest test — **and the audit already RAN its cheapest form
(the no-solve correlation) and REFUTED it: capture is physics-floored.** So the surviving live levers re-rank:

1. **(was #3) Joint realized-cost matching re-opt — the surviving lever.** Violates "matching closed (E-704)".
   The circular Moon orbits (eL<0.1, ~90 of them) MUST all be captured into (~1000+ m/s, irreducible per-orbit);
   the only freedom is *which* Earth orbit (and idd destination) pairs with each. E-704 refuted the `|iE−iL|`
   *proxy* and called the true 400² realized-ΔV(+cld) matrix infeasible (280 CPU-h) — but a **bipartite re-match
   restricted to the ~140 worst transfers** (90 circular-capture + cld-capped 65, overlap) using the fast
   eccentric solver is ~1 % of that. **Build:** realized-cost sub-matrix on those rows × their k≈15 nearest
   alternative idl, Hungarian on the sub-block holding the rest fixed. **Binary:** any feasible re-match lowers
   fleet total ⇒ E-704's "infeasible" was a cost-scope artifact, matching reopens (→ rank-5 +16k). No change ⇒
   matching is genuinely at its joint optimum. *Cheapest of the survivors; take this first.*
2. **(was #2) B1 apolune-plane-change on the high-ΔV tail.** Violates "3-impulse geometry fixed"; deferred B1
   whose ~350k revisit trigger is MET. The high-iL circular captures (expensive tail, iL≈0.84) may shed ΔV via a
   plane change at apolune (cheap radius) instead of perilune. **Binary:** tail ΔV drops ⇒ +toward rank-5.
3. **WSB / low-energy capture for the circular targets, re-examined as a possible bug-class (NOT a refinement).**
   E-604 refuted WSB for circular targets on a *narrow window scan*; given the departure-B9 precedent, re-verify
   the WSB capture window for ~5 circular Moon orbits is genuinely empty and not a scan-resolution artifact.
   **Binary:** a feasible sub-1000 m/s WSB capture exists for any circular target ⇒ E-604 was resolution-limited,
   capture reopens after all. (Lowest prior — the −0.71 physics correlation argues it holds — but it is the only
   path that could reduce the *irreducible* circular-capture floor itself.)

Diagnostic only — no bank change, nothing submitted (user-gated). The cheapest *surviving* assumption-falsifying
probe is #1 (joint matching re-opt); next session takes it. The Ch2-medium rank-1 campaign continues in parallel.
