---
id: E-608
type: experiment
status: done
tags: [ch2, small, kttsp, reject-rate-trap, M-005, verification, anti-oscillation]

hypothesis: "E-607 concluded 'A2 refuted — only the bank order is feasible, the
node order is forced by topology' after OR-Tools + greedy-restart + component
stitching ALL returned 0 feasible orders besides the bank. A solver that
constructs ZERO feasible solutions while a feasible one provably exists (the
bank) is the M-005 reject-rate trap, not proof of optimality. Test it directly."

created: 2026-06-13
ran_start: 2026-06-13
ran_end: 2026-06-13
duration_runtime: "~30 min wall (CPU-contended with 4 Ch1 BCP batch procs)"

# reproducibility
code: /tmp/ch2_small_e607_verify.py
inputs: |
  solutions/upload/small.json (bank perm, last 49 ints; mk=116.3738)
  /tmp/ch2_small_tcoupled_ultrafine.npz (cheap/exc TOF table, 4000 t × 160 tof)
  scripts/ch2_dp_numba.py::evaluate_perm_dp_numba (true-makespan timing oracle)
  reference/.../problems/easy.kttsp (n=49, n_exc=5)
outputs: /tmp/ch2_small_e607_verify.log
seed: deterministic enumeration (no rng)
env: micromamba spoc26, PYTHONPATH=src, OMP_NUM_THREADS=1
---

## What was done (router-free, independent of E-607's machinery)
Bypass the router entirely. Take the bank perm as the start, enumerate ALL
2-opt segment reversals + ALL Or-opt single-node moves (~3400 distinct
neighbors), and DP-time EACH through the SAME `evaluate_perm_dp_numba` that
scores the bank. Correctness gate inside the probe: assert the bank itself is
DP-feasible first (mk=116.3755, e_used=5 — matches the bank's DP makespan).
Scanned ~1900 of the neighbors before stopping (decisive count already in).

## Decisive result
| metric | value |
|---|---|
| bank DP makespan | 116.3755 (e_used=5) |
| **feasible non-bank orders found** | **38** (in ~1900 neighbors scanned) |
| of those, tie the bank (116.3755) | 6 |
| best non-bank makespan | 116.3755 (= bank; **none beats it**) |
| worst feasible non-bank | 150.68 (a long-reversal that stays feasible) |

## Verdict — E-607's stated conclusion is REFUTED; its weaker corollary survives
**E-607 was WRONG that "only the bank is feasible / the order is forced by
topology."** Feasible non-bank orders are DENSE in the bank's immediate
neighborhood — 38 found by trivial local moves. E-607's "global routers found
0 feasible orders" is the **M-005 reject-rate trap**: OR-Tools / greedy-restart
/ component-stitching could not *construct* feasible orders under their
exc-budget model, but that tests the SOLVER's feasibility-construction, NOT the
problem. Same failure shape as E-032 (topology-changing ops 0/10 feasible) and
Ch1 v1 (99% infeasible cold starts). The "exhaustive DFS proves zero
Hamiltonian paths" claim in E-607 is about the *static cheap-only* graph; the
real feasible-order space uses the ≤5 exc budget and is large.

**What DOES survive — the bank is a genuine 2-opt/Or-opt LOCAL optimum.** None
of the 38 feasible neighbors beats 116.3755 (6 tie via cosmetic early-node
reorderings the timing absorbs; the rest are strictly worse). This is now the
THIRD independent confirmation of local optimality (after E-032 local-move ALNS
and E-603's 2448-skeleton DP sweep) — but local optimality is a far weaker
claim than E-607's "topology forces the order," and it does NOT close the
order-search lever.

## Consequence for the R1 gap (the actual question)
The R1 route-length gap (flight Σtof 109.99 vs R1≈101.65, i.e. ~8 d of order
headroom; per-leg min-tof LB 1.77 d/leg vs our 2.29) is NOT reachable by local
moves or naive routers — every path out of the basin passes through
DP-infeasible intermediates, so 2-opt/Or-opt/greedy stay pinned. The open lever
is a **feasibility-aware LARGE-neighborhood / globally-restarted order search**
that co-optimizes order + ≤5-exc allocation + timing while preserving
feasibility across big moves (ruin-and-recreate with a cheap-graph-aware repair,
or SA with feasibility-preserving block moves + the DP as the inner timing
oracle). This is exactly HRI's "massively parallel heavy global optimization"
paradigm — the one paradigm the Phase-3 inventory marked untouched at the ORDER
level. The Ch2-small order lever is therefore **OPEN, not closed** — E-607's
"closed" verdict is reversed.

## Methodology note (anti-oscillation / M-005)
This is the M-005 trigger firing as designed: an agent reported "no feasible
alternative exists" off a ~100% solver reject rate; the independent router-free
DP probe refuted it in one pass. **Lesson reinforced: never accept a
"nothing-better/only-X-feasible" verdict that rests on a solver returning no
feasible solutions at all — verify against the known-feasible incumbent's
neighborhood first.** E-607's verdict line should be read as "OR-Tools could not
construct alternatives," not "alternatives do not exist."

links: [[E-607-ch2-small-global-reroute]] [[E-603-ch2-small-gap-anatomy]]
[[E-606-ch2-small-edge-resolution]] [[methodology-triggers]]
[[anti-oscillation-discipline]]
