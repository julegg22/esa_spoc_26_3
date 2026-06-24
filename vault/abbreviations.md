---
id: ABBREVIATIONS
type: index
updated: 2026-06-13T21:25:00+02:00
tags: [glossary, abbreviations, reference]
---

# Abbreviation index

Single source of truth for the acronyms and abbreviations that
appear across vault entries, hypotheses, scripts, and commit
messages. Each row links to the **primary explanation** (the
node where the term is properly defined or first heavily used).

**Maintenance**: update this file whenever a new acronym is
introduced. See `META.md §3` for the discipline.

> [!warning] Fresh-start scaffold (2026-05-18)
> This glossary was inherited from a prior mature campaign. The
> meanings are correct domain knowledge, but **every `[[primary
> node]]` link below is a forward-reference** — the H/E/T/C/M/L/O
> nodes do **not** exist yet in this repo. Links resolve as the
> campaign produces those nodes. Do not assume a node exists
> because it is linked here; check the frontier (`open-paths.md`).

---

## Vault entry types

| abbr | meaning | primary node |
|---|---|---|
| H | Hypothesis (falsifiable claim with prediction) | `META.md §1`, `_templates/hypothesis.md` |
| E | Experiment (the run that tests an H) | `_templates/experiment.md` |
| T | Takeaway (distilled finding from a closed H) | `_templates/takeaway.md` |
| O | Observation (measurement / data, no claim) | `_templates/observation.md` |
| Q | Question (umbrella for multiple H) | `_templates/question.md` |
| M | Methodology insight (publication-bound research-process learning) | `_templates/methodology.md` |
| L | Lesson (atomic engineering gotcha / ADR / workaround) | `_templates/lesson.md` |
| C | Concept (prior-knowledge primer: domain or tool) | `_templates/concept.md` |
| S | Session (episodic narrative of a working session) | `_templates/session.md` |

---

## Astrodynamics — bodies, frames, problems

| abbr | meaning | primary node |
|---|---|---|
| BCP | Bicircular Problem (Earth + Moon + Sun, restricted 4-body) | [[concepts/C-001-cr3bp-and-bicircular-problem]] |
| CR3BP | Circular Restricted 3-Body Problem (Earth + Moon, autonomous) | [[concepts/C-001-cr3bp-and-bicircular-problem]] |
| BVP | Boundary Value Problem (Lambert is a 2-point BVP) | [[C-006-lambert-problem-and-orbital-tsp]] |
| IVP | Initial Value Problem (BCP propagation is an IVP) | [[C-001-cr3bp-and-bicircular-problem]] |
| ODE | Ordinary Differential Equation (heyoka integrates ODEs) | [[C-001-cr3bp-and-bicircular-problem]] |
| SOI | Sphere of Influence (gravitational dominance boundary) | C-003-sphere-of-influence-patched-conics |
| LOI | Lunar Orbit Insertion (capture burn at Moon-relative periapsis) | [[concepts/C-002-delta-v-rocket-equation-loi]] |
| TOF | Time of Flight (transfer arc duration) | [[C-006-lambert-problem-and-orbital-tsp]] |
| GTO | Geostationary Transfer Orbit (mentioned for departure-energy context) | various Ch1 H |
| LEO | Low Earth Orbit | various Ch1 H |
| L1, L2, L3, L4, L5 | Lagrangian / libration points (CR3BP equilibria) | [[C-001-cr3bp-and-bicircular-problem]] |
| N-body | Many-body gravitational problem (full simulation) | [[C-001-cr3bp-and-bicircular-problem]] |
| dV / ΔV | Delta-V (impulsive velocity change) | [[C-006-lambert-problem-and-orbital-tsp]] |
| v_inf | Hyperbolic excess velocity (asymptotic speed at infinity from secondary) | C-004-hyperbolic-flyby-v-infinity |
| r_peri | Periapsis radius (closest approach to gravitating body) | C-004-hyperbolic-flyby-v-infinity |
| μ (mu) | Gravitational parameter `G·M`; per body: `μ_E`, `μ_M`, `μ_S` | [[C-001-cr3bp-and-bicircular-problem]] |

