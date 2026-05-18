---
id: ABBREVIATIONS
type: index
updated: 2026-05-01T23:50:00+02:00
tags: [glossary, abbreviations, reference]
---

# Abbreviation index

Single source of truth for the acronyms and abbreviations that
appear across vault entries, hypotheses, scripts, and commit
messages. Each row links to the **primary explanation** (the
node where the term is properly defined or first heavily used).

**Maintenance**: update this file whenever a new acronym is
introduced. See `META.md §3` for the discipline.

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
| BCP | Bicircular Problem (Earth + Moon + Sun, restricted 4-body) | [[concepts/C-006-bicircular-problem]] |
| CR3BP | Circular Restricted 3-Body Problem (Earth + Moon, autonomous) | [[concepts/C-006-bicircular-problem]] |
| BVP | Boundary Value Problem (Lambert is a 2-point BVP) | [[concepts/C-001-lambert-two-point-bvp]] |
| IVP | Initial Value Problem (BCP propagation is an IVP) | [[concepts/C-006-bicircular-problem]] |
| ODE | Ordinary Differential Equation (heyoka integrates ODEs) | [[concepts/C-006-bicircular-problem]] |
| SOI | Sphere of Influence (gravitational dominance boundary) | [[concepts/C-003-sphere-of-influence-patched-conics]] |
| LOI | Lunar Orbit Insertion (capture burn at Moon-relative periapsis) | [[concepts/C-005-lunar-orbit-insertion]] |
| TOF | Time of Flight (transfer arc duration) | [[concepts/C-001-lambert-two-point-bvp]] |
| GTO | Geostationary Transfer Orbit (mentioned for departure-energy context) | various Ch1 H |
| LEO | Low Earth Orbit | various Ch1 H |
| L1, L2, L3, L4, L5 | Lagrangian / libration points (CR3BP equilibria) | [[concepts/C-006-bicircular-problem]] |
| N-body | Many-body gravitational problem (full simulation) | [[concepts/C-006-bicircular-problem]] |
| dV / ΔV | Delta-V (impulsive velocity change) | [[concepts/C-001-lambert-two-point-bvp]] |
| v_inf | Hyperbolic excess velocity (asymptotic speed at infinity from secondary) | [[concepts/C-004-hyperbolic-flyby-v-infinity]] |
| r_peri | Periapsis radius (closest approach to gravitating body) | [[concepts/C-004-hyperbolic-flyby-v-infinity]] |
| μ (mu) | Gravitational parameter `G·M`; per body: `μ_E`, `μ_M`, `μ_S` | [[concepts/C-006-bicircular-problem]] |

---

## Orbital elements (Keplerian)

| abbr | meaning | primary node |
|---|---|---|
| a | Semi-major axis | [[concepts/C-001-lambert-two-point-bvp]] |
| e | Eccentricity | [[concepts/C-001-lambert-two-point-bvp]] |
| i | Inclination | [[concepts/C-001-lambert-two-point-bvp]] |
| Ω (raan) | Right Ascension of Ascending Node | [[concepts/C-001-lambert-two-point-bvp]] |
| ω (argp) | Argument of Periapsis | [[concepts/C-001-lambert-two-point-bvp]] |
| ν (nu) | True anomaly | [[concepts/C-001-lambert-two-point-bvp]] |
| e_idx, l_idx | Indices into Earth-orbit / Moon-orbit catalogues for Ch1 Adv | [[hypotheses/H-009-ch1-advanced-infra]] |

---

## Synodic-frame normalisation (BCP units)

| abbr | meaning | primary node |
|---|---|---|
| L_SI | Earth-Moon distance ≈ 384 400 km (length unit) | [[concepts/C-006-bicircular-problem]] |
| T_SI | Synodic time unit `1/ω_EM` (≈ 4.348 d) | [[concepts/C-006-bicircular-problem]] |
| V_SI | `L_SI / T_SI` (synodic velocity unit) | [[concepts/C-006-bicircular-problem]] |
| MU_BCP | Mass parameter `μ_M / (μ_E + μ_M)` for BCP non-dim | [[concepts/C-006-bicircular-problem]] |
| ω_EM | Earth-Moon mean angular velocity | [[concepts/C-006-bicircular-problem]] |

---

## Optimisation methods and solvers

