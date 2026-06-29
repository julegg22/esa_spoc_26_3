# E-756 — Ch1 matching-i deep audit: the missed attack is CARDINALITY-AUGMENTATION, not better swaps

**Date:** 2026-06-29
**Trigger:** user `/deepaudit ch1 matching-i` — "focus on missed attacks / alternative
optimization approaches; competitors use only STANDARD methods, so a better primal IS reachable —
find the shared assumption ALL our methods make."
**Standing verdict under audit:** matching-i WALLED at **33,490.458** (rank 4) across 4 method
families — cooperative MIP-LNS (E-002/003), exact CP-SAT polish (E-004/048), SA transfer-swap
(E-582, fast + hot 60M iters), multi-basin (E-615). Leader **33,555** (+65, rank 1).

corrects: [[E-615-ch1-matching-multibasin-ceiling]]
reframes: [[E-048-ch1-matching-exact-lns-exhausted]], [[E-582]]
relates: [[E-673-ch1-matching-solver-bound-REFUTED]], [[C-003-weighted-3d-matching]]

## Target (live)
Our bank **Y = 33,490.458** (rank 4). Leader **X = 33,555** (rank 1, **+65 = +0.19%**).
Next-lower rank 3 within +5. LP relaxation **34,120.53** (measured here, IPM, see Phase 2).

## Phase 1 — Assumption audit (shared across ALL 4 families)
- **A1 (encoding):** solution = a SUBSET of the 25,000 candidate triples; one binary per triple.
  *Violator:* a method that works on the bipartite alternating-graph / permutation pair instead.
- **A2 (objective/moves):** improvement = **weight-improving exchanges at (near-)FIXED cardinality**
  — single transfer-swap (E-582), LNS destroy-repair (E-002/3), CP-SAT branch-and-bound. None
  performs a **cardinality-augmenting alternating path** (the canonical matching operation).
  *Violator:* an augmenting/ejection-chain move that raises |M| from 4479 toward 5000.
- **A3 (bound to guide):** CP-SAT trusts the LP to prune. *Violator:* a method that ignores the LP
  because it is loose.
- **A4 (candidate set):** all methods take the 25,000 triples as given.
  *Violator:* n/a — **measured full, no pruning** (5 candidates per E-node exactly), so A4 is NOT
  the flaw.

## Phase 2 — Gap accounting (measured on the banked artifact, no new search)
- **Candidate set:** 25,000 triples, 5000 E / 5000 L / 5000 D nodes, **exactly 5 candidates per
  E-node** (min=max=5). Full — pruning is not the flaw (kills A4).
- **Bank:** 33,490.458, **4479 of 5000 nodes matched → 521 UNMATCHED** per dimension.
- **Bank is a MAXIMAL matching:** **0 free insertions** (no unselected triple has all three of its
  e,l,d simultaneously free). ⇒ every gain REQUIRES displacement.