---

## Orbital elements (Keplerian)

| abbr | meaning | primary node |
|---|---|---|
| a | Semi-major axis | [[C-006-lambert-problem-and-orbital-tsp]] |
| e | Eccentricity | [[C-006-lambert-problem-and-orbital-tsp]] |
| i | Inclination | [[C-006-lambert-problem-and-orbital-tsp]] |
| Ω (raan) | Right Ascension of Ascending Node | [[C-006-lambert-problem-and-orbital-tsp]] |
| ω (argp) | Argument of Periapsis | [[C-006-lambert-problem-and-orbital-tsp]] |
| ν (nu) | True anomaly | [[C-006-lambert-problem-and-orbital-tsp]] |
| e_idx, l_idx | Indices into Earth-orbit / Moon-orbit catalogues for Ch1 Adv | H-009-ch1-advanced-infra |

---

## Synodic-frame normalisation (BCP units)

| abbr | meaning | primary node |
|---|---|---|
| L_SI | Earth-Moon distance ≈ 384 400 km (length unit) | [[C-001-cr3bp-and-bicircular-problem]] |
| T_SI | Synodic time unit `1/ω_EM` (≈ 4.348 d) | [[C-001-cr3bp-and-bicircular-problem]] |
| V_SI | `L_SI / T_SI` (synodic velocity unit) | [[C-001-cr3bp-and-bicircular-problem]] |
| MU_BCP | Mass parameter `μ_M / (μ_E + μ_M)` for BCP non-dim | [[C-001-cr3bp-and-bicircular-problem]] |
| ω_EM | Earth-Moon mean angular velocity | [[C-001-cr3bp-and-bicircular-problem]] |

---

## Optimisation methods and solvers

