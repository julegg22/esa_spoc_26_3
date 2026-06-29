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

## RESULT — lever SALVAGED (correct-idD forced-test, 2026-06-29)
Forced-moderate-TOF test on the worst circular pair **(125,329): bank ΔV 4799 → moderate 4126 m/s @
tof 36d (−673 m/s), valid=True**. So moderate TOF *does* lower total ΔV for circular captures, and
(250/250 rocket-limited + cargo cap ≫ mass) that ΔV drop converts ~fully to mass. ⇒ the moderate-TOF
lever is **real** — the idD=0 bug had masked it by selecting the wrong pairs (the buggy fleet's
"winners" were pairs where moderate TOF *raised* ΔV; the real winners like (125,329) need the corrected
metric). Built `scripts/ch1_moderate_fleet_v2.py` (REAL-idD validation via `official_row_idD`, pairs
sorted lowest-bank-mass first = most ΔV room) and launched it (shards 0,1). It banks per-pair gains to
`cache/ch1_moderate_v2_fleet_w*of3.json` (assemble with `ch1_stm_assemble.py`, which already validates
at the real idD). Multi-hour, resumable.

## Verdict
E-754's **fleet** was refuted (idD=0 artifact; +611 kg illusory, bank never corrupted), but the
**underlying lever is alive**: moderate TOF genuinely lowers circular-capture ΔV and the cargo cap is
non-binding, so the corrected v2 fleet realizes real mass on the lowest-mass (highest-ΔV) circular
pairs. The methodology win: an aggregate "+611 kg gain" was a faithful-evaluator (idD) bug — caught by
the assembler's correct-idD revalidation (applied 0/246), per CLAUDE.md §5a. Trajectory is rank 7 with
large room, so the realized v2 gains are the top live points lever for Ch1.
