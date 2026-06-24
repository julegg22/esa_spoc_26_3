---
id: E-603
type: experiment
tags: [experiment, ch2, small, kttsp, assumption-audit, gap-anatomy, topology-basin, exception-allocation]
date: 2026-06-13
status: DIAGNOSTIC (no bank change) — the Ch2-small "no further gains / DP-optimal" verdict is exhaustion WITHIN one topology basin (fixed exception-allocation + comp0 cut), NOT exhaustion of the problem. flight-only=109.99d is already BELOW R3=110.88; the entire R3 gap is phasing idle the DP cannot remove FOR THIS PERM. The local-move ALNS (E-032) never crossed topology basins because the topology-changing operators (double_bridge/random_k) produced 0 bankings (DP-infeasible). The leaders' 101.65 lives in a different exception-allocation basin reachable only through DP-infeasible intermediates.
instance: small.kttsp (easy, n=49), official KTTSP fitness
scripts: /tmp/ch2s_decomp.py, /tmp/ch2s_topo.py (pure arithmetic on bank + edges_small.npz; no search, no write)
related: [[E-602-ch1-trajectory-gap-anatomy]], [[E-032-ch2-dp-alns]], [[E-029-ch2-cpsat-lb-tightening]], [[E-038-ch2-small-epoch-aware-cluster-decomp]], [[E-618-ch2-small-grasp-multistart-floor]], [[A-2026-05-30-ch2-small]], [[M-general-foundation-then-search]], [[M-general-anti-oscillation-discipline]]
---

# E-603 — Ch2 small: assumption audit + gap anatomy (user-requested deep exploration)

## Mandate
User (2026-06-13): treat "better solutions exist per leaderboard" as ground
truth; "no further gains expected" is a FALSE conclusion — find the FLAW in our
reasoning, not optimize further. 4-phase audit (same template as Ch1 E-602).

## Ground truth re-read (official validator, src/esa_spoc_26/ch2_kttsp.py mirrors reference/spoc4_udp)
Decision vector x = `times[:n-1] ++ tofs[:n-1] ++ perm[:n]`, n=49.
`fitness` = `[makespan=times[-1]+tofs[-1], perm_complete, dv_ok, chrono_ok, exc≤5]`.
Per leg: Δv via multi-rev Lambert about the Moon (`max_revs=20`), at the
chosen `(times[i], tofs[i])`. Constraints: each Δv≤`dv_exc`=600; ≤`n_exc`=5 legs
in (100,600]; rest ≤`dv_thr`=100; chronological `times[i]+tofs[i]≤times[i+1]`;
`max_time`=3000 (here horizon 200d binds via leg costs, not the cap).
**Physics is fixed by the validator** — leaders score under identical Lambert/
max_revs. So 101.65 is a pure routing/timing result, NOT different physics.

## Bank decomposition (E-603 probe, exact eval — bank 116.3738d, feasible, 5/5 exc)
```
makespan 116.374 = flight(Σtof) 109.989 + idle 6.384  (initial wait 0)
48 legs: 43 cheap (Δv≤100), 5 exception (Δv∈{565,574,597,561,581} — all near the 600 cap)
cheap-leg Δv: median 98.8  (pressed against the 100 threshold)
idle 6.38d: 5.77 on cheap-leg departures (phasing waits), 0.62 near exc legs
```
**The solution sits on the constraint boundary everywhere** (cheap legs ≈100,
exceptions ≈600) — every drop of Δv budget is already spent.

## The 5 exceptions — role (topology probe)
| leg | edge | Δv | tof | role |
|---|---|---|---|---|
| 2 | 18→12 | 565 | 0.38 | CROSS-COMP (connectivity) |
| 17 | 31→30 | 574 | 0.83 | **INTRA-comp0 (a chosen shortcut, not forced)** |
| 26 | 37→4 | 597 | 0.43 | CROSS-COMP |
| 29 | 17→19 | 561 | 0.43 | CROSS-COMP |
| 45 | 14→16 | 581 | 0.38 | CROSS-COMP |

Cheap-edge(≤100) graph = **4 components {40,3,3,3}**. 4 components need 3 bridges
to chain; the bank uses **4 cross-comp bridges + 1 intra-comp0 shortcut** = 5.
comp0 (40 nodes) is well-connected: min cheap out-degree **2**, **zero degree-1
nodes**, no sources/sinks → comp0's interior route is a genuine combinatorial
search space and is NOT forced to split. The 24+16 split of comp0 (E-038) is a
*choice* of the search, not a structural necessity.

