---
id: E-619
type: experiment
corrected_by: [E-700, E-697]
status: "[RETRACTED 2026-06-22 — see E-700: the 'per-pair floored' verdict was a basin-lock artifact;
  sub-bank captures exist] complete"
tags: [ch1, trajectory, global-search, refuted-floor, departure-energy, wsb, low-energy-transfer, basin-overarching-search, decisive-null]

hypothesis: "The ~2x trajectory gap (our 236,420 kg vs r1 473,332) is a DEPARTURE-ENERGY gap, not capture: 98% of bank pairs are departure-dominated (mean dv0=2851 m/s, which alone exceeds HRI's whole implied budget ~2734). Our per-pair engine (PairUDP) caps coast at ~43d and seeds only Hohmann-family direct transfers, structurally excluding the long-coast Sun-assisted/low-energy (WSB / 3-body-manifold) regime that produces sub-Hohmann INJECTION. This is an architecture/seeding mismatch (refuted-floor shape), testable cheaply with a one-pair positive control."

created: 2026-06-15
ran_start: 2026-06-15
---

> ⚠️ **RETRACTED 2026-06-22 by E-700 / E-697.** The verdict *"per-pair ΔV is floored at ~3851 m/s;
> departure is at the physical LEO floor; the 0/3-pairs null is the true floor"* is **WRONG** — it was
> a **basin-lock / weak-solver artifact**, not a problem floor. A global smooth-penalty CMA-ES search
> with diverse (non-bank) init (E-697) found feasible **sub-bank** circular captures (~6199–6310 vs
> bank 6617), and the "floor"-confirming solvers had bugs (B1: circular pairs never actually evaluated;
> B2–B5: flat/penalty-landscape basin-lock — see E-700). The DEPARTURE-DOMINANCE measurement here
> (ΔV0 ≈ 66%) is correct and useful; only the "floored / nothing-left" *conclusion* is retracted. Body
> preserved below as the historical record — do not act on its floor verdict. → see E-700, E-697.

## Trigger

User (2026-06-15): "test our ideas with global search methods on ch1 trajectory ...
the large gap indicates a true mismatch of our approaches with the problem
structure. ultrathink ... 5 hypotheses ... plan to test them and close the gap."
Re-opens the E-610 "do not fund / rank-irrelevant" verdict, which rested on a
~3850 m/s per-pair floor that is itself an artifact of a bounded local engine.

## Ground-truth re-decomposition (E-619 Step 0, pure arithmetic on the bank)

301 filled pairs. Per-pair burn split (m/s):
- **dv0 departure:** min 665 / med 2944 / **mean 2851** / max 5661
- dv1 mid:           med 456 / mean 574
- dv2 capture:       med 853 / **mean 921** / max 3085
- total:             med 4333 / mean 4346

**98% of pairs are departure-dominated (dv0 > dv2).** dv0 share = 66% of total.

THE decisive number: **HRI's entire implied budget (~2734 m/s) is LESS than our
mean departure burn alone (2851).** So the leaders are NOT merely capturing for
free — their whole transfer, *injection included*, is sub-Hohmann. A free capture
(dv2->0) + zero mid burn would still leave us at 2851 > 2734. The departure burn
itself must come down. That is only physical via a low-energy 3-body / Sun-assisted
(WSB) transfer, which needs a long coast for the Sun term to do work.

Coast usage: mean 21.4d = 10.7% of the 200d horizon. corr(coast_days, dv0)=+0.14
— existing long-coast bank pairs do NOT have lower dv0 (they are *slow direct*
transfers from the Lambert+DC pipeline, not low-energy ones). So H1 cannot be
confirmed from bank data; it needs an ACTIVE global search that seeks Sun-assisted
structure -> the positive control (Step 1) is the real arbiter.

