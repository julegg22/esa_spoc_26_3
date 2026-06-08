---
id: C-029
type: concept
status: confirmed
tags: [implementation, numba, performance, jit, python]
scope: implementation/performance
confidence: high
created: 2026-06-05
sources:
  - "https://numba.readthedocs.io/en/stable/"
  - "Lam, Pitrou, Seibert — Numba: A LLVM-based Python JIT compiler (LLVM-HPC, 2015)"
related: ["[[C-026-dp-on-time-expanded-graph]]"]
---

# C-029 — Numba JIT for tight loops in scientific Python

*The engineering pattern that made DP-ALNS feasible. Without numba,
the medium attack would have taken weeks instead of days.*

## Definition

[Numba](https://numba.pydata.org/) is an LLVM-backed JIT compiler for
a subset of Python. With a single decorator (`@njit`), it compiles a
pure-Python function with numpy array arguments and primitive
operations to native machine code at first call.

Typical speedups for tight integer / boolean numeric loops over
arrays: **50–500×** vs interpreted Python. Memory layout often
matters more than the algorithm itself for the hot path.

## Why it matters here

The forward DP for Ch2 small (see [[C-026]]) in pure Python ran at
**~220 s per perm evaluation**. With numba `@njit(cache=True)`:
**~2.5 s per evaluation = 80× faster**. This made it practical to
run DP-ALNS at hundreds of evaluations per minute per chain across
multiple chains in parallel.

Without this speedup:
- E-529 (12.5 h, 720 k iterations across 6 chains) would have taken
  > 40 days.
- The 10 banking events that took small from 126 → 116 d would have
  been spread over months, with no way to converge in the 3-month
  competition window.

## Mechanics

### When numba JIT is a big win

The forward DP loop is the textbook case:
```python
@njit(cache=True)
def forward_dp(c_arr, e_arr, T, n_legs, n_exc_max):
    reach = np.zeros((n_legs+1, T, n_exc_max+1), dtype=np.bool_)
    pred_t = np.full((n_legs+1, T, n_exc_max+1), -1, dtype=np.int32)
    # ... initialization ...
    for k in range(n_legs):
        for t in range(T):
            for e in range(n_exc_max+1):
                if not reach[k, t, e]: continue
                for tp in range(t, T):
                    arr = c_arr[k, tp]
                    if arr < INF_INT and arr < T:
                        if not reach[k+1, arr, e]:
                            reach[k+1, arr, e] = True
                            # ... record predecessor ...
```

Characteristics:
- Pure numeric: bool/int arrays, integer arithmetic.
- 4-deep nested loop on regular-stride arrays.
- No Python objects, no string ops, no try/except inside loop.
- Numpy operations are sparse (only the array indexing).

### When numba JIT is little or no win

- Calls into external libraries (scipy, pykep) — numba can't compile
  through them; only the wrapper benefits.
- Lots of Python-level dictionary or list comprehension.
- Cold loops (run once or twice — compile time dominates).

### Caching

`@njit(cache=True)` writes the compiled code to disk on first run,
subsequent runs load it directly. Important for multi-process pools
that spawn fresh interpreters — each worker doesn't recompile.

## In practice

- `scripts/ch2_dp_numba.py` — the canonical numba'd forward DP.
  Reused by E-529, E-538, E-543 (all DP-ALNS runs).
- First-call JIT compile cost: ~10–20 s. Acceptable.
- Cache files in `~/.numba/__pycache__/` (per-user).
- Numba version we use: 0.65.1 (installed via micromamba into
  `spoc26` env).

## Gotchas hit

1. **Type inference**: numba needs all variables to have stable
   types. `INF_INT = 10**9` (int) vs `np.inf` (float) — using `np.inf`
   in a `@njit` function with int arrays errors out. We use `INF_INT`
   as a sentinel int.

2. **Numpy boolean array indexing inside @njit**: limited support.
   We use explicit `for t in range(T)` loops with `if not reach[...]`
   checks instead of `np.argwhere`.

3. **Type cast warnings** ("invalid value encountered in cast"):
   when `np.ceil(np.nan / q).astype(np.int32)` is called inside a
   numpy operation, the nan→int cast warns but produces a sentinel
   value (large negative). We filter these by checking `< INF_INT` in
   the DP, so the warning is benign.

## References

- [[C-026]] — the DP that numba's accelerating.
- E-029 / E-032 — measured 80× speedup.
