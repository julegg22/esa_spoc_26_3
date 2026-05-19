---
id: C-006
type: concept
status: confirmed
tags: [astrodynamics, optimization, ch2, lambert]
scope: astrodynamics/two-point-bvp + optimization/time-dependent-tsp
confidence: high
created: 2026-05-19
sources:
  - "Battin, An Introduction to the Mathematics and Methods of Astrodynamics — Lambert's problem"
  - "pykep lambert_problem docs (esa.github.io/pykep)"
related: ["[[O-005-ch2-kttsp-official-udp]]", "[[H-003-ch2-small-lambert-metaheuristic]]", "[[C-003-weighted-3d-matching]]"]
---

# C-006 — Lambert's problem & the time-dependent orbital TSP

*Primer for non-experts: what makes Ch2 a TSP "with physics".*

## Definition

- **Lambert's problem**: given a start position **r₁**, an end
  position **r₂**, and a flight time **Δt**, find the orbit (hence
  the velocities **v₁**, **v₂**) connecting them. It's the orbital
  "which arrow do I throw to hit there in exactly this much time."
  There can be several solutions (short/long way "cw", and
  *multi-revolution* arcs that loop the central body N times).
- **Time-dependent (orbital) TSP**: a Travelling-Salesperson tour
  where each "city" is a *moving* target (a tomato on its own Moon
  orbit) and the cost of an edge depends on **when** you leave and
  **how long** you fly — not a fixed distance matrix.

## Why it matters here

Ch2 (`[[O-005-ch2-kttsp-official-udp]]`) is exactly this. To go from
tomato *i* to tomato *j*: read their positions at the chosen times
(`keplerian.eph`), solve Lambert for the required Δv, and that Δv
must respect the rules (≤100 m/s normally, ≤5 "exception" legs up
to 600, the rest infeasible). The objective is the **makespan**
(when you finish the last leg). So the solver must jointly choose
the **visiting order** (combinatorial, like `[[C-003-weighted-3d-matching]]`)
*and* the **departure times + flight times** (continuous) — coupled
because timing changes both feasibility and cost.

## Mechanics

For a leg: `r_i,v_i = orbit_i.eph(t)`, `r_j,v_j = orbit_j.eph(t+Δt)`;
`pk.lambert_problem(r_i, r_j, Δt, μ☾, cw, max_revs)` → candidate
(v₁,v₂); leg `Δv = |v₁−v_i| + |v₂−v_j|` (depart + arrive burns);
take the cheapest branch/rev. Waiting (later departure) or a longer
Δt can lower Δv but pushes the makespan and the 200-day budget.
Multi-rev arcs sometimes give very cheap transfers at the cost of
long Δt — a key lever.

## In practice

Lambert is cheap (~µs–ms) but a full (i,j,t,Δt) grid is huge, so
realistic solvers **precompute a feasible-edge / time structure**
then run a sequence+timing metaheuristic (LNS / GA / beam) —
mirroring how Ch1 matching needed structure, not brute force.
pykep 2.x required (`pk.lambert_problem`, `pk.planet.keplerian`).

## References

Battin (Lambert); pykep docs; campaign nodes O-005 / H-003.
