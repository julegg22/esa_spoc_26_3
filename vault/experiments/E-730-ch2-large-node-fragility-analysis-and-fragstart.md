---
id: E-730
type: experiment
tags: [ch2, large, rank-1, structure, fragility, node-features, proximity, constructor, time-aware]
date: 2026-06-27
status: ACTIVE — per-node fragility analysis -> fragility index + the fragstart constructor (87-strand seed, best yet)
related: ["[[E-729-ch2-large-low-degree-bottleneck-and-cheap-slot]]", "[[E-728-ch2-large-robust-cls-and-solution-patterns]]", "[[E-710-ch2-large-time-aware-decomp]]"]
---
# E-730 — Ch2-large: per-node fragility analysis + the fragstart constructor (user-directed)

User direction: mine the city graph for per-node priors (connectivity, reachability, timing fragility, feasible
arrival windows), correlate connectivity/proximity with fragility, and use it to prioritise cities / seed search.

## Per-node features (`scripts/ch2_node_analysis.py`, saved to `cache/ch2_node_features.json`)

Computed from the faithful short-tof window table. The **timing-fragility index = `max_gap`** = the longest
stretch (days) in [0,460] where a city has NO cheap arrival window (miss it → wait that long / strand).

**The giant is BIMODAL:**
- **~482 robust cities:** `max_gap ≈ 0.2 d` (cheaply arrivable ~continuously), in/out cheap-degree ~100.
- **119 fragile cities:** `max_gap` 0.7 → **267 d**; degree as low as ~7. These must be hit in narrow windows.

## Correlations (the user's questions)

- **Connectivity vs fragility:** `in_deg` vs `max_gap` = **−0.54** (moderate: low degree → more fragile, but
  degree explains only ~30 % of fragility variance). `arr_density` vs `max_gap` = −0.97 (same robustness, two
  views). `out_deg` vs `in_deg` = +0.98 (connectivity is symmetric). 92 % of fragile cities are also low-degree.
- **Proximity (orbital isolation) vs fragility = +0.12 — NEGLIGIBLE.** Orbital elements individually vs `max_gap`:
  `a` −0.02, `inc` −0.03, `e` +0.02 (all ~0). Fragile cities' mean isolation (1.53) ≈ robust (1.41).
  **Decisive negative result: fragility is NOT a geometric property.** It is a **phase/timing-synchronization**
  property — a city is fragile because of *when* its mean-anomaly phase aligns with potential predecessors for a
  short-tof transfer, not *where* its orbit sits. → You cannot shortcut hardness with geometric heuristics
  (orbital clustering / element-space NN); fragility must be measured *dynamically* from the window table.

## Constructive use — the fragstart constructor (the actionable win)

Tested two uses of the fragility prior in a forward time-aware (earliest-arrival) greedy:
- **Fragility-CHASE priority (grab fragile cities first): BACKFIRES** — 153 strands (chasing creates detours;
  reaching a fragile city needs being at its specific pred, which the chase doesn't arrange).
- **Fragile START + plain earliest-arrival greedy: 87 strands @3610 d** — **best seed ever** (vs static
  min-DV/min-tof 150–165, GLKH 573). Multi-start sweep over the 30 most-fragile starts → best 87 (start 477),
  saved `cache/ch2_seed_fragstart.json`.

So the fragility analysis pays off through **good starts** (begin at the hardest city, place it while its window
is open), not a chase-priority. 87 strands is a ~2× better CLS seed than anything prior. Deployed 2 CLS chains
from it (tags fcls/fcls2, a fresh time-aware basin distinct from both bank and staticLKH).

## Side-finding

As the bank-seeded CLS chains reduce strands via cheap-slot, they **drift from the bank topology** (edge-Jaccard
0.97 → 0.72) — strand reduction genuinely rewires the order, not just polishing. The CLS explores real structure.

## E-730b — W>1 time-aware BEAM constructor (the real win): seed strand-count 87 → 44 → 30

`scripts/ch2_beamfrag_constructor.py`. The greedy fragstart commits to the earliest-arrival window and strands
when that phase has no continuation; a **W>1 beam that branches over windows and keeps the deepest-then-earliest
states** avoids that. Results (seed strand-count under retime_tol W=16): greedy fragstart **87** → beam W=20
**44** → beam W=30 **30** (start 725). Each is the best Ch2-large seed on record (static min-DV/min-tof = 150–165).
**Wider beams keep improving the seed** — the lever is *time-aware beam construction*, not node-feature priors.
Reseeded the fragstart CLS chains from it (descending 44→42…). NB this is the E-710 time-aware beam idea, now
(a) measured by STRANDS on the faithful retimer and (b) launched from fragility-ranked starts.

## E-730c — DECISIVE: makespan converges to RANK-2 across ALL basins at feasibility (rank-1 unreachable)

The beam seeds (87→16 strands) raised the hope "short-tof time-aware order → CLS to 0 strands → rank-1 makespan."
**Refuted by the data.** Penalty-adjusted true makespan as each chain nears feasibility:
- bank basin: bcls 1 strand → ~894 d, bcls2 2 → ~908 d.
- beam (fragstart) basin: fcls 10 → ~983 d, fcls2 7 → ~987 d.

**All chains converge to ~900–985 d (d/leg ~1.5 = RANK-2), independent of seed/topology.** None approaches the
<500 d that would signal rank-1. Tighter maxwait (mw=10 vs 12) gave MORE strands (22 vs 16) at the SAME ~1480 d
— you cannot tighten your way to rank-1; the waits are *required* for feasibility. This is the strongest evidence
yet that rank-1 is **structurally unreachable by feasibility-seeking methods**: two independent basins (bank
topology + a genuinely different beam topology, edge-Jaccard ~0) both bottom out at rank-2 makespan. The
competitor's 424 d tour exists but lives in a tightly-phased basin our constructors/local-search cannot enter.
The rank-1 gap is now empirically a basin-reachability wall, not a "we haven't searched enough" gap.

## CAVEAT (user asked re: orbital isolation index) — static node features only weakly predict ACTUAL strands

Decisive test: per-city involvement in actual strand legs (across staticLKH/fragstart/bcls orders) vs each
static feature:
- fragility (max_gap): **r=+0.095**, low-degree: **+0.146**, orbital isolation: **+0.099**. ALL WEAK.
- orbital isolation vs strand-residual-after-fragility = +0.088 → isolation carries the SAME weak signal,
  **adds no orthogonal value** (don't add it as a prior).
- strand-involvement spreads over **259 cities**, not a small hard set.

**Reconciliation with E-729:** in NEAR-feasible orders (1–6 strands) the few remaining strands ARE the
low-degree/fragile cities (why cheap-slot helps the ENDGAME). In FAR-from-feasible orders (88–153 strands) the
timing CASCADE strands easy cities too, so the difficulty spreads. **Net: static per-node features (degree,
fragility, isolation) are an ENDGAME tie-breaker only; the core difficulty is GLOBAL timing coherence, not a
per-node property.** Don't over-invest in node indices — the lever is global (the time-aware constructor/seed,
e.g. fragstart's 87, which came from the START + earliest-arrival, not per-node prioritisation).

Banks held. Builds on [[E-729-ch2-large-low-degree-bottleneck-and-cheap-slot]] (low-degree = the same set, 92 %
overlap) and gives the constructor the fragility-priority START + precomputed arrival-window priors.
