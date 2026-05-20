---
id: O-009
type: observation
status: confirmed
tags: [ch2, external-intel, methodology, m-005, library-ecosystem]
source: "M-005 external intel survey 2026-05-20"
created: 2026-05-20
referenced_by: ["[[M-005-external-intel-survey]]"]
supersedes:
superseded_by:
---

# O-009 — External intel survey: ESA SpOC ecosystem, the canonical KTSP paper, and the fcmaes lineage

*Triggered by L-005 toolchain-audit + M-005 survey 2026-05-20.
First systematic application of the new methodology after the
fcmaes-by-accident discovery.*

## The eight pinned signals

### 1. Pygmo UDP IS the canonical SpOC4 interface

`reference/SpOC4/README.md` line 70 — verbatim:
> we will provide you with Python validation code for each of the
> challenges. This code includes problem definitions in the
> [Pygmo](https://esa.github.io/pygmo2/#) user-defined problem
> (UDP) format

⇒ The intended user pipeline is `pygmo.problem(...)` + `pygmo`'s
solver suite (sade, de, cmaes, pso, gaco, abc, …) + optionally
fcmaes for the heavier optimizers. Our `KTSP.fitness` interface
already conforms to pygmo's UDP convention.

### 2. Bannach, Acciarini, Izzo (IAC 2024) — THE canonical KTSP paper

["On the Keplerian TSP and VRP: Benchmarks and Encoding
Techniques"](https://openresearch.surrey.ac.uk/esploro/outputs/conferencePresentation/On-the-Keplerian-TSP-and-VRP/99927464502346)
— Bannach (ESA ACT, corresponding author `max.bannach@esa.int`),
Acciarini (ESA ACT), Izzo (ESA ACT + Univ. Surrey).

**The canonical encoding (Section 3) — time-expanded network**:
- V(G) = A × T  (Keplerian object × discrete time point)
- E_C = coasting arcs ((α, t), (α, t+dt)) — stay at body
- E_T = transfer arcs ((α, t), (β, t')) with weight w_G = Δv
- ILP variables: `x_{t,t'}^{α,β} ∈ {0,1}` per arc
- **Departure** constraint: each α visited at least once
- **Flow** constraint: at each (α, t), inflow == outflow
- **Vehicle** constraint: start at (α_s, t_0)
- Min Σ w_G(e) · x_e

**Dynamic Discretization Discovery (DDD)** (Section 5,
Boland et al. 2017):
1. Start with coarse time-interval partition Λ
2. Solve Γ_I (interval-MILP)
3. If feasible to KTSP → optimal; else refine intervals around
   violation and re-solve
4. Subtour-elimination via Dantzig-Fulkerson-Johnson on detected
   cycles

**Theorem 1**: DDD converges to optimum as dt → 0.

### 3. Solver comparison from Table 1 (Bannach et al.)

| instance |A|, |T| | Gurobi | HiGHS | Scip | CBC | OPT (Δv m/s) | beam-search-1M Δv |
|---|---|---|---|---|---|---|---|
| 5, 21 | 0.69s | 0.31s | 0.57s | 0.25s | 10 533 | 10 533 (matches OPT) |
| 10, 41 | **5.89s** | 19.56s | 150.43s | 13.66s | **25 290** | 33 515 (**32 % worse**) |
| 20, 21 | 5.73s | 8.60s | 13 100s | 5.97s | — | — |
| 20, 41 | **1 540s** | 13 100s | 15 397s | 5 833s | **96 835** | — (BW infeasible) |

⇒ **Gurobi dominates on larger instances** (8.5× faster than
HiGHS on 20, 41). **Beam search produces suboptimal Δv**
solutions or fails entirely on larger instances. **HiGHS is
feasible but slow** without DDD.

### 4. DDD reduces problem size 42-65 %

From Table 2: for 10, 41 (largest tractable plain), DDD
shrinks 59 212 vars → 20 438 (65 % reduction). Calls multiple
sub-solvers (242 for plain DDD; 13 for DDD-pc with pre-computed
cycle constraints).

### 5. Zenodo benchmark dataset

[zenodo.org/records/14850862](https://zenodo.org/records/14850862)
— 4.4 GB of `.ktsp` (continuous KTSP) and `.ektsp` (time-expanded
network) reference instances spanning Asteroid Belt and Jupiter's
Moons. Reference solutions per ESA's project page. Our Ch2
small/medium/large likely have direct counterparts here.

### 6. Past SpOC leaderboard signal

| competition | rank | team | global score |
|---|---|---|---|
| SpOC 2023 | 3 | fcmaes (Wolz) | 24 |
| SpOC3 (GECCO 2024) | 🥇 1 | **Team HRI** | **78.444** |
| SpOC3 (GECCO 2024) | 🥈 2 | fcmaes (Wolz) | 68.667 |
| SpOC3 (GECCO 2024) | 🥉 3 | Spacekangaroos | 66.555 |

⇒ **HRI (our user's affiliation) WON SpOC3.** Open question for the
user: *what method did the HRI team use?* This is institutional
intel we can directly tap.

### 7. fcmaes lineage + tutorials

- **Repo**: github.com/dietmarwo/fast-cma-es
- **Author**: Dietmar Wolz (collaborates with U. Jena on GTOC/CTOC since 2006)
- **Algorithms recommended for SpOC class**:
  - **BiteOpt** — single-thread first try
  - **CMA-ES** — <500 dimensions
  - **DE + CMA-ES (`de_cma`)** — hybrid, classic recipe
  - **SBM + DE→CMA** — parallel, best for GTOC-style scheduling
  - **MODE** — multi-objective + mixed-integer
- **Key implementation tricks** (from `Scheduling.adoc`):
  - **Numba JIT** for inner loops (450× speedup)
  - **Multi-objective formulation even for single-objective** (better diversity)
  - **Precomputed transfer tables** (we have `windows2d_small.npz` — same idea)
  - **Parallel retry** (~8-18× speedup on multicore)
- **ESA SpOC tutorial**: `ESAChallenge.adoc` covers the 2023 problem

### 8. RL via pointer networks (Vinyals et al. 2015)

ESA ACT's "Reinforcement Learning for the Keplerian TSP" project
— pointer network trained on randomly-generated target clusters,
used to **provide upper bounds for ILP branch pruning** (not
standalone). Builds on Vinyals 2015.

## Cross-validation across signals

| signal | what it points at | confidence |
|---|---|---|
| Pygmo UDP in README | pygmo/fcmaes optimizer family | very high |
| fcmaes installed in env | fcmaes was intended | very high |
| Bannach paper (Izzo co-author) | ILP + time-expanded networks + DDD | very high |
| Zenodo benchmark format | the official problem encoding | very high |
| ESA RL project | RL warm-start for ILP | medium |
| fcmaes SpOC 3rd place | metaheuristic-only is competitive but not top | high |
| HRI SpOC3 winner | something better than fcmaes alone | medium (need user) |
| Beam search suboptimal | don't rely on greedy/beam | very high |

## What this changes about our approach (T-008 revision needed)

Our current state:
- 142.99 d via **7 local-search methods** (greedy + insertion + 2-opt + Or-opt + SA + cluster-first + exception-replace)
- MILP attempt: **WRONG ENCODING** — used MTZ with arc + window selectors, not the canonical time-expanded network. HiGHS TimeLimit at 1200s without DDD.
- fcmaes attempt: **right family** but wrong scale (4 cores × 30K evals; Wolz uses 64–512 retries × hours)

**The canonical method we should be running**:
1. Build time-expanded graph G = (V_α×T, E_C ∪ E_T) per Bannach §3
2. ILP with the three constraints (Departure, Flow, Vehicle)
3. Solve with HiGHS (we don't have Gurobi)
4. Wrap in DDD: coarse Λ → solve → refine → repeat
5. Subtour elimination via Dantzig-Fulkerson-Johnson on detected cycles

This is similar to but structurally different from our ch2_milp_pwl
(which used MTZ + window-binaries, not the proper time-expanded
encoding).

**Alternative path that requires user input**: ask Julian about
HRI's SpOC3 winning approach. The HRI method (which beat fcmaes
by 14% on global score) is the most direct intel we could get and
costs zero compute time.

## Ranked tools for the canonical KTSP

| tool | role | availability |
|---|---|---|
| **HiGHS** (via highspy) | open-source MILP | ✓ installed |
| **fcmaes** (`de_cma`, BiteOpt) | metaheuristic for upper bounds + diversity | ✓ installed |
| **pygmo** | UDP interface + ESA-canonical | likely installed (used in H-002) |
| **scipy.optimize** | continuous local-NLP per leg | ✓ installed |
| Gurobi | dominant MILP solver | ✗ no licence (L-002) |
| MaxHS / Open-WBO | MaxSAT alternative to MILP | ✗ not installed |
| Bannach reference implementation | DDD + canonical encoding | unknown — check ESA repos |

## Recommendation (next decision point)

Three architecturally orthogonal paths, ranked by ROI:

1. **Ask Julian about HRI's SpOC3 method** (cost: minutes, value:
   potentially the winning recipe).
2. **Re-implement MILP with canonical Bannach encoding + DDD**
   (cost: 1-2 days build, HiGHS solver; expected: ≥ 20-30 d
   makespan improvement based on solver-comparison table).
3. **fcmaes at Wolz-scale**: 64-256 retries × 100k evals × diverse
   warm-starts (cost: hours-days; matches the rank-3 likely
   approach if HRI's exact recipe is unavailable).
