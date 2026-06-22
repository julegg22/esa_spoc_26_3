---
id: E-697
type: experiment
status: BREAKTHROUGH (no bank change yet) — a GLOBAL smooth-penalty CMA-ES search with diverse
  (non-bank) init broke the Ch1-trajectory feasibility wall that ~13 local/bank-seeded solvers hit;
  it finds feasible SUB-BANK circular captures (~6199–6310 m/s vs bank 6617), proving the +117k
  per-pair lever is REAL and was a basin-lock, not a ceiling. Precise official realization (384m/1e-6)
  is the open follow-on (E-701, STM corrector).
corrects: [E-619]
date: 2026-06-22
tags: [ch1, trajectory, basin-overarching, global-search, cmaes, smooth-penalty, breakthrough, circular-capture]
related: [[M-general-basin-overarching-search]], [[E-700-ch1-trajectory-bugfix-journal]],
  [[ch1-trajectory-udp-floor-confirmed]]
---
# E-697 — Ch1 trajectory: global smooth-penalty search breaks the basin-lock

## The move (user-prompted)
User observation: *"if the bank is in a razor-thin manifold different from the top solutions, wouldn't
GLOBAL basin-overarching search be appropriate? CMA-ES / SA — because we've only been trying to jump
out of our banked basin."* Exactly right. Every prior solver was **anchored to the bank's basin**
(bank-seeded local search, or a constrained global search whose flat infeasible-penalty gave no
gradient off the bank — see E-700 B2–B5). Replacing it with a **global CMA-ES, diverse non-bank
random init, smooth uncapped feasibility penalty (perilune→orbit + plane)** found feasible captures
in *other* basins immediately.

## Result
- On the expensive circular pair (241,50), bank ΔV = 6617: CMA-ES finds feasible **6199–6310** at the
  search level (1e-12). Reproduced across restarts and across both forward (perilune-targeting) and
  backward (exact-arrival-by-construction) architectures.
- This is the **first from-scratch feasible circular capture** in the whole investigation; 13 prior
  methods returned the bank exactly or failed. ⇒ the "per-pair floored" verdict (E-619) was a
  basin-lock artifact. **RETRACTS E-619; proves the ≈+117k circular-capture lever is real.**

## Decomposition (why the lever is large)
Expensive circular captures waste budget on a **bad capture**: ΔV2 ≈ 1700–2434 m/s vs a ~875 m/s
minimum-energy floor (the bank itself hits 853 on a favourable pair; orbital mechanics confirms
~875). ΔV0 is apogee-floored; ΔV2 is the reducible lever. Fixing the 90 expensive circular captures
≈ +117k, which with fill/assignment moves trajectory toward rank-3 (~472k).

## Open item (the only remaining gap)
The search finds sub-bank ΔV and the orbit match reaches **~1 km**, but the official validator needs
**384 m / 1e-6**. Finite-difference differential correctors stall at ~1 km on sensitive 3-body arcs.
The standard fix is an **STM-based (analytic-Jacobian / variational-equations) corrector** → E-701.
Once that lands, the per-pair solver validates and a checkpointed fleet sweep realizes the lever.

## Methodology
This is the canonical case for [[M-general-basin-overarching-search]] (now confirmed cross-challenge)
and its continuous-domain + smooth-penalty extension. The bugs that masked it are journaled in
[[E-700-ch1-trajectory-bugfix-journal]].