Engine fact (src/esa_spoc_26/ch1_pair_udp.py): PairUDP DoF = 12
[raan_e, argp_e, ea_dep, t0, T1, T2, dv0(3), dv1(3)]; dv2 SOLVED by
solve_arrival_eccentric (forced single capture). Bounds T1<=7 (~30d), T2<=3
(~13d) => <=43d coast. Seeds = bank + Hohmann multi-phasing only. The best E-605
winners sit at ~20d coast, Hohmann-class. The low-energy regime was never in the box.

## Five hypotheses for the ~2x gap

**H1 (TOP) — Coast-time box excludes the low-energy Sun-assisted regime.**
BCP Sun perturbation lowers departure energy (apogee pumping / WSB) over 80-130d
coasts; horizon affords it; our engine caps ~43d and seeds Hohmann. Mechanism for
a sub-Hohmann dv0. Most likely single cause.

**H2 (diagnostic, CONFIRMED) — Gap is departure-energy, not capture.**
98% departure-dominated; mean dv0 2851 >= HRI total. Narrows the search: the lever
is lower-energy INJECTION, reachable only in the long-coast/manifold regime (H1) or
a different transfer family (H5) — NOT a cheaper capture burn.

**H3 — Cold-start infeasibility makes "global" search a local polisher (basin/init).**
The ~3850 cap came from BANK-SEEDED refinement in the Hohmann basin; random 12-DoF
starts hit the 1e6 penalty (miss the thin (a,e,i) manifold). We have never globally
searched. Need feasible-manifold-aware seeding (backward-from-target / Lambert /
multi-rev) to reach non-Hohmann basins.

**H4 — Matching re-opt once the per-pair cost model changes (scope).**
Matching was closed (E-602) on the OLD Hohmann-family cost. If H1/H3 lower dv
non-uniformly and the 99 empty high-incl slots become cheaply fillable via long
transfers, the optimal assignment shifts. Defer until the per-pair engine improves;
then re-solve assignment (Hungarian) on the new cost matrix.

**H5 (decisive falsifier) — The 3-impulse BCP parametrization cannot express the
leader family at all (multi-rev / Lagrange-manifold highway).**
One-pair positive control with unbounded time + long coast: if we CANNOT break
clearly below ~3850 toward 2734 on even one pair, the parametrization itself is the
mismatch -> need a manifold/multi-rev transfer family (bigger build), the
true "architecture we never built" analog of Ch2-small's joint sequence+epoch search.

## Plan (cheap-first, gated)

- **Step 0 (done):** fleet burn decomposition -> H2 confirmed (departure-energy gap).
- **Step 1 (RUNNING, /tmp/ch1_e619_h1_posctrl.py):** re-run PairUDP on the 3 E-605
  winners with WIDENED bounds (T1<=20 ~87d, T2<=15 ~65d, ~150d total) + Sun-phase
  t0 sweep + long-coast Hohmann seeds, sade(400)->cmaes(400). **GATE:** any best
  clearly < its e605 best (toward 2734) => H1 confirmed, time-box was the wall.
- **Step 2 (H3, conditional):** add backward-from-target / Lambert feasible seeder;
  measure cold feasible-hit rate + whether non-Hohmann basins beat the bank basin.
- **Step 3 (H5 positive control, conditional):** one pair, unbounded time + active
  3rd impulse; the decisive falsifier of the parametrization.
- **Step 4 (conditional on Steps 1/3 breaking ~3500):** fleet-scale parallel per-pair
  re-opt + H4 matching re-solve on the new cost matrix.

## ★ CORRECTION (2026-06-15 ~17:40) — probability-weighted vs the 2x bar (user steer)

User: only chase levers that can explain the FULL 2x, not marginal ones. Re-ran the
arithmetic (`/tmp/ch1_e619_orbit_energy.py`, `/tmp/ch1_e619_gap_decomp.py`):

**The "~2734 m/s per pair" figure was an ARTIFACT of assuming r1 fills 301 pairs.**
At 301 pairs r1's 473,332 implies 1573 kg/pair = **2686 m/s, BELOW the LEO
departure floor (~2900)** — physically impossible. 95% of the 400 Earth orbits are
LEO (only 20 high-energy); the bank already injects at the floor (dv0 2851 ≈ ideal
2886). So r1 CANNOT reach the gap via per-pair dv on 301 pairs. The 2x = a PRODUCT
of two achievable levers:

