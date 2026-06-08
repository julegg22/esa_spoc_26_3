---
id: C-026
type: concept
status: confirmed
tags: [optimization, dp, shortest-path, time-coupled, ch2, breakthrough]
scope: optimization/exact-or-discrete
confidence: high
created: 2026-06-05
sources:
  - "Cordeau, Laporte, Mercier — A unified tabu search heuristic for vehicle routing problems with time windows (J Oper Res Soc, 2001)"
  - "Pesant et al. — An exact constraint logic programming algorithm for the TSP with TWs (Transp Sci, 1998)"
  - "Ahuja, Magnanti, Orlin — Network Flows (textbook, time-expanded graphs)"
related: ["[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-012-earliest-feasible-tof]]", "[[E-030-ch2-dijkstra-bank-perm]]", "[[foundation-then-search-methodology]]"]
---

# C-026 — Forward DP / shortest path on time-expanded graph

*The technique that broke Ch2 small from 142.92 → 126.43 d in one
session. The most powerful tool we have for time-coupled routing.*

## Definition

For a **fixed visit-order permutation** π and a discretized time axis
(buckets of size Δt), build a directed acyclic graph (DAG) whose nodes
are states `(step k, time bucket t, exceptions used e)`. Edges encode
feasible transfers between consecutive nodes in π:

- **cheap edge** from `(k, t, e)` to `(k+1, t+ceil(tof/Δt), e)` if
  `Lambert(π[k] → π[k+1], dep=t·Δt, tof) ≤ dv_thr` for the cheapest
  feasible tof at this t.
- **exception edge** from `(k, t, e)` to `(k+1, t+ceil(tof/Δt), e+1)`
  if e < n_exc, using the cheapest exc-feasible tof.
- **wait edges** (idle): `(k, t, e) → (k, t+1, e)` — encoded
  implicitly by enumerating dep buckets `t' ≥ t` instead of t alone.

**Forward DP** propagates reachability through this DAG in a single
pass over steps. The minimum t at sink `(n_legs, ?, e ≤ n_exc)` is
the provable global minimum makespan on permutation π under the
chosen discretization.

This is provably the optimum (within Δt-precision) — no metaheuristic
local optima, no SA escape problems. Greedy chronological walkers
(walk_perm_chrono) can be arbitrarily far from this optimum because
they commit to the earliest-feasible tof per leg without lookahead.

## Why it matters here

**The decisive breakthrough** of the Ch2-small attack:

| Evaluator | Bank-perm mk |
|---|---|
| walk_perm_chrono (greedy) | 142.89 d |
| walk + SLSQP polish | 142.29 d |
| DP on ultrafine grid (0.05 d × 0.05 d tof) | **126.43 d** |

A **-15.86 d single-step improvement** with no perm change — just
correcting the evaluator. See [[foundation-then-search-methodology]].

## Mechanics

For Ch2 small (n=49, n_exc=5, T=4000 t-buckets):
- State space: 49 × 4000 × 6 = 1.18 M states
- Edges from each state: up to 2 × (4000 − t) (cheap + exc, all
  dep_buckets ≥ t). After "min arrival per outgoing edge type" reduction,
  ~2-200 edges per state.
- Total ops: ~10-30 M in numba-JIT'd code; **~2.5 s on 1 core**.

### Critical implementation detail (sub-quantum tofs)

The DP grid quantizes ALL operations to Δt. To recover sub-quantum
precision, store the **actual tof value** per (i, j, dep_bucket) cell
(from Lambert precompute), not just `ceil(tof/Δt)`. Reconstruct
schedule using actual tofs; departure times remain at Δt resolution.
Error: ≤ Δt per leg. Cumulative error ≤ n_legs × Δt / 2.

### Numba JIT speedup

Pure Python: ~220 s per DP eval. Numba `@njit(cache=True)`: 2.5-3 s.
**80× speedup**, makes DP-based ALNS feasible. See [[C-029]].

## In practice

- `scripts/ch2_dp_numba.py` — the canonical numba DP implementation,
  reusable across small/medium instances.
- `scripts/ch2_e527_dijkstra_ultrafine.py` — single-perm DP on bank,
  reads `/tmp/ch2_small_tcoupled_ultrafine.npz` (the precomputed
  Lambert min-tof table).
- `scripts/ch2_e529_dp_alns.py` — DP-ALNS combining DP-eval with
  SA-driven ALNS perm search.

## Scaling pitfalls

1. **Grid mismatch (the E-541 trap)**: a Δt too coarse for the
   instance scale gives DP results WORSE than walk_perm_chrono. See
   [[C-031]]. Medium at Δt=0.5 d gave 380 d on bank; Δt=0.1 d gave
   228.97 d. Validate Δt scales appropriately for the instance.
2. **Per-pair vs per-leg precompute**: the Lambert table cost scales
   as O(n² · T · tof_grid). For large (n=1051), full table is
   intractable. Workarounds: per-leg fine precompute on bank's pairs
   only (E-540, 13 min) or curated pair set (E-542). See [[C-030]]
   for the per-pair-keyed organization.

## References

- E-030 (ch2-dijkstra-bank-perm) — first successful DP on small bank.
- E-541 (medium DP on fine table) — the −45 d jump on medium.
- M-general-foundation-then-search.md — the meta-methodology this
  technique anchors.
