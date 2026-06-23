---
id: E-609
type: experiment
status: done
tags: [ch2, small, kttsp, global-order-search, LNS, simulated-annealing, reject-rate-trap, M-005]

hypothesis: "E-608 reopened the Ch2-small ORDER lever: the bank order (mk
116.3755) is a confirmed 2-opt/Or-opt local optimum, but feasible non-bank
orders are dense, so a feasibility-aware LARGE-neighborhood / globally-restarted
order search (DP as inner timing oracle) might find an order with strictly
smaller makespan, toward R3=110.88 / R1=101.65. Test it without falling into the
M-005 reject-rate trap that sank E-607."

created: 2026-06-13
ran_start: 2026-06-13
ran_end: 2026-06-13
duration_runtime: "~45 min wall (2 cores, niced; v1 diversified-restart SA ~18min + v2 iterated-LNS ~25min)"

# reproducibility
code: |
  scripts/ch2_e609_search.py      (v1: SA + diversified Hamiltonian restarts)
  scripts/ch2_e609_search_v2.py   (v2: iterated-LNS, growing-ruin kicks from bank)
  scripts/ch2_dp_fast.py          (vectorized inner DP oracle, ~100x faster)
inputs: |
  solutions/upload/small.json (bank perm, last 49 ints; DP mk=116.3755 e=5)
  /tmp/ch2_small_tcoupled_ultrafine.npz (cheap/exc TOF table, 4000 t x 160 tof)
  scripts/ch2_dp_numba.py::evaluate_perm_dp_numba (TRUSTED timing oracle)
  reference/.../problems/easy.kttsp (n=49, n_exc=5)
outputs: |
  /tmp/ch2_e609_s{1,2}.log, /tmp/ch2_e609_v2_s{11,12}.log
  /tmp/ch2_small_e609_*.json (best perms per seed)
seed: 1,2 (v1), 11,12 (v2)
env: micromamba spoc26, PYTHONPATH=src, OMP_NUM_THREADS=1, nice -n 10
---

## What was built
A feasibility-aware order search with the DP as the inner timing oracle. Two
arms, both searching ONLY node orders (the DP allocates timing + the <=5-exc
budget optimally per order):

1. **Fast inner oracle (`ch2_dp_fast.py`).** The trusted `evaluate_perm_dp_numba`
   is correct but ~1.7 s/eval (O(T^2) double loop, T=4000) — far too slow for a
   search. Rewrote the per-leg propagation to exploit "waiting is free": within
   an e-layer, any departure bucket >= the earliest reachable arrival is
   feasible, so propagation is a single scatter per leg. Result: **17 ms/eval
   (~100x faster, ~58/s)**. Cross-validated against the trusted oracle on 400
   random neighbors of the bank: **11/11 feasible makespans matched to 1e-6, 0
   feasibility-class mismatches**. Every reported beat is also re-scored through
   the trusted oracle + official `KTTSP.fitness`/`is_feasible`.

2. **Move operators + constructors (feasibility-preserving).** Pre-screen every
   candidate with the directed "ever-feasible" (cheap-or-exc) mask + an
   exc-lower-bound (count of legs with no cheap edge); only DP-time orders that
   pass. Moves: feasibility-targeted relocate/reverse/segment-relocate (insertion
   points chosen to keep both new adjacencies ever-feasible), plus
   ruin-and-recreate (remove k=4-20, cheap-graph-aware regret reinsertion).
   Diversified starts: a **randomized greedy Hamiltonian-path constructor** on
   the ever-feasible directed graph, preferring cheap edges to stay <=5 exc.

## Correctness gate (M-005 discipline, done FIRST)
- Bank reproduced under both oracles: **mk=116.3755, e_used=5, feasible** — wiring
  confirmed before any search.
- **The original "component-blocked" diversified start was BROKEN: 0% feasible**
  (every start had 4-5 hopeless legs + exc_LB=6 > budget). This is the exact
  M-005 reject-trap that sank E-607. Fixed it: replaced with the Hamiltonian-path
  constructor -> **99.4% of constructed starts are DP-feasible**. Surfacing and
  fixing this BEFORE drawing any verdict is the whole point of the discipline.

## Feasible-construction rate (healthy, not a near-0% artifact)
- Among orders that pass the cheap pre-screen, **~100% DP-time feasibly**
  (prescreen_pass == dp_feasible in every run). The pre-screen correctly and
  cheaply rejects orders with a hopeless leg; it is NOT a silent solver reject.
