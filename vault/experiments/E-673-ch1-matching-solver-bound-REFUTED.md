# E-673/674 — Ch1 matching-II: "solver-bound" verdict REFUTED (deep audit, 2026-06-20)

**Trigger:** user deep-audit ("better solutions exist; HRI is NOT using Gurobi; find the FLAW in our
reasoning, not optimize"). Target = the E-635 verdict "matching is solver-bound, needs commercial Gurobi/CPLEX."

## The flaw — PROVEN three ways (matching-II: bank 72,206.52, leader 73,714.03)

1. **LP relaxation solves FREE.** HiGHS IPM, 179 s → **LP upper bound = 75,360** (26.8% fractional).
   The earlier "root-stuck" was a *branch-and-bound* stall, NOT LP intractability.
2. **The leader is NOT at the integer optimum.** Leader 73,714 sits **2.18% BELOW the LP bound 75,360**
   (1,646 under). A team using a stronger *exact* solver would land at/near the optimum (~75k); the
   leader does not. ⇒ the leader has a better **primal** found by better **search**, not a stronger
   exact solver. (Confirms the user's "HRI not using Gurobi".)
3. **A free Lagrangian dual converges to the LP bound.** Relax the D constraints; subproblem = exact
   2-index (E,L) assignment via a validated **auction** (`scripts/ch1_auction.py`, exact vs scipy to
   1e-15, 4.7 s at full 10k×10k/92k scale). Subgradient dual: 82,671 → 75,734 → ~75,360. A tight UB is
   obtainable with NO commercial solver.

⇒ **"solver-bound, need Gurobi" is FALSE.** The gap is a **primal-search gap** (bank is 95.8% of the LP
bound; leader 97.8%).

## BUT — free primals do NOT beat the bank (honest negatives)

- **Lagrangian dual-ascent primal** (E-673b, exact auction subproblem, 90 iters): plateaus **65,927**.
  D-conflicts drain too slowly (~7/iter) and drop-one-per-conflict repair is lossy.
- **Iterated-auction / cyclic 2-index primal** (Phase-4 exp 3, from scratch): **63,901** (first auction
  matches 9,932 E-L pairs but D-repair keeps only 6,323 — huge conflict loss).
- **Auction-repair LNS** (E-674, `scripts/ch1_auction_repair_lns.py`, user-approved build): warm-start
  bank, destroy a large/contention-targeted set of destinations (frees e,l,d across blocks), repair the
  freed sub-instance with a mini-Lagrangian (exact auction + D-repair), accept only strictly-improving
  region re-opts. **RESULT: clean NULL — every iteration new_region_value == old_region_value EXACTLY,
  0 accepts** (targeted and random destroy, 120 iters). Self-check passed (feasibility + value
  bookkeeping correct).

## Corrected diagnosis

The exact auction strengthens the **bound** (proves not-solver-bound) but does **NOT** yield a stronger
3-D **primal** than the bank — because the hard part is the **D-coupling**, which an E-L auction does not
solve. So the auction-repair reconstructs the bank exactly (consistent with E-048 "bank optimal within
every connected ≤680 block" and E-615 "swap-local"). The leader's +1,507 primal edge is **free-reachable
in principle** but NOT via 2-index/dual decomposition; it needs a genuinely stronger primal method we
have not replicated this session — candidates: (a) a long well-tuned specialized 3-AP metaheuristic
(variable-depth / tabu / path-relinking), (b) a TIGHTER MODEL (clique inequalities on the 26.8%-fractional
set-packing LP → stronger branching), (c) a proper Lagrangian heuristic with volume-algorithm interior
primal recovery + local-search polish (many iterations).

## Status of the E-635 "solver-bound" verdict: REFUTED on principle, OPEN on the primal lever.

Banks intact (no change). Tools added: `ch1_auction.py` (validated exact sparse auction),
`ch1_lagrangian_auction.py`, `ch1_auction_repair_lns.py`, `ch1_lagrangian_probe.py`. See
[[ch1-matching-solver-bound-refuted]].