| Lever | mechanism | factor | % of r1 |
|---|---|---|---|
| **A: per-pair dv -> floor** | keep departure (floored), KILL mid-burn (mean 574) + cheap/ballistic capture (921->~300-700) | 1.5-1.69x | 78-84% |
| **B: fill 301->~360-400** | the 99 empty (high-incl) slots | ~1.2-1.33x | the rest |
| **A x fill-360** | combined | **~2.0x** | **~100%** |

Refuted as 2x levers (probability ≈ 0):
- ❌ **Sun-assisted DEPARTURE** (original H1): departure is at the physical LEO
  floor; the Sun gives hundreds of m/s on *capture*, not injection.
- ❌ **Earth-orbit energy SELECTION**: only 20 cheap orbits, bank already takes
  them (re-select = 1.01x).

Surviving 2x levers:
- ✅ **Lever A = soft-burn reduction.** Our entire ~1000-1500 m/s of per-pair
  headroom lives in dv1 (mid 574) + dv2 (capture 921), NOT dv0. E-605 winners
  already show dv1->0 + dv2 732 reachable (3851 vs 4255). The question is the
  capture floor (ballistic/high-apolune). Dominant: ~1.69x, 84% of r1.
- ✅ **Lever B = fill, but COUPLED to matching (H4).** The unused earth/moon pool
  has median |iE-iL|=38deg (max 49deg) — the GOOD inclination matches are already
  taken, so naive fill needs ~38deg plane changes (expensive). Filling well
  requires JOINT re-matching (which earth pairs with which moon), not appending
  leftovers. This promotes H4 from "deferred" to a BINDING structural lever for the
  fill half. (Probe `/tmp/ch1_e619_leverB_fill.py` running: feasibility + dv of a
  16-pair sample of the empties.)

**Net corrected target:** NOT "find a sub-Hohmann departure" (impossible) but
(A) drive each pair's mid+capture burns to their minimum via global trajectory
search, AND (B) jointly re-match to make the empties cheaply fillable. Both needed;
2x = their product. The single highest-probability lever is A (84% alone).

## EV re-opening note

E-610 priced the trajectory lever at +15-25k kg (stuck in rank 6) ASSUMING a
~3850 m/s floor. That floor is exactly what Steps 1/3 test. If it falls, the ceiling
estimate is void and rank-5 (~372,729, +136k) re-enters scope. Cheap to test;
high option value. See [[E-049-ch1-trajectory-filled-pair-dof-exhausted]],
[[M-general-basin-overarching-search]], [[M-general-deep-single-prompt-audit]].

## ★★★ VERDICT (2026-06-15 ~17:30) — Lever-A floor test = DECISIVE NULL

`/tmp/ch1_e619_leverA_floor.py` ran the 3 E-605 winners winner-SEEDED (no H3
cold-start confound) with WIDENED capture coast (T2~43d, for ballistic/Sun-assisted
capture) + sade(600)→cmaes(600). Result (`/tmp/ch1_e619_leverA.log`):

| pair | winner | best | dv0 | dv1 | dv2 | Δ vs winner |
|---|---|---|---|---|---|---|
| (245,264) | 3851 | **3851** | 3119 | 0 | 732 | **+0** |
| (126,286) | 3858 | **3858** | 3169 | 0 | 690 | **+0** |
| (7,155)   | 4222 | 4221 | 2843 | 888 | 490 | −1 |

**0/3 pairs beat the E-605 local floor by >50 m/s ⇒ ~3851 m/s IS the true per-pair
floor**, now established by GLOBAL search (sade+cmaes from the feasible basin), not
an assumed bound. Two diagnostics that close the question:
- **dv1 (mid-burn) is already 0** on both good winners — the "kill the mid-burn"
  half of Lever A was already realized by E-605; there is nothing left there.
