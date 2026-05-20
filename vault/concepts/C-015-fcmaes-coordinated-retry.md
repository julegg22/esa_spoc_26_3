---
id: C-015
type: concept
status: confirmed
tags: [optimization, evolutionary, fcmaes, ch2, tool, parallel]
scope: optimization/global + tooling
confidence: high
created: 2026-05-20
sources:
  - "fcmaes — github.com/dietmarwo/fast-cma-es (Dietmar Wolz)"
  - "Wolz, Practical guide to solve SpOC/GTOC problems with fcmaes"
related: ["[[C-014-cma-es-and-evolution-strategies]]", "[[C-016-argsort-permutation-encoding]]", "[[C-011-metaheuristic-local-search-routing]]"]
---

# C-015 — fcmaes coordinated retry (Wolz's SpOC/GTOC recipe)

*Primer for non-experts: the parallel-restart wrapper around CMA-ES/
DE that wins ESA orbital trajectory competitions — and almost
certainly was used by Ch2 rank-3 (the leaderboard submission helper
is literally named after this library).*

## Definition

**fcmaes** is Dietmar Wolz's optimisation library purpose-built for
the GTOC/SpOC problem class: continuous + mixed-integer trajectory
optimisation with strongly multi-modal Lambert/Keplerian
landscapes. Its key offering is not just CMA-ES itself but the
**coordinated parallel retry pattern**:

```python
from fcmaes import retry
from fcmaes.optimizer import de_cma
result = retry.minimize(
    fitness, bounds=bounds,
    optimizer=de_cma(max_evals),
    num_retries=N,         # e.g., 32–256 independent restarts
    workers=W,             # parallel processes
    value_limit=current_best,
)
```

Each retry:
1. Random initial population in the bounded domain.
2. **DE** for several generations → global exploration.
3. **CMA-ES** for refinement → local exploitation.
4. Compare against the running best (shared via inter-process state).
5. If better, retain; else drop.

The combined result is robust against local optima: many
independent searches converge to **different basins**; the best
across all is kept.

## Why it matters here

- **Strong empirical signal**: SpOC4 submission helper is named
  `fcmaes` ⇒ winners use it.
- **Wolz's domain match**: Lambert + permutation + tight horizon
  is exactly the class his library targets.
- **Our local search converged at 142.99 d across 7 methods**
  (E-018 → E-024); the remaining 31-d gap is across-basin, which
  is precisely what parallel CMA-ES restarts address.
- **No commercial-solver dependency** (unlike PWL MILP, E-024).
- **Mostly wiring**: build cost is small (a few hundred lines for
  encoding + bounds + warm-start), compute cost is hours.

## Mechanics — the standard SpOC recipe

1. Define `fitness(x)` returning a single float — penalty for
   infeasibility, makespan otherwise.
2. Define bounds as `scipy.optimize.Bounds(lo, hi)`.
3. Encode any non-continuous variables (e.g., permutations via
   [[C-016-argsort-permutation-encoding|argsort keys]]).
4. Choose optimizer: `de_cma` (default for Wolz's GTOC tutorials),
   `Bite_cpp` (BiteOpt), or `Cma_python` for plain CMA-ES.
5. `retry.minimize(...)` with N >> workers; budget in hours.
6. Optional: a small subset of populations seeded from a known
   feasible solution (warm-start).

## In practice

`src/esa_spoc_26/ch2_fcmaes.py` implements the pattern for Ch2:
- `_Ch2Problem` class with `Bounds(lo, hi)` over 145 dimensions.
- `_fitness(x)` decodes (times, tofs, perm) and returns makespan or
  penalty.
- `encode_solution()` builds an x⁰ from the banked 142.99 d
  decision vector for warm-start.
- `retry.minimize(de_cma, num_retries=32, workers=4)` is the call.

## Expected behaviour

| metric | typical SpOC use | what we set |
|---|---|---|
| Restarts | 64–512 | 32 (smoke) → 256+ for production |
| Workers | physical cores | 4 |
| Per-retry max_evals | 50 k – 500 k | 10 k (smoke) → 100 k+ production |
| Wall time | hours–days | 30 min (smoke) → 8–24 h production |

## Caveats

- The argsort permutation encoding is **continuous over discrete
  choices** — fitness has flat plateaus where the argsort doesn't
  change. CMA-ES's covariance adaptation softens this, but for very
  rugged permutation landscapes, dedicated permutation operators
  (or-opt, 2-opt) on the integer side complement the continuous
  search.
- fcmaes by default prints via `loguru`; if a worker crashes, the
  message may not reach the parent's stdout — watch the process
  state.
- The `value_limit` mechanism keeps only retries that beat the
  threshold; setting it to the current best prevents the search
  from spending time on inferior outcomes.

## References

- fcmaes repository, examples directory.
- Wolz, "How to solve GTOC11 with fcmaes" (blog/tutorial).
