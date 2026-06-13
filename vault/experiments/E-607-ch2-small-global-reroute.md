---
id: E-607
type: experiment
status: done
tags: [ch2, small, kttsp, global-atsp, assumption-audit, anti-oscillation]

hypothesis: "Audit claim A2 — the bank's node ORDER was never globally re-routed; a real ATSP solver on the 40-node interior would find a materially shorter flight / makespan than 116.3738."

created: 2026-06-13
ran_start: 2026-06-13
ran_end: 2026-06-13
duration_runtime: "~5 min (correctness gate + 3 search variants)"

# reproducibility
code: /tmp/ch2_small_e607.py, /tmp/ch2_small_e607b.py, /tmp/ch2_small_e607c.py
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp (n=49, n_exc=5)
  /tmp/ch2_small_tcoupled_ultrafine.npz (cheap/exc TOF table, 4000 t × 160 tof)
  solutions/upload/small.json (bank perm, mk=116.3738)
  scripts/ch2_dp_numba.py (true-makespan timing oracle)
outputs: /tmp/ch2_small_e607_cand.json
seed: deterministic OR-Tools + rng(12345/7)
env: micromamba spoc26, PYTHONPATH=src:scripts, OMP_NUM_THREADS=1
---

> **⚠ VERDICT CORRECTED BY [[E-608-ch2-small-e607-verification]] (2026-06-13).**
> This experiment's conclusion ("A2 SURVIVES — only the bank is feasible, order
> forced by topology") is a **M-005 reject-rate artifact** and is REVERSED. An
> independent router-free DP probe found **38 feasible non-bank orders** in the
> bank's 2-opt/Or-opt neighborhood. OR-Tools/greedy/stitching returning "0
> feasible" tested the SOLVER's construction, not the problem. The bank is a
> genuine *local* optimum (none of the 38 beats it) but the global order-search
> lever is **OPEN, not closed**. Read the verdict below as "our routers could
> not construct alternatives," NOT "alternatives do not exist."

## Correctness gate (PASSED)
`evaluate_perm_dp_numba` on the bank perm → mk = 116.3755, Σtof = 109.991,
e_used = 5. Matches the expected DP makespan (~116.3755) and the known flight
time. Oracle wiring verified before any search.

## What was done
1. Built static proxy cost matrices `C_cheap[i,j]=min_t cheap[i,j,t]`,
   `C_exc=min_t exc`, `C = C_cheap if finite else C_exc`, exc-mask = (C_cheap inf).
2. Global routers for open Hamiltonian paths, ≤5 exc arcs:
   - **E-607**: OR-Tools routing (dummy depot, exc-dim≤5) × 7 strategies × 3
     metaheuristics; plus 600-restart greedy + 2-opt/Or-opt local search.
   - **E-607b**: component-aware — OR-Tools cheap-only path within the big
     component + brute-force small clusters + exc-bridge stitching (4! comp
     orders × endpoints).
   - **E-607c**: full-49 OR-Tools ATSP with exc-dim≤5, 11 strategies × 4
     metas, 5 s each (~100 s total).
3. DP-timed every distinct feasible static order against the true oracle.

## Decisive structural finding
The cheap (Δv≤100) graph is **4 components: {40, 3, 3, 3}** with min
out-degree 2. An exhaustive DFS proves the directed cheap graph admits
**ZERO Hamiltonian paths even within the 40-node big component** — it cannot be
traversed cheap-only; interior exceptions are forced. The bank's 5 exc legs are
spread through the route (indices 2, 17, 26, 29, 45), not just inter-component
bridges. Because the static `min-over-t` proxy is *optimistic* (superset of
chronologically realizable arcs), the true feasible-order space is even smaller.

Consequently **every global router found 0 feasible orders other than ones
isomorphic to the bank**: OR-Tools (even 100 s, full exc-dim model) returned no
feasible solution; greedy+LS found 0; component stitching found 0 valid
full orders. The only order DP-timed feasibly was the bank itself.

## Result
| metric | value |
|---|---|
| best DP makespan | 116.3755 (= bank) |
| best Σtof (flight) | 109.991 (= bank) |
| distinct orders DP-timed feasibly | 1 (the bank) |
| any order beats 116.3738 | **no** |

## Verdict
**A2 SURVIVES / audit claim REFUTED.** The node-visit order is not freely
globally optimizable: the cheap-edge topology (4-component, no interior
Hamiltonian path, ≤5 exc budget) constrains the feasible-order space so tightly
that a real ATSP solver cannot even produce a feasible alternative, let alone a
shorter one. The R1 gap (109.99 flight vs 101.65) is **not** reachable by
re-routing within our resolved cheap/exc edge set. R1's shorter route must rely
on **finer/different edge resolution** (cheap windows our table missed, or
shorter realizable TOFs) — i.e. the lever is the EVALUATOR/edge layer, not the
router. See [[E-606-ch2-small-edge-resolution]].

## Methodology note (anti-oscillation)
This closes the "order was never globally optimized" structural-insight
proposal: per M-applying-methodology-triggers, the new-lever claim was tested
and does not fit the gap decomposition — the order is forced by topology.

links: [[E-603-ch2-small-gap-anatomy]] [[E-606-ch2-small-edge-resolution]]
