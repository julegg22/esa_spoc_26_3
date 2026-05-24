---
id: H-011
type: hypothesis
status: draft
tags: [ch1, trajectory, tier-3, stm, jacobian, heyoka, variational]
parent: "[[lessons/L-012-solver-assumption-audit-before-research-grade-verdict]]"
created: 2026-05-24
priority: 3
mode: research

claim: >
  Using heyoka's variational-equation feature to compute the State
  Transition Matrix (STM) gives scipy a true analytic Jacobian for
  the trajectory residuals. Convergence becomes O(quadratic) instead
  of O(linear), the basin of attraction widens 10-100×, and the
  solver tolerates initial guesses that finite-difference Jacobian
  rejects.

falsifiable_prediction: >
  STM-based DC unlocks an additional ~20% of the hard pairs (where
  finite-difference DC fails to converge from any Lambert seed),
  contributing +30,000-50,000 kg to the bank. Convergence rate for
  formerly-converging pairs improves 5-10× in iteration count
  (matters for the per-pair speed cost).

estimated_effort_h: 16-24
expected_points: 3-5 (incremental, complements WSB)
---

# H-011 — STM-based differential corrector for Ch1 trajectory

## Background

Standard mission design uses the STM (state transition matrix)
∂x(T) / ∂x(0) — propagated alongside the spacecraft state via
variational equations of the dynamics. This gives an exact analytic
Jacobian of the trajectory's final state with respect to the
initial state perturbations.

scipy's least_squares with `jac="2-point"` (finite difference)
costs 6 propagations per Jacobian column × 6 columns = 36
propagations per iteration. STM gives the same info in 1
propagation (the variational equations are stacked with the state).

## Speedup analysis

- Per-iteration: 36 → 1 propagations (36× cheaper per iteration).
- Iteration count: 5-10× fewer (analytic Jacobian gives Newton-like
  convergence).
- Combined: 180-360× speedup per DC convergence.

For our 100s-per-pair sweep, that's ~0.5s per pair → entire 160k
pair space solvable in 8h!

## Why we haven't done this yet

heyoka supports variational equations but requires care:
- Need to define variational symbols alongside state symbols.
- The integrator becomes 6+36=42-dim (state + 6×6 STM).
- API: `taylor_adaptive` with `compact_mode=True`, then accessing
  the variational outputs.
- Documentation is sparse for nested variational use cases.

## Implementation phases

### Phase 1: STM propagator (~6-8h)
Build a `propagate_with_stm(pv0, t0, DVs, Ts) -> (pv_end, STM)`
using heyoka's variational features. Validate STM accuracy vs
finite-difference.

### Phase 2: STM-DC wrapper (~4-6h)
Replace `least_squares` calls with manual Newton step using STM.
Compare convergence rates on test pairs.

### Phase 3: Integrate into production sweep (~4h)
Drop into existing pipeline; rebenchmark per-pair time.

### Phase 4: Expand coverage (~4h)
Re-run on FULL 160k pair space (now feasible). Hungarian re-bank.

## Risk

- heyoka variational API may not support our setup natively. Could
  require manual symbolic differentiation of BCP equations (more
  work).
- STM accuracy degrades over long TOFs in chaotic regions (near
  L1/L2). May need to multi-shoot to maintain conditioning.

## Decision criteria

Apply AFTER WSB (H-009) is done OR if WSB is too risky. The STM
approach is "incremental but reliable" — unlocks more pairs and
makes the WHOLE solver dramatically faster.

For ambition target (rank 1+): STM enables FULL 160k pair sweep,
which finds the absolute optimal Hungarian assignment. That's the
upper bound of what's possible without WSB.
