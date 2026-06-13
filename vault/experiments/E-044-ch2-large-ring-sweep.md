---
id: E-044
type: experiment
tags: [experiment, ch2, large, kttsp, ring-sweep, phase, banked, refutation]
date: 2026-06-12
status: PARTIAL WIN + DECISIVE REFUTATION — v1 banked 1048.98→1041.33 (−7.64d); v2 defrag refuted; pure phase-sweep cannot reach r1; large pole needs global TD-TSP
instance: hard.kttsp (n=1051)
script: scripts/ch2_e580_large_ring_sweep.py, scripts/ch2_e581_large_defrag_sweep.py
related: [[E-043-ch2-large-legslack-phasemiss]], [[E-041-ch2-large-gap-decomposition]], [[ch2-large-bank]], [[ch2-compute-parallelization-roi]], [[competitor-algorithm-inference]]
---

# E-044 — Ch2 large: ring phase-sweep (v1 banked, v2 refuted)

Follow-up to E-043's ring decomposition. Two constructions tested.

## v1 (E-580) — within-run phase sweep on the bank skeleton → BANKED

Keep the bank's run sequence, bridge endpoints, and exception placement;
re-order each same-ring run's interior by argument of latitude
u=argp+M (forward & backward sweeps), choose per run by realised
chronological walk from the actual arrival state (self-consistent epochs).

**Result: 1048.9786 → 1041.3340 d (−7.64 d), feasible, exc=5.**
Guard-banked (fresh re-score 1041.334034, viol [0,0,0,0], perm valid,
strictly better, backup `large.json.bak.e580`, round-trip OK). Still
RANK 2 (0 marginal points; bank already beats r2=1143.56) — new best
incumbent + seed for further work.

Only 7.6 d because within contiguous runs the bank was already near
phase-optimal.

## Structure (16 rings; 2 shells)

- **small shell** a≈3747 km, period 0.238 d: 3 rings {0°,90°,180°},
  150 nodes each — each visited as **1 clean fragment** in the bank.
- **big shell** a≈14989 km, period 1.906 d: 13 rings. The 3 dense ones
  (0°/90°/180°, ~155-163 nodes) are **fragmented into 2-4 visits each**;
  10 minor planes (15-165°, ~9-13 nodes) cost 1.8-3.2 d/node.

## v2 (E-581) — defragmenting sweep (finish each ring once) → REFUTED

Rebuild the order to sweep each ring to completion (small shell, then big
shell), bridging rings greedily. **Aborted at ring 2**: after sweeping
ring(0,90) it could not bridge to ring(0,180). The small-shell rings
(equatorial/polar/retrograde) need large plane changes, cheap only at
specific co-phased epochs. **Inter-ring bridges are COUPLED across rings**
— committing to a full-ring sweep destroys the phasing the next bridge
needs. This is the core reason the problem is a hard time-dependent TSP,
not a separable per-ring sweep.

## Decisive probe — phase-adjacent floor

For ring(0,90), phase-sorted forward hops at a fixed epoch:
**mean 0.857 d, median 0.800 d, min 0.100 d (40/40 feasible)** — *worse*
than the bank's realised 0.692 d/node. So E-041's "0.150 d available" was
a single best-pair minimum over ~40 neighbours, **not chainable
sequentially**. The bank's ~0.69 d/node on the main rings is already near
the sequential-chaining floor for ordering heuristics.

Budget map of the 1041 d: 3 small rings ≈310 d + 3 big main rings ≈382 d
+ ~110 minor-plane nodes ≈242 d + bridges ≈100 d.

## Verdict (large pole position)

r1 = 424.62 d ⇒ **0.404 d/node average**, below even phase-adjacent
(0.857 d). No greedy/sweep/local-repair heuristic reaches it (confirmed
across E-572/573/576/577/578/580/581). Crossing 424.62 requires a
**global time-dependent TSP solver** (LKH/Concorde on an iterated
epoch-aware cost matrix that re-chains the cheap-tof pairs better than
greedy) — almost certainly TGMA's recipe for their one-shot 1143→424 jump
(June 5). That is a multi-day build, **binary** (0 marginal points unless
it actually crosses 424.62; large is already secure at rank 2), with
~30-40% estimated odds → **LOW expected points/hour**.

## Lesson

A loose per-leg lower bound (E-043's 500 d "recoverable") can collapse
under sequential consumption: v1 realised only 7.6 d of it. Test the
cheapest construction before claiming the bound is reachable, and probe
the *chainable* per-step floor (phase-adjacent here) rather than the
single-pair minimum.