- Search-wide feasible rate (DP-feasible / all candidates incl. pre-screened):
  **~16%** steady-state for v1, ~14% for v2 — a HEALTHY rate. Diversified
  Hamiltonian starts feasible at **99.4%**.

## Result vs bank 116.3755
| arm | seeds | restarts/kicks | orders constructed | best mk found | beat? |
|---|---|---|---|---|---|
| v1 SA + diversified restarts | 1,2 | ~40 restarts/seed | ~124k/seed | 116.3755 | NO |
| v2 iterated-LNS (growing ruin) | 11,12 | 40-80 kicks/seed | ~66k + ~109k | 116.3755 | NO |

- Lowest makespan any diversified-restart SA descent reached (other than the
  bank incumbent itself): **116.8255** — i.e. it got within **0.45 d** of the
  bank but **never beat it**. Best-per-restart makespans cluster at **123-129 d**
  with a single outlier at 118.5; the bank at 116.38 is an isolated deeper basin.
- v2 iterated-LNS ran the bank as incumbent and applied 40-80 large-ruin kicks
  (k grows to 20 under stagnation) + SA descent per kick; **62 consecutive kicks
  on one seed produced no improvement**. Incumbent never left 116.3755 (one seed
  briefly accepted an 118.5 worsening to diversify, still found nothing below
  bank).
- **TOTAL across the 4 runs: 422,125 orders constructed, global minimum makespan
  = 116.3755 (the bank itself); not a single order came in below it.**

## The reframing finding (why route-length headroom is largely illusory)
Decomposed the bank schedule: **makespan 116.38 = 109.99 flight (Sum tof) +
6.38 wait (5.5%), and NO leg waits > 0.5 d.** The bank is **flight-bound, not
wait-bound**. So beating it requires an order with strictly smaller
chronologically-feasible Sum-tof, NOT smaller waits. The per-leg-min-tof bound
(1.77 d/leg, ~84.8 total) is unreachable because those minima occur at mutually
incompatible departure times; the timing-free TSP-style LB on Sum-min-tof is a
useless 1.2 d. The only arbiter of an order's real cost is the DP, and across
422k candidate orders (~67k DP-feasible) from two genuinely different global
strategies, none came in under 116.3755.

## Verdict — order lever is (empirically) at/near a GLOBAL optimum, not just local
This is the FOURTH independent confirmation the bank is optimal under bounded
order search, and the first with a *healthy* feasible-construction rate and
genuinely global (not local) moves:
- E-032 ALNS, E-603 skeleton sweep, E-608 full 2-opt/Or-opt scan -> local opt.
- E-609 (this): diversified Hamiltonian restarts (99.4% feasible starts) +
  iterated-LNS with large growing-ruin kicks -> **0 orders beat 116.3755** out of
  422k candidates (~67k DP-feasible). Feasible alternatives ARE dense (refuting
  E-607), but they are all >= the bank. The big-valley structure (random optima
  cluster 8-13 d above, bank an isolated outlier) is the classic signature of a
  near-global optimum.

**Honest read:** the Ch2-small ORDER lever is, for practical purposes, EXHAUSTED
under bounded autonomous search — not because construction failed (it didn't:
99.4% feasible) but because no shorter feasible order exists in reach of strong
global operators. The remaining gap to R3/R1 is NOT order-length headroom as the
per-leg LB suggested; it is the chronological-coupling tax baked into Sum-tof for
THIS instance's cheap/exc geometry. A beat below 116.3755, if one exists, would
require either (a) a finer/different TOF table changing the cheap-edge geometry,
or (b) a fundamentally different solver (exact CP-SAT over order+timing jointly),
not more metaheuristic order search.

## Methodology note
The discipline worked exactly as intended: the FIRST diversified-start
constructor was the M-005 reject-trap (0% feasible) — caught and fixed before any
verdict, instead of mis-reporting "no better order exists" off a broken
constructor (the E-607 mistake). The negative result here rests on a 99.4%
feasible-start rate and ~16% overall feasible rate, so "nothing better found" is
a valid negative, not a solver artifact.

links: [[E-608-ch2-small-e607-verification]] [[E-607-ch2-small-global-reroute]]
[[E-603-ch2-small-gap-anatomy]] [[E-606-ch2-small-edge-resolution]]
[[M-applying-methodology-triggers]] [[M-general-anti-oscillation-discipline]]
[[M-general-foundation-then-search]]
