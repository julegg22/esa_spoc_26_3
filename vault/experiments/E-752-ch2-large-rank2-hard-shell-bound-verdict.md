---
id: E-752
type: experiment
tags: [ch2, large, rank-2, hard-shell, verdict, exhaustion]
date: 2026-06-29
status: DONE — comprehensive 8h-window verdict: large rank-2 (-197d to 682) is HARD-SHELL-BOUND; bank 879.53 (rank-3) is our method floor; rank-2 needs a denser cheap graph / different transfer model = competitor's research-grade edge
related: ["[[E-750-ch2-large-beam-completion-wall]]", "[[E-748-ch2-large-worst-leg-lns]]", "[[E-729-ch2-large-low-degree-bottleneck-and-cheap-slot]]", "[[ch2-large-first-bank-topology]]", "[[E-721-ch2-large-cheap-graph-recompute]]"]
---
# E-752 — Ch2-large rank-2 is hard-shell-bound (8h-window comprehensive verdict)

The 8h ch2 window drove large rank-2 (879.53 → need 682, -197d) through the entire reorder/completion family.
**Every method walls on the SAME ~29-33 structurally-low-degree comp0 cities.**

## Reorder/completion family — all exhausted this window
- **Worst-leg exact-clock repair** (E-748): banked 890.99→879.53 (-11.46d, a small-cluster leg), then plateaued.
- **Forward beam W=150** (E-750): walls 546/601 @ 258d.
- **Backward beam** (E-750): walls 324/601; **33 cities stranded BOTH ways** (bidirectionally hard).
- **Completion-by-insertion** (E-751): grafting the 55 hard cities onto the cheap 546-core gives a feasible (1
  exc) tour but **1338d ≫ 804** — the cheap core is cheap only by omitting the hard cities.
- **SA order-search on the complete comp0 order** (E-724): baseline 1112d/3-strands, **0 accepts in 25 iters**
  — the bank's comp0 order is locally optimal.

## Root cause — measured, structural, NOT a graph artifact
- comp0 cheap out-degree: **median 152, but 29 cities <10 (worst 6-8)** — e.g. city 134 has 6 cheap neighbours.
- The cheap graph is **faithful**: dense1d was built with `MAXREV = kt.max_revs = 20` (full multi-rev) and
  recomputed in E-721. The low degree is real, not under-counting.
- These low-degree "hard-shell" cities are expensive to reach in **any** ordering (the bank already routes them
  about as well as the cheap graph allows: comp0 804d). Threading them cheaply is bidirectionally impossible.

## Verdict
**Large rank-2 (682) is hard-shell-bound and beyond our current method.** It requires the ~29 hard cities to be
reachable cheaper than the faithful cheap graph permits — i.e. a **denser cheap graph (different transfer model:
low-energy / many-rev / phasing tricks) or a fundamentally different solver** = the competitor's likely edge,
**research-grade**. The bank **879.53 (rank-3, 138d cushion) is our method floor**; accept rank-3. The cheapest
remaining +EV ch2 action is the **medium rank-1 submission** (182.11, now aligned in the upload, user-gated).
Not refuted, not a basin-lock we can escape with our tools — a genuine model-capacity wall.

## Bank impact
None. Large held 879.53 (rank-3). All ch2 banks held/feasible.
