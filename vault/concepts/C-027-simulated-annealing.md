---
id: C-027
type: concept
status: confirmed
tags: [optimization, metaheuristic, sa, mcmc, ch2]
scope: optimization/metaheuristic
confidence: high
created: 2026-06-07
sources:
  - "Kirkpatrick, Gelatt, Vecchi — Optimization by Simulated Annealing (Science, 1983)"
  - "Černý — Thermodynamical approach to the travelling salesman problem (J Optim Theory Appl, 1985)"
related: ["[[C-011-metaheuristic-local-search-routing]]", "[[C-028-adaptive-large-neighborhood-search]]", "[[E-032-ch2-dp-alns]]"]
---

# C-027 — Simulated Annealing

*The acceptance criterion at the heart of every metaheuristic we
deploy. Subtle implementation details matter — see "cooling schedule
trap" below.*

## Definition

Simulated annealing (SA) is a stochastic acceptance rule for moves in
a local-search trajectory:

```
Δ = f(new) − f(current)
if Δ < 0:                 accept  (uphill direction = minimization)
elif rand() < exp(−Δ/T):  accept  (uphill, with probability)
else:                     reject
```

The **temperature T** starts high (most uphill moves accepted) and
**cools** toward zero over the search (only downhill moves accepted).
By the time T ≈ 0, the chain behaves as pure greedy descent — but
along a trajectory shaped by the high-T exploration. Theoretical
result (Geman & Geman, 1984): with cooling slower than `T₀ / log(k)`,
SA converges to the global optimum in probability.

In practice, geometric cooling `T(k) = T₀ · α^k` for α ∈ [0.99, 0.9999]
is universal. The constraint: high enough T at start to escape the
seed basin, low enough at end to lock in the best found.

## Why it matters here

SA is the **acceptance criterion** in:
- All our ALNS chains (E-529, E-530, E-538, E-543)
- The destroy-repair perm search on small + medium

Picking SA parameters (T₀, α, cooling timing) makes or breaks the
search:
- T₀ too low → chain stuck in seed basin (0 bankings, see E-538/E-538b)
- T₀ too high → chain accepts uphill freely, never converges
- Cooling tied to wrong counter → schedule decoupled from progress
  (the **E-538 bug**, see below)

## Mechanics for our DP-ALNS

We use:
- **T₀ = 5–8** (early E-529 used 3.0, later runs 5–8 for diverse seeds)
- **α = 0.999 or 0.99995** per **iteration** (not per banked, not per
  DP-feasible). See "trap" below.
- Reseed schedule: every 6 h, if `global_bank < state - 0.1 d`, adopt
  global bank as state and reset T → T₀. Lets late-arriving information
  from sister chains restart exploration.

### The "cooling tied to wrong counter" trap

In E-538 the line `sa_temp *= SA_DECAY` was placed AFTER the
DP-infeasibility `continue`. Result: T only cooled on DP-feasible
iterations (~1.1 % of iters). After 30k iters / 344 DP_ok:
`T = 5 × 0.999^344 = 3.54`. The chain was still hot when we expected
it to be cold.

**Fix (E-538b)**: move `sa_temp *= SA_DECAY` to top of the iteration
loop, before any `continue`. Now T cools per wall-iter, which scales
with wall-clock (since iter rate is roughly constant).

**Lesson**: always couple SA cooling to the operation that consumes
wall time. If iteration time varies wildly (due to DP-feasibility,
solver timeouts, etc.), cool per `time.time()` instead.

## In practice

- `scripts/ch2_e529_dp_alns.py` — SA_T0=3.0, decay=0.999 per iter.
  Worked productively on small (10 bankings in 12.5h burst).
- `scripts/ch2_e538b_dp_alns_lkh_seed.py` — SA_T0=8.0, decay=0.99995
  per iter. Hot start for diverse-basin exploration.
- `scripts/ch2_e543_medium_dp_alns.py` — medium analogue.

## When SA fails

Three patterns observed:

1. **Stuck at seed**: T₀ too low → can't escape initial basin.
   Symptom: best mk == seed mk after many iters. Fix: raise T₀.

2. **Random walk forever**: cooling too slow → never locks in.
   Symptom: best mk reached early then no further improvement.
   Fix: faster decay (α closer to 0.99).

3. **Basin saturation**: SA can't bridge between deep basins.
   Symptom: bank seed and LKH-3 seed both stuck at their respective
   mks even after 5+ h of search (E-538b confirmed). Fix: crossover
   operators or much hotter restart cycles. SA alone isn't sufficient
   when basins have large uphill barriers.

## References

- E-029, E-032 — first productive SA-ALNS runs.
- E-538/E-538b — the cooling-trap diagnosis.
