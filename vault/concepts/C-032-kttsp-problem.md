---
id: C-032
type: concept
status: confirmed
tags: [ch2, kttsp, tsp, time-dependent-routing, lambert, problem-definition]
scope: ch2/problem
confidence: high
created: 2026-06-13
sources:
  - "Official KTTSP UDP (reference/spoc4_udp/kttsp-{small,medium,large}.py) — the authoritative scorer"
  - "ESA SpOC4 Challenge 2 problem statement"
related: ["[[O-005-ch2-kttsp-official-udp]]", "[[concepts/C-006-lambert-problem-and-orbital-tsp]]", "[[concepts/C-010-constrained-hamiltonian-time-dependent-routing]]", "[[concepts/C-012-earliest-feasible-tof]]", "[[concepts/C-026-dp-on-time-expanded-graph]]", "[[concepts/C-030-lkh3-tsp-solver]]"]
---

# C-032 — KTTSP (Keplerian Tomato Traveling Salesperson Problem)

*ESA SpOC4 Challenge 2. A time-dependent orbital routing problem: visit
every "tomato" once, in an order + schedule that minimizes total mission
time, under per-leg Δv and chronology constraints. This note is the
plain-language primer; the exact UDP scorer lives in [[O-005-ch2-kttsp-official-udp]].*

## What the name means

- **Keplerian** — the targets ("tomatoes" — small bodies in orbit about
  the Moon) and the spacecraft all move on fixed **Keplerian orbits**
  (MU_MOON = 4.9048695e12). A target's position is a function of time:
  `keplerian.eph(t)`.
- **Tomato** — the instance language's whimsical name for a target node.
  Pure flavor; a tomato is just a city to be visited.
- **Traveling Salesperson Problem** — you must visit all N tomatoes
  exactly once. But unlike a classic TSP, the cost of going from tomato
  *i* to tomato *j* depends on **when** you depart and how long you take —
  so it is a **time-dependent ATSP** (asymmetric, because the Lambert Δv
  of i→j ≠ j→i).

## The problem in one paragraph

Choose (a) the **order** to visit the N tomatoes (a permutation), (b) the
**departure epoch** `times[k]` of each leg, and (c) the **time-of-flight**
`tofs[k]` of each leg. Each leg's velocity change Δv is computed by a
multi-rev **Lambert** solver from the two endpoint positions at the chosen
epochs. Minimize the **makespan** while respecting the fuel/feasibility
budget.

## Objective and constraints (see O-005 for the exact UDP)

- **Objective — makespan**: `total_time = times[-1] + tofs[-1]`
  (minimize). Equivalently Σ tof (flight) + Σ wait (idle). This single
  number is the leaderboard score; lower is better.
- **Visit-once**: the order must be a permutation of 0..N−1.
- **Δv cap**: every leg Δv ≤ `dv_exception` = 600 m/s (hard cap).
- **Exception budget**: at most `n_exception` = 5 legs may use Δv in
  the band (100, 600]; all other legs must be ≤ `dv_threshold` = 100 m/s
  ("cheap"). This is the structural heart of the problem — see below.
- **Chronological coupling**: `times[k] + tofs[k] ≤ times[k+1]` — you
  cannot depart leg k+1 before you have arrived from leg k. (You may
  *wait* — idle time — which is allowed but adds to makespan.)
- **min_tof** = 0.001 d, **t0** = 0. (`max_time` = 200 d for small is a
  feasibility cap, not usually binding once a good tour exists.)

The official `fitness(x)` returns `[total_time, perm_c, dv_c, time_c,
dv_exc_c]`; a feasible solution has the four constraint terms at
`[*, 0, 0, 0, 0]`.

## Decision vector

`x` has length 3N−2:
`times[0:N-1] ++ tofs[N-1:2N-2] ++ order[2N-2:]` (the last N entries are
the integer permutation). Submission JSON keeps the usual
`decisionVector` / `problem` / `challenge` shape with `problem ∈
{small, medium, large}`.

## The three instances

| instance | `.kttsp` file | N | dim (3N−2) | role |
|---|---|---|---|---|
| small  | `easy.kttsp`   | 49   | 145  | easy (weight ×1) |
| medium | `medium.kttsp` | 181  | 541  | medium (weight ×4/3) |
| large  | `hard.kttsp`   | 1051 | 3151 | hard (weight ×16/9) |

## Why it is hard (and where our levers live)

1. **Time-dependent cost matrix.** A leg's Δv (and its minimum feasible
   tof) depends strongly on the departure epoch via orbital phasing.
   Reorder the tour and *every downstream epoch shifts*, so any
   fixed-cost-matrix TSP solver (LKH, Concorde) optimizes the wrong
   objective unless wrapped in an epoch-rebuilding outer loop. This is
   the **"epoch-shift trap"** — the central recurring lesson. See
   [[concepts/C-030-lkh3-tsp-solver]] and [[concepts/C-010-constrained-hamiltonian-time-dependent-routing]].
2. **The cheap/exception structure.** Only ≤100 m/s legs are "free"; the
   cheap-Δv graph is sparse and typically splits into a few **components**
   (clusters of mutually-reachable tomatoes). You get just 5 expensive
   "bridges" to stitch components together. The whole route-construction
   problem reduces to: cover each component cheaply, then spend the 5
   exceptions wisely. See [[concepts/C-013-cluster-bridge-insertion-pattern]]
   and [[concepts/C-017-subtour-bridge-insertion-large-clusters]].
3. **Joint order + timing.** Makespan = flight + idle, and the two trade
   off: departing slightly later can buy a much shorter feasible tof
   (orbital phasing), so optimal timing is not "depart as early as
   possible." The timing sub-problem, for a *fixed* order, is solvable by
   a forward earliest-arrival sweep / DP on a time-expanded graph
   ([[concepts/C-012-earliest-feasible-tof]], [[concepts/C-026-dp-on-time-expanded-graph]]).
   The hard residual is the *joint* order+timing optimization.

## The shared-evaluator fact (important, vs Ch1)

The Δv of every leg comes from the official `kt.compute_transfer(i, j,
t_start, tof)` — a multi-rev Lambert solver (`max_revs=20`, min over
cw/ccw branches and revolution counts). Unlike Ch1 (where our
patched-conic model differs from the hidden full-physics validator),
**Ch2's `compute_transfer` IS the shared exact cost that every team
uses** — there is no hidden physics. So a leaderboard score lower than
ours is reachable *in principle* through search alone; the gap is route
structure, not an unmodeled transfer family.

## Standard solution pipeline

1. Precompute a cheap-edge (≤100 m/s) graph / transfer structure
   (epoch-aware, on a fine tof grid).
2. Construct a feasible tour: cover each cheap component, reserve the 5
   exceptions for unavoidable bridges (greedy earliest-feasible +
   cluster/sub-tour bridge insertion).
3. Optimize the schedule for the fixed order (forward earliest-arrival
   sweep / DP).
4. Search neighboring orders (ALNS / SA / LKH-per-component), always
   **re-evaluating timing chronologically** to avoid the epoch-shift trap.

## References

- [[O-005-ch2-kttsp-official-udp]] — the authoritative UDP spec (exact
  fitness vector, compute_transfer mechanics).
- [[concepts/C-006-lambert-problem-and-orbital-tsp]] — Lambert edges +
  orbital-TSP framing.
- [[concepts/C-010-constrained-hamiltonian-time-dependent-routing]] — the
  time-dependent routing structure and why reordering shifts costs.
- [[concepts/C-030-lkh3-tsp-solver]] — LKH and the epoch-shift trap.
