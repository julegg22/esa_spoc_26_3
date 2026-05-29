---
date: 2026-05-29
tags: [concept, ch1, pygmo, design, pl2pl, standard-tool, L1-L2]
status: ACTIVE DESIGN — implementation for Option B per user 2026-05-29
---
# C-025 — Per-pair pygmo UDP solver design (the standard approach)

## Context

User direction 2026-05-29: "go for option B. We have come from almost 0
to 215k by cleaning up bugs, and this will continue. It is not realistic
that other groups implemented real research — there must be a
sophisticated yet reasonable standard approach if done right."

Investigation of `pykep.trajopt` confirms: **the standard approach is
pygmo UDPs** (e.g., `pl2pl_N_impulses`, `mga`, `mga_1dsm`) wrapped around
the trajectory physics + optimized by `pygmo` algorithms (CMA-ES, DE,
BiteOpt, NSGAII). Source: Izzo, D. *Global optimization and space pruning
for spacecraft trajectory design.* (2010). Cited by `pykep.trajopt`
docstrings — Dario Izzo is ESA's chief space mission designer and author
of pykep itself.

Our problem doesn't fit `pl2pl_N_impulses` directly (BCP physics, Earth
orbit not Earth planet, Moon orbit not Moon planet, (a,e,i)-only match).
But the *pattern* — UDP + CMA-ES — is exactly right and we should mirror it.

## The proper UDP design

**Decision vector** (14 dofs per pair):
```
[raan_e, argp_e, ea_dep, t0, T1, T2, dv0_x, dv0_y, dv0_z, dv1_x, dv1_y, dv1_z, t2_d, t_max_d]
```

Where:
- `raan_e, argp_e, ea_dep` — initial state on Earth orbit (3 free dofs per spec)
- `t0` — synodic epoch (1 dof)
- `T1, T2` — leg times (2 dofs)
- `dv0_3` — first impulse vector (3 dofs)
- `dv1_3` — second impulse vector (3 dofs)
- `dv2` is COMPUTED via `solve_arrival_eccentric` (zero dofs added)

**Bounds**:
- Angles in [0, 2π]
- T1 in [3, 30] days, T2 in [0, 10] days
- dv0, dv1 in [-5000, 5000] m/s each component (= ±5 km/s)

**Seeded population**: 
- Pop 0: physics-informed seed (Hohmann dv0, dv1=0)
- Pop 1-N: random within bounds

**Fitness** (single-objective minimization):
```python
def fitness(x):
    raan_e, argp_e, ea_dep, t0, T1, T2, dv0x, dv0y, dv0z, dv1x, dv1y, dv1z = x
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, t0, [[dv0x,dv0y,dv0z], [dv1x,dv1y,dv1z], [0,0,0]], [T1, T2])
    if len(pv_arr) == 0:  # impact
        return [10000.0]  # large penalty
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return [10000.0]
    dv2, _ = res
    dv_total = (norm(dv0) + norm(dv1) + norm(dv2)) * V
    return [dv_total]  # minimize total dv (= maximize mass via rocket eq)
```

**Optimizer**: `pygmo.cmaes(gen=100, force_bounds=True)` with pop ~25.

Per-pair cost: ~2500 evals × ~0.5 sec/eval = 1250 sec ≈ 21 min per pair.
For 400 pairs / 8 workers = ~17.5 hours wall (overnight).

## Why this should work where my previous attempts failed

**My DC attempts** kept getting stuck in local minima because:
- Position-match DC has 3-eqn 3-unknown determined system
- No global optimization
- Starting from Hohmann seed only

**This pygmo UDP**:
- Global optimization (CMA-ES)
- Population covers multiple basins
- Adaptive covariance handles parameter scale differences
- Bounds enforcement prevents wandering
- Multi-start via random initial population

**Pygmo also handles**:
- Constraints (we don't need any — solve_arrival absorbs orbit match)
- Multi-objective (single-obj for now)
- Parallel evaluation via `pg.bfe` (batch fitness evaluation)

## Per-lever mapping (from A-2026-05-29 coherent model)

| Lever | This solver addresses |
|---|---|
| L1 (smart pair matching) | After per-pair optimization, Hungarian re-picks |
| L2 (B1 done right: apolune plane change) | CMA-ES finds the apolune-burn configuration naturally |
| L3 (crack 104 unused pairs) | Same UDP applied to unused-pair candidates |
| L5 (NLP joint dv optimization) | CMA-ES IS the joint NLP |

Expected combined gain: per the coherent model, +167k kg to reach
impulsive ceiling 382k.

## Implementation plan

1. **`src/esa_spoc_26/ch1_pair_udp.py`** — pygmo UDP class
2. **`scripts/ch1_pair_optimize.py`** — per-pair CMA-ES + result writer
3. **Validate** on 10 representative pairs (smoke test, ~3.5 hours)
4. **If validation gives 600+ kg avg for hard pairs**: full bank pass
5. **Iterate**: rebank, identify worst pairs, re-optimize with bigger budget

## Anti-oscillation discipline

Per A-2026-05-29:
- **Validate before scaling**: 10 pairs first, compare to per-class ceiling
- **If actual << prediction**: implementation bug, debug rather than pivot
- **Measure & report**: each cycle prints actual vs predicted per pair

## Cross-references
- A-2026-05-27 — original audit
- A-2026-05-29 — coherent physics model (lever-to-gap map)
- C-022 — current production architecture
- pykep.trajopt._pl2pl_N_impulses — Izzo 2010 reference implementation
