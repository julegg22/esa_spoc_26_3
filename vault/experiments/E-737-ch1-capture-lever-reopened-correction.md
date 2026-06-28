---
id: E-737
type: experiment
tags: [ch1, trajectory, capture, basin-lock, correction, lever-open]
date: 2026-06-28
status: CORRECTION — E-733/E-736 "capture physics-floored / Ch1 at floor" are WRONG; the circular-capture lever is OPEN (basin-lock, ~+50-117k), per E-697
corrects: [E-733, E-736]
related: ["[[E-697-ch1-trajectory-global-smooth-breakthrough]]", "[[E-733-ch1-trajectory-deepaudit-capture-floor]]", "[[E-736-ch1-matching-lever-closed]]", "[[ch1-trajectory-udp-floor-confirmed]]", "[[M-general-basin-overarching-search]]"]
---
# E-737 — Ch1 capture lever REOPENED: my "physics-floored" was a basin-lock (corrects E-733/E-736)

While probing the one "open" Ch1 lever this session I re-read the vault and caught a **self-inflicted error**:
E-733's `corr(DV2,eL)=−0.71` → "capture physics-floored" and E-736's "Ch1 at tooling floor" **contradict the
standing BREAKTHROUGH E-697**, which proved the circular-capture cost is a **basin-lock, not physics**:
- E-697 (2026-06-22): a GLOBAL smooth-penalty CMA-ES with diverse non-bank init finds feasible **sub-bank**
  circular captures (pair (241,50): 6617→~6199-6310 search-level; the Jun-22 backshoot fleet sweep realized
  4447 m/s / mass 71→663, officially feasible). **13 prior bank-anchored solvers returned the bank exactly** —
  the "per-pair floored" verdict was a basin-lock artifact. DV2 ≈ 1700-2434 m/s in the bank vs a **~875 m/s
  minimum-energy floor** ⇒ DV2 is the reducible lever, **≈+117k** over the 90 expensive circular captures.
- This is the SAME over-generalization E-604 made ("circular capture closed") that E-697/E-700 retracted: the
  bank's high cost for circular orbits is a **solver-capability** limit, not orbital mechanics. My E-733
  rediscovered the symptom (−0.71) and repeated the wrong conclusion. **Annotated: REFRAMED, not refuted — the
  correlation is real; "physics-floored" is the error.**

## What I verified this session (grounds the correction)
- Current Ch1 bank = **361,013.5 kg** (feasible). The Jun-22 fleet-sweep checkpoints (`cache/ch1_ecc_fleet_w*of3.json`,
  160 pairs, recorded +32k vs the OLD bank) are now **fully superseded** — a per-pair guard applies **0/160** (the
  current bank already beats every one; (241,50) is already ≥663 kg).
- BUT the bank's **worst circular captures are still ~392-558 kg** (DV2 high) vs the **~956 kg energy floor**
  (DV0~2772 apogee-floored + DV2~875 ⇒ total ~3763 m/s ⇒ ~956 kg). So **~400-560 kg/transfer headroom remains on
  the ~90 worst circular pairs ⇒ the +50-117k lever is OPEN and unrealized in the current bank.**

## Corrected verdict — Ch1 is NOT at floor
The open Ch1 lever is **realizing E-697's cheap circular captures officially**: a solver that (a) escapes the
bank basin to the cheap-capture basin (E-697's global CMA-ES does this at search level) AND (b) validates to the
official 384 m / 1e-6 tolerance — the **STM-based corrector** (E-700/E-701 machinery: `ch1_stm_corrector.py`,
`ch1_backshoot_ecc.py`). The Jun-22 sweep used a weaker corrector (reached ~km, banked partial gains now absorbed).
**Realization = re-run the fleet sweep over the ~90 worst circular pairs with the STM corrector + E-697 global
init, guard-bank per-pair.** This is research-grade (sensitive 3-body capture arcs) but is the genuine, large,
named next lever — potentially rank-5 (+11.7k) → rank-3 (~472k). **E-733/E-736 "exhausted" retracted; Ch1 has a
live high-value lever.** Bank unchanged, nothing submitted.

## Methodology note
This is a textbook **anti-oscillation / check-the-vault** catch: a fresh audit (E-733) re-derived a symptom and
re-concluded a wall that a prior BREAKTHROUGH (E-697) had already overturned. The deep-audit Step 0 ("question the
recorded results, read the subtree") is what surfaced E-697 and prevented banking a false "Ch1 closed." Reinforces
[[M-general-basin-overarching-search]] and the rule: **before declaring a floor, grep the vault for a prior
breakthrough on the same axis.**