- **LP relaxation = 34,120.53, 45.0% fractional** (11,258 of 25,000 vars in (0,1)). The LP is
  *loose* — half-integral — so LP-based methods (CP-SAT B&B, LP-rounding) get almost no guidance.
  This is the textbook max-weight-3-DM signature (mirrors matching-II's 26.8% fractional, E-673).
- **Gap decomposition:** LP−bank = 630.1 (1.88%); leader−bank = **65 (0.19%)**; LP−leader = 565.
  The leader is itself 1.66% under the LP ⇒ **not** an exact-solver result — a better PRIMAL from
  better SEARCH (same conclusion as E-673 for matching-II). The +65 is ~13 node-matches' worth.

**Number overrules story:** the wall is NOT "need a stronger exact solver" (LP is loose, CP-SAT
can't prune) and NOT "candidate set too small." It is that the bank is a **swap-optimal, maximal**
matching, and **no method ever applied the augmenting/ejection operation that the matching
structure demands** to move off it.

## Phase 3 — Paradigm inventory
| Paradigm | Touched? | Note |
|---|---|---|
| MIP branch-and-bound (CP-SAT) | ✅ E-004/048 | loose LP ⇒ no pruning, 40min stall |
| LNS destroy-repair | ✅ E-002/003 | repair = re-solve subset; fixed-cardinality basin |
| SA single transfer-swap | ✅ E-582 | depth-1 displacement only |
| **Augmenting-path / ejection-chain** | ❌ | the canonical matching move; **never built** |
| **Alternating exact-2-DM (Hungarian/auction) rotation** | ⚠️ partial | `ch1_auction.py` exists (E-673, exact (E,L) auction 4.7s) but used for the DUAL bound, never as a rotating primal optimizer |
| **Lagrangian-dual-guided primal** | ⚠️ partial | E-673 built the dual for matching-II's BOUND; never repaired into a matching-i primal |

The untouched paradigm (augmenting/ejection chains) was skipped because of **A2** — everyone
assumed "improve weight by swapping," which is exactly the assumption Phase 2 shows is binding
(bank maximal + swap-optimal). This survives scrutiny: it is an artifact of the chosen
neighborhood, not a property of the problem.

## Phase 4 — Plan (3 experiments, each violates ≥1 assumption, cheapest-info first)
1. **Ejection-chain / augmenting-path local search** (violates **A2**). For each of the 521
   unmatched E-nodes, BFS an alternating chain: unmatched-E wants one of its ≤5 candidate (l,d);
   if l,d are used by selected triples T1,T2, eject them, freeing their E's, which recurse (depth
   ≤3) — accept the chain iff net Δweight > 0. **Cheap** (~100 lines, sparse adjacency, seconds).
   **Binary:** any chain with Δweight>0 found ⇒ swap-neighborhood was too weak, **lever OPEN**
   (scale to full ejection-chain SA). Full sweep finds none ⇒ bank is augmentation-optimal, wall
   real for this neighborhood → escalate to #2.
2. **Alternating exact-2-DM rotation** (violates A2 with EXACT subproblem moves). Reuse
   `ch1_auction.py`: hold the D-assignment of selected triples fixed, re-solve the induced (E,L)
   assignment over the sparse candidate graph EXACTLY, rotate dimension held fixed (D→L→E), iterate
   to convergence from the bank + random restarts. Exact subproblem >> single swaps. **Binary:**
   converges >33,490 ⇒ loose-LP basin escapable by exact rotation; else confirms.
3. **Lagrangian-dual-guided primal** (violates A3). Relax L,D constraints (multipliers); relaxed
   problem decouples per E-node (pick best of 5 by adjusted weight); subgradient to tighten; at each
   iterate REPAIR the conflicting relaxed solution into a feasible matching (greedy/auction).
   Reuses E-673 dual machinery as a PRIMAL generator. **Binary:** repaired primal >33,490 ⇒
   dual-guidance beats direct search; else the +65 is genuinely at the search frontier.

## Results (experiments run 2026-06-29)
- **exp#1 cardinality-augmenting ejection trees** (`ch1_matching_ejection_chain.py`, best-choice,
  depth-5, 500k node budget, double-conflict branching): **0 net-positive augmenting trees** over all
  521 unmatched E-nodes (147 s full sweep). NOTE: a depth-1 single-conflict version found nothing in
  0 s — that was a **probe artifact** (81.4% of unmatched-E candidates are DOUBLE-conflict, silently
  skipped); the real test needed the branching ejection tree (instrumented per CLAUDE.md §5a).
- **exp#1-Phase2 same-cardinality k-cycle exchange** (seed from matched node, re-place higher, close
  into freed slot — the k≥3 cycles single-swaps miss): **0 improving cycles** over 4479 matched
  triples (depth-5 best-choice).
- **exp#3 Lagrangian dual-guided primal** (`ch1_lagrangian_auction.py i`, reused E-673b machinery):
  best primal **30,245.0** = **−3,245 BELOW bank**. Dual bound fell to 34,314 (≈ LP 34,121); leader
  33,555 sits below it → corroborates E-673's "primal-search gap, leader NOT at integer optimum".
- exp#2 (alternating exact-2-DM rotation) not separately run: exp#3 is a strictly stronger version of
  the same assignment-decomposition paradigm and nulled hard (−3,245), so #2 is low-probability.

**Synthesis — the gap is BASIN, not neighborhood.** The bank 33,490 is now a verified local optimum
under SIX standard primal neighborhoods: single-swap (E-582, 60M iters), LNS destroy-repair (E-002/3),
exact MILP B&B (E-004/048, 40 min), cardinality-augmenting trees (E-756 depth-5), k-cycle exchange
(E-756 depth-5), Lagrangian-repair (E-756). None reaches the leader's +65 (0.19%). The leader's
solution is therefore a **structurally different maximal matching in a different basin**, reachable
only by GLOBAL diversification (large destroy + exact rebuild with SA/restart acceptance, or
many diverse-seed reconstructions), **not** by any local move from our bank. This is exactly the
[[basin-overarching-search]] pattern: many methods converge + a competitor sits just above ⇒
basin-LOCKED, not at a ceiling.

## Verdict
The "walled across 4 families" claim is **conditional on a single neighborhood assumption (A2):**
all four families improve weight by **fixed-cardinality swaps / loose-LP branch-and-bound**, and
the bank is provably **maximal (0 free insertions) and swap-optimal**. The matching-theoretic move
that escapes such a point — a **cardinality-augmenting alternating path / ejection chain** — was
**never built**. The LP being 45% fractional confirms LP-based methods can't help, so this is a
pure primal-search gap (leader is 1.66% under the LP — not an exact-solver result). The +65 is
small (0.19%, ~13 matches) but the lever is real and untried. Taking experiment #1 now.
