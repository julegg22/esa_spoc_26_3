---
id: E-728
type: experiment
tags: [ch2, large, rank-1, robustness, local-search, complete-order, patterns, topology]
date: 2026-06-27
status: ACTIVE — robust complete-order method built + descending; pattern analysis reveals two structural basins
related: ["[[E-727-ch2-large-faithful-insertion-repair]]", "[[E-726-ch2-large-ultrathink-audit-rank1-reachable]]", "[[ch2-large-first-bank-topology]]"]
---
# E-728 — Ch2-large: robust complete-order local search + alternative-solution PATTERNS (user-driven)

Two user prompts drove this: (1) *"ALL alternatives failed to allocate all cities — find ONE method robust
against strands, so we know we can complete a tour, then move from there."* (2) *"Find several alternative
solutions (even if worse than the bank) and analyse their patterns."*

## The diagnosis (why every alternative failed to complete)

Every method we'd built — forward beam, GRASP, insertion-repair (E-727) — is **constructive**: it grows the tour
and **DROPS cities it can't place** (strands). That is *structurally* why none completes. The only method that
ever produced a complete tour (the OR-Tools recipe → 932 d bank) is a **complete-solution** method (full
permutation first, then retime). We had never built a *second* complete-solution method.

## The robust method (CLS — complete-order penalty local search)

`scripts/ch2_giant_completion_repair.py` mode=cls. Keep ALL 601 cities in the order at all times; objective =
(n_strands, makespan) via a **tolerant retimer** (`retime_tol`: a leg with no cheap window penalty-carries the
clock + counts a strand instead of stopping). Minimise by **strand-targeted or-opt relocations** (relocate a city
*involved in a strand* — random moves almost never fix a strand) + SA acceptance. It can never "fail to
allocate" — it drives infeasible legs toward 0. **Confirmed descending:** static-LKH seed 188→163 strands;
bank seed 19→17. *This is the robustness the user asked for.* (Speed: ~3 s/move full retime — the staticLKH
basin descends slowly; a prefix-cached retime is the next speedup.)

## The pattern analysis (`scripts/ch2_analyze_solutions.py`, E-728) — TWO structural basins

Directed-edge Jaccard of each complete order vs the bank (1.0 = identical topology, 0 = different basin):

| solution | strands@mw20 | makespan | edge-Jaccard vs bank |
|---|---|---|---|
| bank | 19 | 1352 | 1.000 |
| bank-seeded CLS (×3) | 17–18 | 1334–1342 | **0.96–0.99** (same basin) |
| static-LKH order | 188 | 6810 | **0.017** (different) |
| static-LKH CLS (×2) | 163 | 6098 | 0.016 |
| GLKH tour | 573 | 17280 | 0.000 (different) |

**Decisive finding — resolves the "why only one topology?" mystery ([[ch2-large-first-bank-topology]]):** it is
NOT that we only *built* one topology. There are (at least) two structural basins, and they differ radically:
- **Bank basin:** near-TD-feasible (~18 strands, fixable to 0 by local search) — the only basin that completes.
- **LKH/min-distance basin:** a structurally valid tour sharing only **~1.6 % of edges** with the bank, but
  **deeply TD-infeasible (163–573 strands).** Min-distance ordering ignores time → phasing is wrecked.

So the bank topology is **special**: it is the basin where a static order happens to be re-timeable to feasibility.
Other topologies are tours but ~163 legs from feasible.

## The live question (fleet grinding)

Can CLS drive the *different* (LKH) topology down to 0 strands → a **genuinely alternative complete solution**
(the second topology we've never had)? Or does it plateau (confirming the bank basin is uniquely completable)?
4 CLS chains running (2 staticLKH-diverse, 2 bank-completable). Either answer is valuable: a different complete
tour = new basin to optimise toward rank-1; a plateau = strong evidence the bank topology is structurally forced.
**Next build:** prefix-cached retime to make the staticLKH descent fast enough to settle this. Banks held.