| abbr | meaning | primary node |
|---|---|---|
| LP | Linear Programming | [[concepts/C-004-mip-and-mip-lns]] |
| MIP / MILP | (Mixed-)Integer Linear Programming | [[concepts/C-004-mip-and-mip-lns]] |
| IPM | Interior Point Method (LP / convex algorithm) | M-005-cut-engagement-threshold-scales-with-instance-size |
| HiGHS | "High performance Software for Linear programming" — open-source LP/MIP solver | [[concepts/C-004-mip-and-mip-lns]] |
| TSP | Traveling Salesperson Problem | H-031-ch2-easy-mip |
| ATSP | Asymmetric TSP (direction-dependent costs) | H-031-ch2-easy-mip |
| MTZ | Miller-Tucker-Zemlin (subtour elimination via time variables) | H-031-ch2-easy-mip |
| LK | Lin-Kernighan (variable-depth k-opt TSP local search) | [[concepts/C-030-lkh3-tsp-solver]] |
| LKH / LKH-3 | Lin-Kernighan-Helsgaun (state-of-the-art LK implementation; LKH-3 adds ATSP/variants) | [[concepts/C-030-lkh3-tsp-solver]] |
| Concorde | Exact TSP solver (branch-and-cut); pairs with LKH as the high-end routing toolkit | [[concepts/C-030-lkh3-tsp-solver]] |
| elkai | Python wrapper around the LKH C solver | [[concepts/C-030-lkh3-tsp-solver]] |
| JV transform | Jonker-Volgenant ATSP→STSP node-doubling reduction (lets LKH's symmetric solver handle asymmetric costs) | [[concepts/C-030-lkh3-tsp-solver]] |
| DFJ | Dantzig-Fulkerson-Johnson (subtour elimination via lazy cuts) | H-031-ch2-easy-mip |
| LNS | Large Neighborhood Search (ruin + recreate metaheuristic) | [[concepts/C-011-metaheuristic-local-search-routing]] |
| SA | Simulated Annealing (Metropolis acceptance) | H-035-ch2-easy-sa-lns-with-precomp |
| GA | Genetic Algorithm (population + crossover + mutation) | H-037-ch2-easy-memetic-ga |
| MA | Memetic Algorithm (GA + inner local search) | [[C-011-metaheuristic-local-search-routing]] |
| DE | Differential Evolution (vector-difference mutation) | [[C-014-cma-es-and-evolution-strategies]] *(disambiguate from "DE440" ephemeris)* |
| CMA-ES | Covariance Matrix Adaptation Evolution Strategy | [[C-014-cma-es-and-evolution-strategies]] *(comparison table)* |
| NM | Nelder-Mead (simplex local search) | M-014-multi-start-refinement-as-artifact-resolver |
| BFGS | Broyden-Fletcher-Goldfarb-Shanno (quasi-Newton local search) | E-034-ch2-easy-continuous-time-probe |
| L-BFGS-B | Limited-memory BFGS with Bounds (scipy default for bounded smooth optimisation) | [[C-014-cma-es-and-evolution-strategies]] |
| PMX | Partial-Matched Crossover (permutation crossover for GA) | [[C-011-metaheuristic-local-search-routing]] |
| BLX-α | Blend Crossover with parameter α (real-valued GA crossover) | H-037-ch2-easy-memetic-ga |
| 2-opt | Tour-edit operator: reverse a sub-segment of the permutation | [[concepts/C-011-metaheuristic-local-search-routing]] |
| Or-opt | Tour-edit operator: relocate a sub-segment within the permutation | [[concepts/C-011-metaheuristic-local-search-routing]] |
| PSO | Particle Swarm Optimization | [[C-011-metaheuristic-local-search-routing]] *(comparison)* |
| BO | Bayesian Optimization | [[C-014-cma-es-and-evolution-strategies]] *(comparison)* |
| CP | Constraint Programming | [[concepts/C-009-constraint-programming-cp-sat]] |
| CP-SAT | OR-Tools' hybrid CP + SAT solver | [[concepts/C-009-constraint-programming-cp-sat]] |
| SAT | Boolean satisfiability problem | [[concepts/C-009-constraint-programming-cp-sat]] |
| NSGA-II | Non-dominated Sorting Genetic Algorithm II (multi-objective Pareto GA) | [[C-009-constraint-programming-cp-sat]] |

---

## Statistical / model

| abbr | meaning | primary node |
|---|---|---|
| MSE | Mean Squared Error (Ch3 reconstruction metric) | H-021-ch3-greedy-baseline |
| BLAS | Basic Linear Algebra Subprograms | L-007-appcontrol-blocks-entire-sci-python-stack |
| ML | Machine Learning | [[C-009-constraint-programming-cp-sat]] *(strategic mention)* |
| RL | Reinforcement Learning | H-037-ch2-easy-memetic-ga *(strategic mention)* |
| DL | Deep Learning | [[C-009-constraint-programming-cp-sat]] *(strategic mention)* |
| Pareto | Set of non-dominated trade-offs (orbital-element / dV) | T-009-single-impulse-knob-pareto-is-model-bound |
| Tsiolkovsky | Rocket equation `Δv = v_e · ln(m_0 / m_f)` | H-009-ch1-advanced-infra |

---

## Software / external tools

| abbr | meaning | primary node |
|---|---|---|
| heyoka | Adaptive Taylor-series ODE integrator (used for BCP propagation) | [[C-001-cr3bp-and-bicircular-problem]] |
| pykep | Python Keplerian library (ESA / pagmo team; canonical Lambert + multi-rev) | H-015b-multirev-lambert *(we replace this in our toolchain)* |
| pygmo | Python Generic Multi-Objective optimisation library (sister to pykep) | L-007-appcontrol-blocks-entire-sci-python-stack |
| udp | User-Defined Problem (pygmo / pagmo idiom for an objective + constraints object) | H-021-ch3-greedy-baseline |
| OR-Tools | Google's open-source operations-research toolkit (host of CP-SAT) | [[C-009-constraint-programming-cp-sat]] |
| numpy | Python numerical-array library | L-007-appcontrol-blocks-entire-sci-python-stack |
| scipy | Python scientific computing library (`scipy.optimize` for NM / BFGS / DE) | [[C-014-cma-es-and-evolution-strategies]] |
| highspy | Python bindings for HiGHS solver | [[C-004-mip-and-mip-lns]] |
| miniforge | Conda variant using conda-forge by default | L-001-windows-requires-miniforge |
| App Control | Microsoft Windows code-integrity policy (blocked our `.pyd` modules) | L-007-appcontrol-blocks-entire-sci-python-stack |
| DE440 | JPL high-precision planetary ephemeris (mentioned for context, not used) | [[C-001-cr3bp-and-bicircular-problem]] *(comparison table)* |
| SPICE | NASA NAIF's astrodynamics toolkit (mentioned for context, not used) | [[C-001-cr3bp-and-bicircular-problem]] *(comparison table)* |

---

## SpOC4 / project / tooling

| abbr | meaning | primary node |
|---|---|---|
| SpOC | Space Optimisation Competition (ESA) | [[C-032-kttsp-problem]] |
| SpOC4 | The 4th edition of SpOC (this campaign's target) | `vault/index.md` |
| Optimise | The ESA submission portal for SpOC4 | O-005-ch1-instance-sizes-corrected |
| GTOC | Global Trajectory Optimisation Competition (sibling competition; comparison reference) | [[C-014-cma-es-and-evolution-strategies]] |
| KTTSP | Keplerian Tomato Traveling Salesperson Problem — the Ch2 time-dependent orbital ATSP (and its `.kttsp` instance format) | [[concepts/C-032-kttsp-problem]] |
| AoE | Anywhere on Earth (deadline timezone convention) | `vault/index.md` |
| ROI | Return on Investment (used in frontier-selection scoring) | `META.md §5` |
| ADR | Architecture Decision Record | L-003-tier1-code-hygiene |

---

## Domain-specific scoring / state (Ch2 + Ch3)

| abbr | meaning | primary node |
|---|---|---|
| n_visited | # cities visited in a Ch2 partial tour | H-016-beam-search-easy |
| n_exc | # legs counted as "exceptions" (dV in regular-cap..hard-cap range) | H-031-ch2-easy-mip |
| dv_max_m_s | Per-leg regular dV cap (Ch2: 100 m/s) | E-034-ch2-easy-continuous-time-probe |
| dv_exception_m_s | Per-leg hard dV cap (Ch2: 600 m/s) | E-034-ch2-easy-continuous-time-probe |
| n_exceptions | Total exception-count cap per tour (Ch2: 5) | E-034-ch2-easy-continuous-time-probe |
| max_time_days | Total mission-time cap (Ch2 easy: 200 d) | H-031-ch2-easy-mip |
| min_tof_days | Per-leg minimum TOF (Ch2 easy: 0.001 d) | E-034-ch2-easy-continuous-time-probe |
| mtime | Mission time so far (running) | H-016-beam-search-easy |
| tomato | A target asteroid in Ch2 (instance-language quirk) | [[C-032-kttsp-problem]] |
| viol | Constraint violation (sum of exceedances + counts × penalties; GA fitness term) | H-037-ch2-easy-memetic-ga |
| prefix | "Feasible-prefix length" — # legs feasible before first violation in chromosome decoding | H-037-ch2-easy-memetic-ga |
| MSE bound | Ch3 reconstruction tolerance (≤ 0.05) | [[O-001-spoc4-problem-grounding]] |

---

## Maintenance

This file is **tier-1 active reading** (see `META.md §14`) — it
should be loaded at every session resume. When introducing a
new acronym in any vault node, add a row here in the same edit
(part of the same commit). Pull-request-style discipline: if the
new acronym appears in a commit, this file should appear in the
same commit.

When in doubt, prefer **expanding on first use** in a node body
and adding the acronym here on second use. Single-use acronyms
in long-form prose may stay un-listed; recurring ones must be
documented.
