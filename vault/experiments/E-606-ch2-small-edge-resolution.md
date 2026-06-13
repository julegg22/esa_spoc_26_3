---
id: E-606
type: experiment
tags: [experiment, ch2, small, cheap-graph, edge-resolution, lambert-resolution]
date: 2026-06-13
status: closed — edge-resolution-sufficient; the 4-component cheap graph is NOT a precompute artifact. The leaders' gap is not an under-resolved-edge-set phenomenon.
---

# E-606 — Ch2-small: is the cheap-graph edge set a Lambert/tof-resolution artifact?

## Hypothesis (the last untested Ch2-small lever)

The leaders (R3=110.88d, R1=101.65d) beat our bank makespan (116.3738d). The
remaining structural hypothesis: our Lambert transfer precompute
**under-resolves cheap transfers**, so the Δv≤100 adjacency is too sparse. The
cheap graph has **4 connected components {40,3,3,3}** with **zero
inter-component cheap edges**; the 3 tiny components bridge to comp0 only via
expensive (exceptional, Δv∈(100,600]) legs. If a higher-resolution precompute
(finer tof grid, longer tof horizon to catch multi-rev windows, finer departure
sampling) revealed transfers currently scored >100 m/s that are actually ≤100,
components would **merge**, opening cheaper routings and reducing the exceptional
budget pressure.

## Method — decisive measurement

Current precompute (`ch2_e526_precompute_ultrafine.py`): departure grid 0.05 d,
**tof grid linspace(0.025, 8.0, 160) — capped at 8 d**, max_revs=20.

Higher-resolution probe (`/tmp/e606_edge_res.py`, the `_edge_worker`
high-accuracy pattern from the official-style edge builder):
- departure grid 1.0 d over full [0, max_time)
- **tof grid 0.25 d out to 6 d, then 2.5 d out to 60 d** (extends past the 8 d cap
  to catch multi-rev cheap windows)
- top-K seeds → 15-basin Nelder-Mead polish
- uses the official `kt.compute_transfer` (same Lambert, both cw/ccw,
  max_revs=20) → any edge found is automatically consistent with `kt.fitness`.

Probed **all 774 inter-component directed pairs** (comp0↔tiny, tiny↔tiny) plus
**60 intra-comp0 samples** = 834 pairs. Evaluator audited: edge 0→39
reproduces official dv=98.223; the probe re-uses `kt.compute_transfer` so it
cannot disagree with official fitness.

## Result

```
current cheap directed edges: 138
new <=100 edges NOT in current set: 0
inter-component NEW cheap edges (would merge comps): 0

lowest inter-component min-Δv (top 15):
  14->16 dv=511.84  comps 0->2   45->4  dv=512.71  comps 0->1
  33->16 dv=512.28  comps 0->2   46->34 dv=512.79  comps 0->3
  16->33 dv=512.44  comps 2->0   14->32 dv=512.81  comps 0->2
  32->42 dv=512.69  comps 2->0   45->11 dv=512.88  comps 0->1
  16->42 dv=512.70  comps 2->0   ... (all >511 m/s)
```

- **Zero** new ≤100 edges at the higher resolution. The 138 cheap directed edges
  found by the current precompute are exactly the ones a 60-d-tof / 1-d-dep
  probe finds. The current resolution is already sufficient.
- **Zero** inter-component cheap edges. The lowest inter-component min-Δv anywhere
  is **511.84 m/s** — more than **5×** the 100 m/s cheap threshold. The 3 tiny
  components are isolated by a huge margin, not a marginal one; no plausible
  resolution refinement closes a 412 m/s gap.

## Verdict

**Edge-resolution-sufficient → this lever is CLOSED.** The 4-component cheap-graph
topology {40,3,3,3} is a genuine property of the instance, not an artifact of
the precompute tof cap or sampling density. The tiny components require
exceptional (Δv>100) legs to reach by physics, and only ~5 such legs are
budgeted — this is a hard structural constraint of the problem, identical for
every solver including the leaders (validated physics, max_revs=20).

Therefore the leaders' 101.65d / 110.88d cannot come from a denser cheap-edge
set we are missing. Combined with E-603 (flight-only lower bound 109.99d < R3,
so the entire R3 gap is phasing idle, not flight time), the Ch2-small gap is a
**routing/timing-of-the-given-graph** problem, not an edge-discovery problem.
No candidate was generated (edge set unchanged → nothing to rebuild). Bank
remains 116.3738d.

## Follow-on

The only consistent remaining direction for Ch2-small is squeezing phasing idle
out of the **existing** 4-component graph under the ≤5-exceptional-leg budget
(DP/ALNS timing on the fixed adjacency), not searching for new edges. See E-603
for the flight-only floor.
