---
id: M-003
type: methodology
status: active
tags: [methodology, frontier, family-breadth]
created: 2026-05-20
related: ["[[M-002-stuck-triggers-ultrathink-reframe]]", "[[L-005-toolchain-audit-at-task-bootstrap]]", "[[M-004-convergence-watchdog-across-families]]"]
---

# M-003 — Approach-family inventory & breadth requirement

*Trigger event*: spent ~15 h on Ch2 polishing within the
**local-search-on-combinatorial-structure** family (greedy +
cluster-insertion + 2-opt + Or-opt + SA + cluster-first + MILP +
LNS), all converging at the same 142.99 d local optimum. The
**population-based evolutionary** family (CMA-ES, DE, fcmaes) —
the *canonical* tool for ESA-orbital optimisation — was not
considered until the user accidentally noticed the submission
helper was named `fcmaes`. The library was even installed in the
env from the start.

## Rule

For every open question / challenge:
1. Maintain a **family coverage table** (see schema below) in
   `open-paths.md` (or a dedicated `families.md`).
2. Before committing >1 h of compute to refining a method, verify
   that **at least 2 approach families** are *priced and ranked*
   on the frontier.
3. When a refinement is "the same but more specific", check if any
   priced family alternative offers higher ROI.

## Approach-family taxonomy (general)

| family | typical methods | when canonical |
|---|---|---|
| **exact** | MILP, CP-SAT, SAT, branch-and-bound | small/medium combinatorial; provable bounds |
| **local search** | greedy, 2-opt, Or-opt, LNS, ALNS | rugged combinatorial; warm-start-friendly |
| **annealing** | SA, ILS | escaping shallow local optima |
| **population evolutionary** | CMA-ES, BIPOP-CMA-ES, DE, GA, PSO | continuous high-dim, multi-modal |
| **problem-specific analytical** | Lambert, Hohmann, Kepler analytical | astrodynamics-canonical pieces |
| **mathematical programming** | Lagrangian, column-generation, decomposition | structured large-scale |
| **ML-based** | RL, supervised heuristics, neural | learning from solved instances |
| **hybrid / portfolio** | parallel restarts, coordinated retry, ALNS, memetic | combine the above |

## Family coverage table schema

```yaml
# open-paths.md or families.md entry per challenge
families:
  exact:
    status: tried_refuted
    methods: [E-014 CP-SAT, E-015 LP, E-018→E-021 CP-SAT v3, E-024 MILP]
    verdict: "discrete-window incompatible with NLP refinement; PWL needs Gurobi"
  local_search:
    status: tried_local-optimum
    methods: [E-022 greedy+insertion, 2-opt rounds, Or-opt, E-023 SA, E-024 exception-replace]
    verdict: "7 methods converge at 142.99d; basin tight"
  population_evolutionary:
    status: ATTEMPTED_LATE  # ← gap caught by accident
    methods: [E-025 fcmaes/CMA-ES]
    note: "fcmaes was env-installed from start; should have been first-class"
  problem_specific:
    status: tried
    methods: [pykep Lambert max_revs=20]
  ml_based:
    status: not_considered
  hybrid:
    status: partial
    methods: [find_transfer + greedy + insertion + 2-opt is hybrid LS]
```

## How this enforces breadth

At each "should I deepen X?" decision, the frontier shows the
coverage table. If, e.g., `population_evolutionary` is
"not_considered" while we're 3rd-pass refining a local-search
method, that mismatch is visible and the breadth requirement
triggers a probe of the unconsidered family.

## Concrete how-to-apply

1. **At task bootstrap**: list ALL plausible families for the
   problem class (≈ 6–8 categories from taxonomy above).
2. **Per family, write a 1-line "would this work here?"** answer.
   Dismissal needs a *reason* (e.g., "ML: no training data
   available"); else it stays open.
3. **As experiments close**: update family status (`tried` →
   `tried_refuted` / `tried_optimum` / `tried_promising` /
   `tried_partial`).
4. **Frontier breadth check** (every reprice): if ≥3 open
   hypotheses are in the same family, REQUIRE adding ≥1 from a
   different family before committing.
5. **Pair with M-004 (convergence watchdog)**.
