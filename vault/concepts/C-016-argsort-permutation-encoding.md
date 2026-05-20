---
id: C-016
type: concept
status: confirmed
tags: [optimization, encoding, permutation, ch2, evolutionary]
scope: optimization/encoding
confidence: high
created: 2026-05-20
sources:
  - "Bean, Genetic and Evolutionary Computation: Frontiers in Theory and Application (random keys encoding, 1994)"
  - "fcmaes examples — permutation problems"
related: ["[[C-014-cma-es-and-evolution-strategies]]", "[[C-015-fcmaes-coordinated-retry]]"]
---

# C-016 — Argsort (random-keys) encoding for permutations

*Primer for non-experts: how to hand a permutation problem to a
continuous-domain optimizer like CMA-ES or DE.*

## Definition

To encode a permutation `π ∈ S_n` for a real-valued optimizer:
1. Maintain n **real keys** `k[0], k[1], ..., k[n-1] ∈ ℝ` (commonly
   bounded [0, 1]).
2. Decode: `π = argsort(k)` — sort the keys, the indices give the
   permutation order.

Result: a continuous, smooth wrapping of the discrete S_n.

Properties:
- Continuous-and-smooth: small key perturbations usually leave π
  unchanged ⇒ flat plateaus.
- Crossover-friendly: real-valued GA / DE / CMA-ES operators work
  on the keys without special permutation operators.
- Lossy: many distinct (k, k') tuples decode to the same π.
- Inverse: given π, set `k[π[i]] = i/(n−1)` for i = 0..n−1.

This is sometimes called **"random keys" encoding** (Bean 1994).

## Why it matters here

Ch2's decision vector has a 49-element permutation. fcmaes /
CMA-ES / DE all operate on `ℝⁿ`; the argsort encoding makes the
permutation accessible without rewriting the optimizer.

The continuous-but-plateaued landscape interacts non-trivially
with CMA-ES:
- Inside a plateau, the gradient is 0 — but CMA-ES doesn't use
  gradients, so it relies on diversity to escape.
- The covariance adaptation captures the directions across plateau
  boundaries where π changes.

## Mechanics

```python
def decode(x, n):
    keys = x[2*(n-1):2*(n-1)+n]
    perm = np.argsort(keys).tolist()
    return perm

def encode(perm, n):
    keys = np.zeros(n)
    for pos, node in enumerate(perm):
        keys[node] = pos / max(1, n - 1)
    return keys
```

## When to use vs alternatives

**Use** when the outer optimizer is real-valued (CMA-ES, DE,
fcmaes, scipy's continuous optimizers).

**Avoid / supplement** when:
- The fitness landscape is "permutation-dominated" — most basins
  differ only in permutation. Dedicated permutation operators
  (2-opt, Or-opt) on the integer side may converge faster.
- The encoded permutation matters for very tight constraints
  (e.g., adjacency); plateaus may waste evaluations.

## In practice

`src/esa_spoc_26/ch2_fcmaes.py` uses argsort encoding for the
permutation slice of x; `encode_solution()` provides the inverse
to warm-start with our 142.99 d solution.

## References

- Bean (1994) — random keys for genetic algorithms.
- fcmaes examples — repeated use of this pattern for SpOC.
