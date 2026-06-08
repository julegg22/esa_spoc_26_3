---
id: C-030
type: concept
status: confirmed
tags: [optimization, tsp, lkh, lin-kernighan, ch2, large]
scope: optimization/tsp
confidence: high
created: 2026-06-07
sources:
  - "Helsgaun — An effective implementation of the Lin-Kernighan TSP heuristic (Eur J Oper Res, 2000)"
  - "Helsgaun — General k-opt submoves for the Lin-Kernighan TSP heuristic (Math Prog Comput, 2009)"
  - "LKH-3 manual: http://akira.ruc.dk/~keld/research/LKH-3/"
  - "elkai Python wrapper: https://github.com/fikisipi/elkai"
related: ["[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-028-adaptive-large-neighborhood-search]]", "[[E-536-lkh-small-benchmark]]"]
---

# C-030 — Lin-Kernighan-Helsgaun (LKH-3) TSP solver

*The state-of-the-art TSP heuristic. Solves 100-1000 node instances to
near-optimality in seconds. The presumed core of TGMA's leaderboard-
breaking algorithm on Ch2 large.*

## Definition

The **Lin-Kernighan (LK)** heuristic (1973) is a variable-depth
k-opt search for TSP: at each step, identify an improving sequence
of edge swaps of unbounded depth. Generalizes 2-opt, 3-opt to "do
all swaps that improve, until no more improvement".

**Helsgaun's LKH** (Helsgaun 2000) is a heavily-engineered LK
implementation with:
- Candidate edge sets (only consider top-α nearest neighbors)
- Sequential-edge improvement search (efficient enumeration)
- Better data structures (segment trees for O(log n) updates)
- Multiple restarts with perturbation

**LKH-3** (Helsgaun 2017) extends LKH to many variants: ATSP,
HCPP, TRP, sequential ordering problem (SOP), etc.

State of the art: LKH-3 finds optimal or near-optimal tours on
TSPLIB instances up to ~85k nodes. For typical engineering-scale
TSPs (n < 5000), LKH-3 is the **default first try**.

## Why it matters here

**E-536 validation on Ch2 small** (n=49): LKH-3 via the elkai wrapper
solves the ATSP in **0.3 s** producing a perm with DP-mk = 125 d.
That's worse than our DP-ALNS bank (116 d) — because LKH minimizes
the sum-of-min-tofs proxy, not the actual time-coupled makespan —
but it's already in rank-5 territory in sub-second.

**For large** (n=1051, see [[O-015]]): the cheap-edge graph
decomposes into [601, 150, 150, 150] components. The three small
components are near-complete subgraphs (in/out degree ≈ 149 on 150
nodes). For dense graphs, LKH-3 finds optimal Hamilton paths in
**seconds**. The 601-node comp0 is harder but still in LKH-3's
typical range (minutes).

This is the inferred algorithmic structure of TGMA's June-5 large
breakthrough (1143 → 424 d in 1 hour, see [[O-014]]):
1. Decompose into 4 components.
2. LKH-3 per component (seconds each).
3. Optimize 3 inter-comp bridges + 2 intra-comp exception slots.
4. Stitch into full tour.
5. Polish (times, tofs) on each leg via Lambert refinement.

## Mechanics

### Asymmetric → symmetric (Jonker-Volgenant transform)

LKH-3's symmetric solver is faster than its ATSP solver. For our
asymmetric Lambert costs (dv differs by direction), the canonical
workaround:

Each node i → two STSP nodes (2i, 2i+1). STSP edges:
- between blocks: `stsp[2i+1, 2j] = atsp_cost[i, j]`
- within block: `stsp[2i, 2i+1] = -L` (force in-block edge used)

Doubles n but makes LKH-3 happy. We saw on small:
- Direct STSP (max-of-(i,j)/(j,i) symmetric proxy): 125 d.
- JV-transform ATSP: 133 d. Surprisingly WORSE.

Hypothesis: the JV penalty `L` was wrong, dominating the cost. Tuning
`L` and rerunning could give better ATSP results.

### Open vs closed tour

LKH-3 solves CLOSED tours. For open paths (our use case — perm starts
at a specific node and ends at another):

Add a **dummy node** with cost 0 to all real nodes. The optimal closed
tour through n+1 nodes naturally "breaks" at the dummy, leaving an
open Hamilton path. The first and last nodes of the path are wherever
the tour breaks.

For **fixed endpoint** open paths: set dummy's cost = 0 to ONLY the
specified start and end nodes, with cost BIG to others. LKH-3 will
then choose to break the tour at the dummy with start/end on either
side.

### Cost matrix scaling

LKH-3 requires integer costs. We scale floats (e.g., tof in days) to
centidays or similar small-int range. Watch for:
- **Precision parameter**: LKH-3 has an internal precision check.
  If your scaled costs are too large or have inconvenient GCDs, the
  solver asserts and crashes (we hit this in E-536 with microday
  scaling → assertion `Gain % Precision == 0` failed).
- **Range**: keep costs < 10⁶ for stability.

## In practice

- `elkai` (Python) provides `solve_int_matrix(matrix, runs=k)`.
  `runs` controls the number of restarts; 5 is good default for n<200.
- `scripts/ch2_e536_lkh_small_benchmark.py` — small validation.
- `scripts/ch2_e537_large_cluster_lkh.py` — cluster-decomp pipeline
  scaffold for large (the architecture but with greedy fallback for
  comp0; needs LKH-3 integration for that comp).
- `scripts/ch2_e535_large_cluster_decomp_skeleton.py` — earlier
  skeleton.

## When LKH-3 is the right tool

- Static cost TSP at n=100–5000: yes, immediately.
- Time-coupled TSP: only as a constructive baseline. LKH minimizes
  cost-sum, not chronologically-bounded makespan.
- For our setup: LKH-3 + DP-polish + ALNS-refine is the natural
  pipeline. LKH-3 produces a strong starting perm, DP gives the
  optimal schedule, ALNS explores nearby perms.

## References

- E-536 — sub-second LKH solution at 125 d on small.
- E-537 — cluster-LKH on large (runs end-to-end, greedy walk rejects
  on first ordering — fixable).
- O-014 — TGMA submission pattern suggesting they use LKH or similar.
- O-015 — large structure confirming TGMA's likely architecture.
