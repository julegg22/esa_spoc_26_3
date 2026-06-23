---
id: C-014
type: concept
status: confirmed
tags: [optimization, evolutionary, continuous, cma-es, ch2]
scope: optimization/evolutionary
confidence: high
created: 2026-05-20
sources:
  - "Hansen, The CMA Evolution Strategy: A Comparing Review (2006)"
  - "Auger & Hansen, A restart CMA-ES with increasing population size (IEEE CEC 2005) — BIPOP-CMA-ES"
  - "Storn & Price, Differential Evolution (J. Global Optim. 1997)"
related: ["[[C-011-metaheuristic-local-search-routing]]", "[[C-015-fcmaes-coordinated-retry]]", "[[H-003-ch2-small-lambert-metaheuristic]]"]
---

# C-014 — CMA-ES & evolution strategies for continuous optimisation

*Primer for non-experts: the "evolve a population of candidate
solutions" tool that wins many continuous global-optimisation
problems — including orbital trajectory optimisation (GTOC, SpOC).*

## Definition

**Evolution strategies (ES)** maintain a population of real-valued
candidate solutions and iteratively sample new candidates from a
multivariate-Gaussian distribution centred on the current best /
mean, then update the distribution from the better samples.

**CMA-ES** (Covariance Matrix Adaptation ES) is the canonical
modern ES:
- State: mean **μ ∈ ℝⁿ**, step-size **σ > 0**, covariance matrix
  **C ∈ ℝⁿˣⁿ**.
- Sampling: x_i ~ μ + σ · N(0, C), i = 1..λ.
- Selection: keep top μ_eff candidates.
- Adaptation: update μ toward selected mean, C toward selected
  covariance, σ via path-length heuristic.

The covariance adaptation makes CMA-ES **invariant under affine
re-scaling and rotation** of the search space — robust to
ill-conditioned objectives.

**BIPOP-CMA-ES** wraps CMA-ES with two restart strategies (small
σ vs. large σ population) to handle multi-modal objectives.

**Differential Evolution (DE)** is a simpler ES variant: x_new =
x_i + F · (x_j - x_k); accept if better. Less geometry-aware than
CMA-ES, but cheap and surprisingly effective for ruggedness.

## Why it matters here

Ch2 KTTSP is a **145-dim real-valued** problem (48 td + 48 tof + 49
permutation keys after [[C-015-fcmaes-coordinated-retry|argsort encoding]]) with a highly
non-convex Lambert-driven objective surface. Local search methods
(2-opt, Or-opt, SA, LNS) have **convergence-confirmed** at 142.99 d
across 7 methods (E-018→E-024); the remaining 31-d gap to rank-3
(111.76 d) is in **other basins**, not adjacent moves.

CMA-ES with restarts is the canonical tool for **population-based
global exploration of continuous landscapes**. Wolz's fcmaes
library (the leaderboard helper's namesake; see C-015) makes
parallel CMA-ES + DE retries the go-to recipe for SpOC-style
orbital problems.

## Mechanics for KTTSP

Decision-vector encoding:
```
x ∈ ℝ¹⁴⁵
  x[0:48]    = departure times (continuous, bounded [0, 200])
  x[48:96]   = times of flight (continuous, bounded [min_tof, 200])
  x[96:145]  = real-valued permutation keys (bounded [0, 1])
```
Fitness: decode x, evaluate official `kt.fitness`, penalise
infeasibility (large constant + per-violation magnitude).

CMA-ES sampling: each generation draws λ ≈ 4 + 3·log(n) ≈ 22 new
candidates from N(μ, σ² C) and keeps the top 11 to update μ, σ, C.

## In practice

`src/esa_spoc_26/ch2_fcmaes.py` wires `fcmaes.optimizer.de_cma`
(DE for global + CMA-ES for local) into `retry.minimize` for
parallel restarts. The 142.99 d banked solution is encoded as
a warm-start seed for one population member.

## References

- Hansen tutorial: https://arxiv.org/abs/1604.00772
- DE: Storn & Price (1997).
- ESA SpOC4 leaderboard helper named `fcmaes` ⇒ winners likely
  use Wolz's library.
