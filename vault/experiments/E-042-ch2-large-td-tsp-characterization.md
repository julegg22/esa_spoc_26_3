---
id: E-042
type: experiment
tags: [experiment, ch2, large, kttsp, time-dependent-tsp, anti-oscillation, decisive-null]
date: 2026-06-12
status: DECISIVE CHARACTERIZATION — three large-attack families ruled out; lever isolated to MONOTONE time-dependent local search on realized makespan
instance: hard.kttsp (n=1051)
scripts: [ch2_e572_large_global_epoch_lkh.py, ch2_e573_large_fixpoint.py, ch2_e576_large_td_greedy.py, ch1_e575_matching_gurobi.py]
related: [[E-041-ch2-large-gap-decomposition]], [[E-034-ch2-large-epoch-aware-reorder]], [[E-039-ch1-matching-evaluator-audit]], [[M-general-anti-oscillation-discipline]]
---

# E-042 — Ch2 large: time-dependent-TSP characterization (3 families ruled out)

E-041 proved the 1048.98→424.62d (r2→r1) gap is ordering/phasing, not
physical (idle=0; median min-cheap-tof 0.150d at every epoch; ~37 cheap
neighbors/node/epoch). This tick attacked it three ways. **All three
failed in instructive ways that together isolate the real lever.**

## Family 1 — global epoch-aware surrogate re-solve (E-572) → unwalkable

Build a full epoch-aware cost (find_earliest_transfer at each node's
current walk-epoch), one global OR-Tools open-path GLS solve, re-walk,
iterate. Iter0 found a **cheap-cost ~389d order — BELOW r1=424!** — but
`walk_perm_chrono` **REJECTED** it: the costs were evaluated at the seed's
epochs, and reordering shifts realized epochs, so cheap-at-seed edges are
infeasible at the new arrival times. The static-cost optimum (~389d) is
**not walkable**. (The time-dependent TSP trap.)

## Family 2 — self-consistent fixpoint (E-573) → diverges

Fix the trap with a fixpoint: `soft_walk` (never rejects; escalating dv
caps + waiting) extracts a realized-epoch profile from ANY order; build
the cost at the order's OWN soft-walk epochs; re-solve; repeat; track best
STRICT-feasible. **It diverged:** soft real_mk 1522→1433d (both WORSE than
the 1048 bank), exc_over stuck at 3–4, strict walk REJECTED every iter.
The full re-solve jumps to a wholly different order each iter whose
realized epochs are again inconsistent → no contraction.

## Family 3 — pure global greedy NN (E-576) → IS the 1048 bank

A global time-dependent greedy nearest-neighbor (hop to the unvisited node
with smallest feasible tof NOW) got **STUCK** (exhausted the 5-exc budget
mid-tour and dead-ended). Inspection showed `greedy_subtour_only`
(ch2_hierarchical_large, used by E-556) is **already exactly this**
argmin-`t+tof` greedy, applied per-component — and it produced the
**1048d bank**. So greedy NN is not a missing lever; it is the incumbent.
Greedy is myopic (the E-041 fat tail: 654 legs >0.5d) → ~2.5× above the
424d optimum, as expected for greedy on a hard TD-TSP.

## Side result — matching exact-solver lever is HARD-BLOCKED (E-575)

E-039 named "a Gurobi-class solver" as the matching lever. Gurobi 13.0.2
is installed but carries a **size-limited restricted license**: the 25k
(matching-i) / 92k (matching-ii) variable model raises *"Model too large
for size-limited license."* Both instances are a **single connected
component** (union-find over rows sharing any e/l/d index → 1 component of
size n) → no decomposition into license-sized subproblems. With CP-SAT
plateaued at 33,338 (bound 34,339) and HiGHS timed out, the matching exact
lever is closed without an unrestricted Gurobi. **Matching is ceilinged.**

## Synthesis — the isolated lever

| Approach | Why it fails | Verdict |
|---|---|---|
| surrogate global solve (E-572) | optimizes frozen-epoch cost → unwalkable | ✗ |
| full-resolve fixpoint (E-573) | non-monotone → diverges/oscillates | ✗ |
| greedy NN (E-576=E-556) | myopic → 1048d incumbent | ✗ (=bank) |

What none of them does: **monotonically lower the REALIZED makespan via
local moves that keep the walk feasible.** A 2-opt/Or-opt local search that
evaluates each candidate move by its true realized makespan (partial
re-walk) and accepts only strict improvements **cannot diverge** (monotone)
and directly optimizes the true objective — the one principled, untried
attack. Tractability requires neighbor-list-restricted moves + windowed
re-walk (full O(n) suffix re-walk per move is too costly at n=1051).

## Family 4 — monotone single-node Or-opt (E-577) → bank is a LOCAL OPTIMUM

Built the isolated lever: monotone Or-opt on the REALIZED makespan
(neighbor-restricted single-node relocation, long-leg targets per E-041,
screen by local tof-delta then VERIFY by full chrono re-walk, accept only
strict feasible improvements — cannot diverge). One pass screened **26,347**
improving relocations; **every one FAILED re-walk verification** → the 1048
bank is an **Or-opt local optimum under realized makespan**. A locally
cheaper relocation is wiped out (or made infeasible) by the downstream
epoch cascade — the epoch-shift trap at the single-move level. Single moves
cannot escape the 1048 basin.

**Consequence:** escaping requires a **multi-node window re-optimization**
(destroy-and-repair LNS over a contiguous window, entry epoch fixed, window
re-walked, spliced only if the realized makespan drops). This is the one
remaining tractable, monotone, untried attack (E-578). 2-opt segment
reversal is excluded — reversing travel direction perturbs epochs even
more violently than relocation and will also find the bank locally optimal.

## Binary-threshold caveat (pricing)

large is r2 at 1048.98 with r1=424.62, r3=1238.5 (O-016). **Only a feasible
makespan <424.62 changes the rank** (+1.78 pts); anything in (424.62,
1238.5) stays r2 = ZERO points. A local search seeded from 1048 is unlikely
to cross 424 (a 2.5× gap), so this lever's POINT-EV is low despite being
the principled algorithm. Documented so the next tick prices it honestly
rather than re-deriving the threshold.

## Lesson

When a time-dependent routing problem resists a surrogate-cost global
solver, the failure mode is almost always **surrogate/realized epoch
divergence**, not solver weakness. Optimize the realized objective
**monotonically** (local moves on the true walk) instead of re-solving a
frozen snapshot. And: before crediting a "new" construction heuristic,
grep the codebase — E-576's greedy NN was already the incumbent's interior
method (E-556), a duplicate that the anti-oscillation grep caught.