## The flaw (Phase 1+3 verdict)
**flight-only (zero idle) = 109.99d < R3 = 110.88d.** The entire R3 gap (5.49d)
is phasing idle (6.38d) that the DP cannot remove *for this permutation*. The
DP-ALNS bank (E-032/E-527) is provably the optimal (times,tofs) **for its
permutation AND its exception-allocation** (E-038 confirmed interior reorder
`big=0`). The "exhausted/DP-optimal" verdict is therefore correct WITHIN one
**topology basin** = {these 4 bridge edges, this comp0 entry/exit/cut, this exc
allocation}, and false as a claim about the problem.

**Why the search never escaped the basin (smoking gun, E-032):** the topology-
PRESERVING operators (segment_reverse, swap) produced 8/10 and 2/10 of the
bankings; the topology-CHANGING operators (double_bridge, random_k-insert)
produced **0/10** — they all yielded DP-infeasible candidates (DP feasibility
only ~1.2%). The search was structurally confined: every path to a different
exception-allocation passes through DP-infeasible intermediates, so the only
operators that could cross basins always failed the feasibility gate. This is
the Ch1 pattern exactly: exhaustion within an architecture/basin ≠ exhaustion of
the problem. The leaders' 101.65 lives in a different exception-allocation basin.

## Gap accounting (Phase 2)
- to R3 (110.88): **5.49d**, ⊆ the 6.38d idle. Reachable by a perm/allocation
  whose DP-optimal idle is ≲0.9d at similar flight, OR slightly lower flight.
- to R1 (101.65): **14.72d**. Needs ~8d less flight than 109.99 (shorter,
  better-phased legs) on top of near-zero idle ⇒ a materially different route.
- No tight LOWER bound exists: E-029 CP-SAT LB=66.5d is too loose (F3); R3/R1
  are NOT proven unreachable, and flight-only<R3 makes them look very reachable.
- per-leg-independent min-tof LB ≈ 84.82d (unreachable — ignores chronology);
  our 109.99 flight is +25d from it = the chronological-coupling tax for THIS
  perm. A different perm pays a different (possibly smaller) tax.

## Phase 4 — 3 assumption-falsifying experiments (ranked by INFO gain, cheap first)
1. **Component-skeleton enumeration + DP on interiors (violates the fixed-topology
   assumption; CHEAPEST, most decisive). ★ SHARPENED 2026-06-13 after reading the
   DP machinery (scripts/ch2_dp_numba.py):** the forward DP's `e`-budget dimension
   ALREADY allocates the ≤5 exceptions optimally *for a given permutation* (it
   chooses per leg cheap-vs-exc) — so "enumerate exception allocations" is partly
   subsumed by the DP; the genuinely untried degree of freedom is one level up =
   the **component skeleton**: (a) the cyclic ORDER in which the 4 cheap-graph
   components {40,3,3,3} are visited, and (b) which boundary nodes are used to
   bridge between them (the bridge edge is a function of the exit/entry node
   choice, from the (100,600] candidate set in edges_small.npz). For each skeleton
   (few component-orders × small set of boundary-node pairs), construct candidate
   perms (interior of each component ordered by a cheap heuristic or short DP) and
   run the EXISTING ultrafine DP (no Lambert recompute) for the makespan. If any
   skeleton beats 116.37 → flaw confirmed, direct lever; if none across a broad
   sweep → strong evidence the incumbent skeleton is best. Hours, pure DP on the
   cached table. **Run first.** This is the structured perm-space move that the
   local-move ALNS (segment_reverse/swap) provably cannot reach atomically.
2. **Feasibility-repair large-radius ALNS (violates local-move confinement).**
   E-032's cluster/double_bridge ops failed because random repair → 98.8%
   DP-infeasible. Replace random insertion with a cheap-graph-aware repair
   (reinsert destroyed nodes only at cheap-adjacent positions; re-pick bridge
   edges to reconnect components) so that k=8–15 destroy lands feasible and the
   search can actually move between basins. This is E-033's stalled idea with
   the missing piece (feasible repair) added. Days; build on E-032 harness.
3. **Tight lower bound to settle reachability (violates the loose-relaxation
   assumption; INFO-decisive).** Held-Karp 1-tree / Lagrangian relaxation on the
   time-bucketed graph, or an LP bound on the time-expanded network — strong
   enough to bracket 101.65/110.88. Tells us whether to keep searching or accept
   the floor. Larger build; do only if (1)/(2) stall.

## Caveats / honesty
- Diagnostic only, no bank change. Probes are pure arithmetic on the bank +
  edges_small.npz (the fine per-pair Δv table); they bound the gap STRUCTURE,
  not a realized candidate.
- "comp0 not forced to split" is from cheap-graph degrees; experiment 1 must
  confirm a non-splitting (or different-split) allocation is actually DP-feasible
  and better.
- ×1-weight (easy) instance near its floor — EV per hour is modest vs higher-
  weight levers; experiment 1 is cheap enough to settle the "are we trapped?"
  question without a large commitment.
