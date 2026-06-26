---
id: E-722
type: experiment
tags: [ch2, large, rank-1, construction, beam, fail-first, sub-tour, phase-lock, cascade]
date: 2026-06-26
status: ACTIVE — forward construction ceiling ~575 characterized; phase-lock crux isolated
---

# E-722 — Ch2-large rank-1: reachability-aware beam + sub-tour bridge → the PHASE-LOCK crux

> 🔄 **REFRAMED 2026-06-26 by [[E-726-ch2-large-ultrathink-audit-rank1-reachable|E-726]]** (data valid,
> direction wrong). The measurements below — forward construction caps ~564–575, insertion/bridge cascade —
> all stand. The **conclusion** ("a hard wall / phase-lock crux / needs a global TD-TSP moonshot") was skewed
> by the premise **P: completeness (cities-threaded) measures progress toward rank-1.** Corrected premise
> **P′:** the beam already threads 558 @ 283 d = **0.51 d/leg = rank-1 PACE**; the cap is *completeness only*,
> not makespan. Under P′ this same result means **rank-1 is a COMPLETION problem on an already-fast structure,
> not a 2× compression** — reachable, not a moonshot. See [[M-general-root-objective-and-proxy-skew]].

After insertion/SA was proven cascade-defeated (E-721g), the next family was global *construction* that never
perturbs a tight schedule. Two distinct constructors built and run on the corrected graph
(`ch2_giant_dense1d_aug.npz`):

## Reachability-aware ("fail-first") beam (`ch2_giant_reach_beam.py`)

State ranking `t + LAM*risk`, where `risk = Σ_{unvisited hard h} 1/max(1,#unvisited preds(h))` (penalize burning
a hard city's few predecessors) + forced-capture of a hard city about to lose its last predecessor.

| beam | threaded | hard threaded | d/leg |
|---|---|---|---|
| coverage-elite (E-719b) | 575 | — | 0.65 |
| reach t16/LAM1.0/Crit4 | **564** | 31/38 | 0.582 |
| reach t22/LAM0.5/Crit3 | **564** | 90/112 | 0.589 |

Fail-first threaded **more hard cities but fewer total** — grabbing hard cities early strands the easy tail.
So **forward construction caps ~564–575 regardless of heuristic** (earliest-arrival, coverage-elite,
fail-first all land there). That ceiling is the structural fact.

## Diagnostic — the 564-tour's 37 missing cities (decisive)

- **NOT the hard cities** (median in-deg **41**, only min 14) — a **coherent internally-connected cluster**
  (8.9 internal preds/city).
- **All 37 enterable from the tour; 32/37 from the first 200 cities.** The beam bypassed them and dead-ended
  at frontier city 24 (**0 successors into the cluster**) — textbook corner-painting, not unreachability.

## Sub-tour bridge (`ch2_giant_subtour_bridge.py`) — the Ch2-medium pattern — FAILS here

Splice a time-dependent detour through the cluster into the main tour. Result: **detour covers only 1 city**
(can't chain >1 missing city from a given entry time), and splicing that 1 city **cascades the suffix to ~300
strands, makespan 15,777 d**.

## The crux: PHASE-LOCK (reconciles everything)

Every cheap transfer is **phase-locked** — feasible only in a narrow TOF band at a narrow accumulated clock.
The 2d-resolution table's "wide epoch windows" mean *some* predecessor is cheap at that epoch, **NOT** that a
*specific consecutive pair* stays feasible under a clock shift. Consequences, all now observed:
- The 601-tour must be a **single phase-coherent chain** built forward.
- **Forward beam** builds such a chain but **corner-paints at ~575** (commits to a frontier from which the
  remaining cluster isn't phase-reachable).
- **Any insertion / detour / 2-opt** shifts the downstream clock → breaks phase for the whole suffix →
  cascades (1 city → 300 strands). So **all local repair and bridging are dead** (independent of E-721g's ALNS
  evidence — this is a *second* confirmation at the 1-city limit).

## Lever decision (this tick) + next steps

Forward-beam heuristics exhausted (3 variants → 564–575); local repair/bridge dead (cascade). Per CLAUDE.md
§5b the freed cores went to **untried forward levers**: a **much wider coverage-beam (W=220, only W≤100 tried
before — width directly fights corner-painting)** and a **focused fail-first on only the truly-hard in-deg<15**.
If width doesn't break 575, the next named build is a **rollout/lookahead-augmented forward construction**
(score each candidate by a short greedy rollout to estimate *completability*, so the beam stops committing to
dead-end frontiers) — the standard fix for beam corner-painting, and a concrete build, not a stop. Rank-2
(932.53) secure; TDSA-D continues toward a complete rank-2 tour (20 strands) as the realistic interim outcome.

Extends [[E-721-ch2-large-foundational-graph-undercount]]; the phase-lock crux sharpens
[[foundation-then-search-methodology]] and [[basin-overarching-search]].