- **dv2 (capture) floors at ~690–732 m/s and the widened capture coast (T2~43d for
  ballistic/Sun-assisted capture) did NOT lower it.** The optimistic decomposition
  assumed a ~300 m/s capture floor (→1.69×); the REAL capture floor for these
  LEO→Moon pairs is ~700 m/s. So Lever A's true factor is ≈ E-610's +15–25k kg
  (~1.06–1.11×), NOT 1.69× — and certainly not the 2×.

### What this means for the 2× gap (the user's probability-weighted question)

Per-pair trajectory optimization is now EXHAUSTED as a 2× lever, with every
sub-lever measured shut:
- ❌ Sun-assisted DEPARTURE — refuted (LEO floored).
- ❌ Earth-orbit energy SELECTION — refuted (bank already optimal, 1.01×).
- ❌ Lever A soft-burn (mid+capture) — **CONFIRMED CAPPED at ~3851/pair (~1.1×)**,
  this test. dv1 already 0; dv2 capture floor ~700 unmoved by widened coast.
- ⚠️ Lever B fill — H3-confounded (cold-start manifold-miss ≠ physical
  infeasibility) AND coupled to matching (H4: unused pool median |iE−iL|=38°).

**Net: the 2× is NOT reachable by any per-pair lever in our current architecture
(per-pair BCP refinement + fixed Hungarian matching).** It would require the one
build we never made — a JOINT matching+trajectory+epoch global optimizer with
FEASIBLE-MANIFOLD seeding (H5 + H3 + H4 together): free (e,l) assignment co-optimized
with low-energy/long-coast transfer families and a backward-from-target seeder that
reaches non-Hohmann basins. This is the same architectural mismatch as Ch2-small
(joint sequence+epoch global search = the competitor pipeline we never built) —
[[E-618-ch2-small-grasp-multistart-floor]], [[M-general-basin-overarching-search]].

**E-610's "rank-6, do not fund the per-pair trajectory lever" verdict is
RE-CONFIRMED and now rests on a SEARCHED floor, not an assumed one.** Rank-5 (+136k)
re-enters scope ONLY via the multi-week joint-architecture build — high cost,
uncertain payoff, 15 days left. With every other instance's search frontier also
floored, the dominant realized-points lever remains SUBMISSION of the 6 banks
(user-gated). See [[E-049-ch1-trajectory-filled-pair-dof-exhausted]].

### Lever-B closure (2026-06-15 ~17:35) — neighbour-seeding does NOT defeat H3; fill is rank-irrelevant regardless

Tried to clean the H3 confound on the Lever-B fill probe by seeding each empty (e,l)
from its k nearest-inclination FILLED bank rows (`/tmp/ch1_e619_leverB_seeded.py`).
**Eval-only check killed the premise:** warm seeds land **0/6 feasible** (fitness=1e6
penalty) even for 0.3–0.4° empties — the (a,e,i) match constraint is PAIR-SPECIFIC, so
a neighbour's chromosome (tuned for the neighbour's SMA/ecc) does not transfer to the
empty's manifold. `bank_to_seed` only works on a pair's OWN bank row (as E-605 used it).
⇒ A proper Lever-B feasibility test REQUIRES the actual per-pair feasible-manifold
seeder — the Lambert+3D-DC pipeline (`src/esa_spoc_26/ch1_traj_lambert.py`) that built
the 301 filled pairs — run on the empties. That is the SAME H3/H5 seeder-build the 2×
verdict already identifies as the binding need.

**Not funding that build to chase Lever B, because it is rank-irrelevant:** even if all
99 empties fill at bank-avg mass (fill 301→~360, ~1.2–1.3×) AND Lever A's confirmed
~1.1× stacks, the product ≈1.3× ≈ ~307k kg — still deep in the rank-6 band (rank-5
needs +136k → ~372,729). So Lever B's exact magnitude cannot move the trajectory rank.
The corrected-assumption audit is complete: **no per-pair lever, alone or combined,
reaches rank-5; only the joint matching+trajectory+epoch architecture build does, and
it is a multi-week, EV-uncertain commitment with 15 days left.**
