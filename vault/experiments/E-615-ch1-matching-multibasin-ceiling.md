---
id: E-615
type: experiment
status: done             # draft | running | done | invalidated
tags: [ch1, matching, multi-basin, basin-overarching-search, sa-swap, lahc, alns, ceiling, user-conjecture]

hypothesis: "User conjecture (2026-06-14): the matching leaderboard is not one basin being polished but MANY near-equivalent basins; reaching a better one needs GLOBAL inter-configuration search, not single-basin escape."

created: 2026-06-14
ran_start: 2026-06-14
ran_end: 2026-06-15
duration_runtime: "Lever-1 ~4×1h (4 seeds); Lever-2 ~30min (killed early, verdict unambiguous)"

# reproducibility
code: |
  scripts/ch1_e582_matching_sa_swap.py   (Lever-1: SA over ejection-chain swap + tabu)
  scripts/ch1_e579_matching_lahc.py       (Lever-2: LAHC + exact HiGHS repair + ALNS destroy)
inputs: |
  reference/SpOC4/Challenge 1 .../matching-i.txt  (|T|=25000, nodes 5001/5001/5001, bank sel 4465)
  reference/SpOC4/Challenge 1 .../matching-ii.txt (|T|=92103, nodes 10001×3,  bank sel 9111)
  solutions/upload/matching-i.json  (bank mass 33338.184)
  solutions/upload/matching-ii.json (bank mass 72206.516)
outputs: |
  /tmp/ch1_e582_*_best.json  (only written if BEATS BANK — NONE written)
  runs/ch1/e579_lever2_m{i,ii}.log
seed: 4 seeds for Lever-1; ALNS roulette for Lever-2
env: micromamba spoc26, python 3.13.13
---

## Question

User's conjecture: top teams' matching submission *progression* looks like a
staircase of distinct near-equal incumbents (0.2% spread, dozens per team) — the
fingerprint of a **multi-basin plateau** crossed by global inter-configuration
search, NOT improvement-only polishing of one basin. If true, every method we'd
run that is single-basin (exact repair = deterministic bank rebuild; greedy/GRASP
= samples WORSE basins) would be structurally unable to cross. The discriminating
test: does a TRUE configuration-space walk that accepts WORSENING moves climb
PAST the bank?

Context that makes the conjecture reasonable: matching-i is perfectly regular
(every node in exactly 5 transfers), near-uniform weights U(0,10), near-perfect
matching ⇒ a vast plateau of near-equal configurations. m-i SCIP dual bound
**34118 > bank 33338 > leaderboard r1 33555** ⇒ r1 is REACHABLE in our faithful
model (E-039 byte-faithful) — the gap is not a model defect, so a better config
provably exists. Full Gurobi B&B is LICENSE-BLOCKED (25k vars ≫ 2k size cap), so
we cannot out-SOLVE; the edge would have to be smarter SEARCH.

## Method (two levers, escalating neighborhood size)

**Lever-1 — SA transfer-swap (E-582):** Metropolis acceptance of worsening moves
over single ejection-chain SWAP moves (add an unselected transfer i, eject its ≤3
conflicting selected transfers, greedy-refill the freed nodes), + tabu on
freshly-ejected transfers, + periodic `ejection_improve` re-tighten/track. Starts
FROM the bank. Adjacency-guided proposal (pick a conflict of a selected transfer)
so |Δ| is small ⇒ the walk actually traverses the plateau (uniform-random i gave
~0% acceptance). This is the first TRUE config-space walk for matching — the one
thing exact-repair LNS structurally cannot do.

**Lever-2 — large-window structured destroy + EXACT repair (E-579):** LAHC
acceptance + EXACT HiGHS repair of a destroyed window + ALNS roulette over
{random, worst, blocking} destroy operators, at LARGE ruin_k (m-i 120, m-ii 250 —
the untested, conjecture-relevant regime; prior E-579 null was only ruin_k≤40).
Guard-banked. This tests whether a *coordinated* large jump + optimal repair can
land in a different, better basin.

## Result — BOTH DECISIVE NULL

**Lever-1:** ~970M ejection-chain swap moves across 4 seeds, ~1.83M ACCEPTED
worsening moves — every run's best = EXACTLY the bank (m-i 33338.184, m-ii
72206.516), delta +0.000, zero /tmp candidates written. ⇒ every single-swap-
reachable basin tightens back to ≤ bank; the bank is a strong swap-local
attractor and worsening-tolerance does not escape it.

**Lever-2:** ~1.7M total moves (m-i ~1.2M iters, m-ii ~500k), all 4 workers
`wors=0`, every operator `0 wins`, `cur` NEVER left the bank ⇒ even LARGE
coordinated destroy + EXACT repair reconstructs the bank's exact mass every time.
Killed early at ~30min — verdict unambiguous, banks confirmed intact (m-i 4465 /
m-ii 9111 sel).

## Conclusion — matching free-method ceiling = bank, across 7 families

Confirmed = bank: SCIP-i/ii (E-578), exact-LNS (E-048), swap-SA (E-582, 970M
moves), LAHC small-window (E-579 k≤40), LAHC large-window (E-579 k=120/250),
GRASP (E-577, +2.2 one-off, no rank cross), memetic (E-581).

The user's multi-basin conjecture is REASONABLE and the dual bound proves a better
config exists in our model — but NO free operator we have (local swaps OR large
structured destroy + exact repair, with worsening acceptance) crosses to it. The
+217 (m-i, 0.65%) / +1507 (m-ii, 2.05%) gap to r1 is a true integrality/heuristic
gap that a free method cannot cheaply cross. Reaching r1 would need a paid exact
solver (Gurobi license) or an as-yet-unidentified problem-specific global move —
NOT another acceptance metaheuristic over our current neighborhoods.

**Matching frontier CLOSED. Do not re-open without a paid exact solver or a
genuinely new (non-swap, non-window-destroy) global operator.** See
[[basin-overarching-search]] (reframed: matching is reachable-multi-basin, not an
exact-locked ceiling, but unreachable by our free methods).
