# E-757 — Ch1 moderate-TOF fleet: gains were an idD=0 validation artifact (E-754 refuted as-built)

**Date:** 2026-06-29 (8h autonomous window)
**Trigger:** assembling the E-754 moderate-TOF fleet gains into trajectory.json — `ch1_stm_assemble.py`
applied **0/246** candidates ("not in bank" + silent non-application). Investigated per CLAUDE.md §5a.

reframes: [[ch1-trajectory-udp-floor-confirmed]] (E-754 moderate-TOF lever)
relates: [[scientific-bug-surfacing-method]] (the original idD=0 silent-rejection bug), [[E-754-ch1-deepaudit-moderate-tof-capture-reopened]]

## The bug — `official_row` evaluates mass against delivery idD=**0**, not the assigned idD
`scripts/ch1_backshoot_ecc.py:71`:
```
row = [idE, idL, 0, float(t_arr - tof), ...]      # <-- idD hardcoded to 0
f = udp.fitness(row)[0]; return row, ..., -f      # mass computed with cld[idL, 0]
```
The cargo mass is `min(rocket_mass(ΔV), (200−dt)·cld[idL,idD])` (`ch1_trajectory.py:160`). With idD=0
the cargo density `cld[idL,0]` differs from the real assignment's `cld[idL,idD]`, so the reported mass
does **not** correspond to the actual delivery. The **fleet** then compared this idD=0 mass to the
bank's *real-idD* mass → spurious "gains".

## Measured (4 moderate-fleet "winners")
| pair (E,L,D) | fleet new_mass (idD=0) | re-spliced @ real idD | bank | real gain |
|---|---|---|---|---|
| (381,104,381) | 747 | **421** | 545 | **−124** |
| (154,42,335) | 809 | 506 | 635 | −129 |
| (368,92,361) | 855 | 555 | 689 | −134 |
| (380,133,323) | 714 | 555 | 646 | −91 |

Every "win" is actually a **loss** at the real idD. `ch1_stm_assemble.py` re-validates by splicing the
trajectory into the bank row (keeping the real idD) and checks `mass > cur` — so it **correctly
rejected all of them** (the bank 365,597.5 was never corrupted). But the fleet burned 3 cores for
hours producing gains that are all rejected at assembly. **Fleet stopped.**

## BUT — the cargo cap is NOT the wall (huge headroom); the open question is ΔV
Analytic probe over all 250 circular bank pairs (real idD):
- **250/250 are ROCKET-mass-limited** (realized mass < cargo cap), **0 cargo-limited**.
- Cargo cap even at dt=40d is 5,000–11,000 kg vs current masses ~800 kg ⇒ **186 pairs have >50 kg
  cargo headroom at moderate TOF**. So a ΔV reduction at dt≤40 would translate ~fully to mass.
⇒ The moderate-TOF idea is *not* killed by the cargo-time-cap. It hinges only on whether forcing
tof∈[35,60]d actually **lowers total ΔV** vs the bank's short-TOF solution. For the 4 buggy "winners"
it did **not** (re-spliced rocket mass 421–555 < bank 545–689 ⇒ moderate ΔV was *higher*). E-754's
forced-test claimed a ΔV drop for (125,329) — but that was the UDPModerate champion_f (pure ΔV), never
mass-validated at the real idD.

## Decisive test (running, `br9kdqelx`)
Correct-idD moderate solver (`official_row_idD`, real idD in row[2]) on the 4 highest-cargo-headroom
circular pairs. **Binary:** any pair with moderate-TOF mass > bank+5 ⇒ lever ALIVE — build a
corrected fleet (potentially large: rocket-limited + huge headroom). Zero wins ⇒ moderate TOF does not
lower ΔV for circular captures; E-754 lever is genuinely dead and the bank's short-TOF ΔV is near-floor.

## Verdict (interim)
E-754 "moderate-TOF capture → +60k → rank-3" is **refuted as built** — the +611 kg fleet gains were an
idD=0 evaluation artifact (rejected at assembly; bank safe). The *physics* question (does moderate TOF
lower circular-capture ΔV?) is decided by the running correct-idD test, not the buggy fleet. Cargo
headroom is confirmed huge, so IF moderate TOF lowers ΔV the lever is real and large.