| abbr | meaning | primary node |
|---|---|---|
| LP | Linear Programming | [[concepts/C-002-highs-mip-solver]] |
| MIP / MILP | (Mixed-)Integer Linear Programming | [[concepts/C-002-highs-mip-solver]] |
| IPM | Interior Point Method (LP / convex algorithm) | [[methodology/M-005-cut-engagement-threshold-scales-with-instance-size]] |
| HiGHS | "High performance Software for Linear programming" — open-source LP/MIP solver | [[concepts/C-002-highs-mip-solver]] |
| TSP | Traveling Salesperson Problem | [[hypotheses/H-031-ch2-easy-mip]] |
| ATSP | Asymmetric TSP (direction-dependent costs) | [[hypotheses/H-031-ch2-easy-mip]] |
| MTZ | Miller-Tucker-Zemlin (subtour elimination via time variables) | [[hypotheses/H-031-ch2-easy-mip]] |
| DFJ | Dantzig-Fulkerson-Johnson (subtour elimination via lazy cuts) | [[hypotheses/H-031-ch2-easy-mip]] |
| LNS | Large Neighborhood Search (ruin + recreate metaheuristic) | [[hypotheses/H-017a-lns-easy]] |
| SA | Simulated Annealing (Metropolis acceptance) | [[hypotheses/H-035-ch2-easy-sa-lns-with-precomp]] |
| GA | Genetic Algorithm (population + crossover + mutation) | [[hypotheses/H-037-ch2-easy-memetic-ga]] |
| MA | Memetic Algorithm (GA + inner local search) | [[concepts/C-010-memetic-algorithm]] |
| DE | Differential Evolution (vector-difference mutation) | [[concepts/C-009-differential-evolution]] *(disambiguate from "DE440" ephemeris)* |
| CMA-ES | Covariance Matrix Adaptation Evolution Strategy | [[concepts/C-009-differential-evolution]] *(comparison table)* |
| NM | Nelder-Mead (simplex local search) | [[methodology/M-014-multi-start-refinement-as-artifact-resolver]] |
| BFGS | Broyden-Fletcher-Goldfarb-Shanno (quasi-Newton local search) | [[experiments/E-034-ch2-easy-continuous-time-probe]] |
| L-BFGS-B | Limited-memory BFGS with Bounds (scipy default for bounded smooth optimisation) | [[concepts/C-009-differential-evolution]] |
| PMX | Partial-Matched Crossover (permutation crossover for GA) | [[concepts/C-010-memetic-algorithm]] |
| BLX-α | Blend Crossover with parameter α (real-valued GA crossover) | [[hypotheses/H-037-ch2-easy-memetic-ga]] |
| 2-opt | Tour-edit operator: reverse a sub-segment of the permutation | [[concepts/C-010-memetic-algorithm]] |
| Or-opt | Tour-edit operator: relocate a sub-segment within the permutation | [[hypotheses/H-036-ch2-easy-beam-recreate-lns]] |
| PSO | Particle Swarm Optimization | [[concepts/C-010-memetic-algorithm]] *(comparison)* |
| BO | Bayesian Optimization | [[concepts/C-009-differential-evolution]] *(comparison)* |
| CP | Constraint Programming | [[concepts/C-011-cp-sat]] |
| CP-SAT | OR-Tools' hybrid CP + SAT solver | [[concepts/C-011-cp-sat]] |
| SAT | Boolean satisfiability problem | [[concepts/C-011-cp-sat]] |
| NSGA-II | Non-dominated Sorting Genetic Algorithm II (multi-objective Pareto GA) | [[methodology/M-015-cardinality-vs-constraint-satisfaction-framing]] |

---

## Statistical / model

| abbr | meaning | primary node |
|---|---|---|
| MSE | Mean Squared Error (Ch3 reconstruction metric) | [[hypotheses/H-021-ch3-greedy-baseline]] |
| BLAS | Basic Linear Algebra Subprograms | [[lessons/L-007-appcontrol-blocks-entire-sci-python-stack]] |
| ML | Machine Learning | [[methodology/M-015-cardinality-vs-constraint-satisfaction-framing]] *(strategic mention)* |
| RL | Reinforcement Learning | [[hypotheses/H-037-ch2-easy-memetic-ga]] *(strategic mention)* |
| DL | Deep Learning | [[concepts/C-011-cp-sat]] *(strategic mention)* |
| Pareto | Set of non-dominated trade-offs (orbital-element / dV) | [[takeaways/T-009-single-impulse-knob-pareto-is-model-bound]] |
| Tsiolkovsky | Rocket equation `Δv = v_e · ln(m_0 / m_f)` | [[hypotheses/H-009-ch1-advanced-infra]] |

---

## Software / external tools

