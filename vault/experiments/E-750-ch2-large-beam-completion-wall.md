---
id: E-750
type: experiment
tags: [ch2, large, beam, completion-wall, bidirectional, rank-2]
date: 2026-06-29
status: DONE — comp0 601-completion is beam-walled (forward 546, backward 324, 33 cities bidirectionally hard). Reframes the rank-2 lever from "complete the tour" to "cheaper backbone + graft hard cities"
related: ["[[E-710-ch2-large-time-ordering-wall-overturned]]", "[[E-748-ch2-large-worst-leg-lns]]", "[[ch2-large-first-bank-topology]]", "[[C-034-time-aware-beam-narrow-window-tdtsp]]"]
---
# E-750 — Ch2-large: the comp0 601-completion is bidirectionally beam-walled

8h-window completion push for rank-2 (-197d to 682). Ran forward beam W=150 + backward meet-in-middle.
- **Forward W=150 walls at 546/601** (258.1d @ 0.474 d/leg) — marginally past the historical ~540 wall.
- **Backward beam (T=420) walls at 324/601**, stranding 277.
- **Overlap: 33 cities stranded BOTH ways** (forward-only 2, backward-only 244). These 33 are **bidirectionally
  hard** — no cheap-leg ordering (forward, backward, or meet-in-middle) threads them. rank-1-via-pure-beam is
  beam-infeasible.

## Reframe — the bank already completes; the lever is a CHEAPER BACKBONE
The bank (879.53) visits all 601 comp0 cities by using **expensive legs** to reach the hard-shell. The beam's
**546-city cheap core runs at 0.47 d/leg** — a *better backbone* than the bank's order. So the rank-2 lever is not
"thread 601 cheaply" (impossible) but **"keep the cheap 546-core and graft the ~55 hard cities + satellites onto
it"** (completion-by-insertion), accepting a few expensive legs for the bidirectionally-hard 33. If the
cheap-core + grafted-tail beats 879.53, that's the gain. This is the next build.

## Bank impact
None. Large unchanged at 879.53 (rank-3, held). Forward 546-order preserved at cache/ch2_giant_fine_beam_546.json.