| abbr | meaning | primary node |
|---|---|---|
| heyoka | Adaptive Taylor-series ODE integrator (used for BCP propagation) | [[concepts/C-006-bicircular-problem]] |
| pykep | Python Keplerian library (ESA / pagmo team; canonical Lambert + multi-rev) | [[hypotheses/H-015b-multirev-lambert]] *(we replace this in our toolchain)* |
| pygmo | Python Generic Multi-Objective optimisation library (sister to pykep) | [[lessons/L-007-appcontrol-blocks-entire-sci-python-stack]] |
| udp | User-Defined Problem (pygmo / pagmo idiom for an objective + constraints object) | [[hypotheses/H-021-ch3-greedy-baseline]] |
| OR-Tools | Google's open-source operations-research toolkit (host of CP-SAT) | [[concepts/C-011-cp-sat]] |
| numpy | Python numerical-array library | [[lessons/L-007-appcontrol-blocks-entire-sci-python-stack]] |
| scipy | Python scientific computing library (`scipy.optimize` for NM / BFGS / DE) | [[concepts/C-009-differential-evolution]] |
| highspy | Python bindings for HiGHS solver | [[concepts/C-002-highs-mip-solver]] |
| miniforge | Conda variant using conda-forge by default | [[lessons/L-001-windows-requires-miniforge]] |
| App Control | Microsoft Windows code-integrity policy (blocked our `.pyd` modules) | [[lessons/L-007-appcontrol-blocks-entire-sci-python-stack]] |
| DE440 | JPL high-precision planetary ephemeris (mentioned for context, not used) | [[concepts/C-006-bicircular-problem]] *(comparison table)* |
| SPICE | NASA NAIF's astrodynamics toolkit (mentioned for context, not used) | [[concepts/C-006-bicircular-problem]] *(comparison table)* |

---

## SpOC4 / project / tooling

| abbr | meaning | primary node |
|---|---|---|
| SpOC | Space Optimisation Competition (ESA) | [[observations/O-002-ch2-keplerian-tomato-tsp]] |
| SpOC4 | The 4th edition of SpOC (this campaign's target) | `vault/index.md` |
| Optimise | The ESA submission portal for SpOC4 | [[observations/O-005-ch1-instance-sizes-corrected]] |
| GTOC | Global Trajectory Optimisation Competition (sibling competition; comparison reference) | [[concepts/C-009-differential-evolution]] |
| KTTSP | Keplerian Tomato TSP — the Ch2 problem-instance file format | [[observations/O-002-ch2-keplerian-tomato-tsp]] |
| AoE | Anywhere on Earth (deadline timezone convention) | `vault/index.md` |
| ROI | Return on Investment (used in frontier-selection scoring) | `META.md §5` |
| ADR | Architecture Decision Record | [[lessons/L-003-tier1-code-hygiene]] |

---

## Domain-specific scoring / state (Ch2 + Ch3)

| abbr | meaning | primary node |
|---|---|---|
| n_visited | # cities visited in a Ch2 partial tour | [[hypotheses/H-016-beam-search-easy]] |
| n_exc | # legs counted as "exceptions" (dV in regular-cap..hard-cap range) | [[hypotheses/H-031-ch2-easy-mip]] |
| dv_max_m_s | Per-leg regular dV cap (Ch2: 100 m/s) | [[experiments/E-034-ch2-easy-continuous-time-probe]] |
| dv_exception_m_s | Per-leg hard dV cap (Ch2: 600 m/s) | [[experiments/E-034-ch2-easy-continuous-time-probe]] |
| n_exceptions | Total exception-count cap per tour (Ch2: 5) | [[experiments/E-034-ch2-easy-continuous-time-probe]] |
| max_time_days | Total mission-time cap (Ch2 easy: 200 d) | [[hypotheses/H-031-ch2-easy-mip]] |
| min_tof_days | Per-leg minimum TOF (Ch2 easy: 0.001 d) | [[experiments/E-034-ch2-easy-continuous-time-probe]] |
| mtime | Mission time so far (running) | [[hypotheses/H-016-beam-search-easy]] |
| tomato | A target asteroid in Ch2 (instance-language quirk) | [[observations/O-002-ch2-keplerian-tomato-tsp]] |
| viol | Constraint violation (sum of exceedances + counts × penalties; GA fitness term) | [[hypotheses/H-037-ch2-easy-memetic-ga]] |
| prefix | "Feasible-prefix length" — # legs feasible before first violation in chromosome decoding | [[hypotheses/H-037-ch2-easy-memetic-ga]] |
| MSE bound | Ch3 reconstruction tolerance (≤ 0.05) | [[observations/O-006-ch3-luna-tomato-advertising-grounding]] |

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
