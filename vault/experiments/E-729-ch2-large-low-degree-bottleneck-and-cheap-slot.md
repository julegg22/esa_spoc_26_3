---
id: E-729
type: experiment
tags: [ch2, large, rank-1, structure, connectivity, low-degree, bottleneck, cheap-slot, lever]
date: 2026-06-27
status: ACTIVE — rank-1 obstacle characterized as a low-degree sequencing constraint; cheap-slot move validated
related: ["[[E-728-ch2-large-robust-cls-and-solution-patterns]]", "[[E-720-ch2-large-ultradeep-audit]]", "[[E-727-ch2-large-faithful-insertion-repair]]"]
---
# E-729 — Ch2-large: the rank-1 obstacle is a LOW-DEGREE sequencing constraint (+ cheap-slot lever)

User: *"collect broadly different strand-0 solutions, analyse connection + tof statistics to attack the problem
better."* We have no short-tof strand-0 solutions yet (that IS rank-1), so instead analysed **where the
lowest-strand orders strand** — those legs are precisely the rank-1 obstacles.

## Key retimer nuance (why "0 strands" = rank-1)

Our fast CLS retimer (`retime_tol`/`windows_k`) is **short-tof-biased** — it can't see the long multi-rev
transfers (tof up to 6.7 d) the bank uses, so it scores the *officially-feasible* bank at **18 strands**
(independent of beam width W=12/24/40). This is a FEATURE for rank-1 hunting: **strand-count under the short-tof
retimer = how far an order is from being an all-short-tof (rank-1-pace) tour.** Reaching 0 = rank-1 — which is
exactly why no chain reaches 0. The stranding legs are the rank-1 obstacles.

## The decisive finding — LOW-DEGREE cities, not inclination, not a structural floor

Strand cities in the two lowest-strand orders (bcls/bcls2, 6 strands each):
- **NOT inclination-driven** (giant inc spans median 1.57, p10≈0 … p90≈π; strand cities are spread, not extreme).
- **Driven by cheap-graph IN/OUT-DEGREE:** strand cities have **7–14 cheap predecessors vs the giant median 152**
  (~10× fewer), and **~1,000–2,100 cheap arrival windows vs ~35,000–42,000 typical** (~30× fewer).
- **6 RECURRENT bottleneck cities strand in both orders: 347, 430, 529, 531, 684, 753** — pushed to the tour's
  tail (legs >585) where they strand.
- **NOT a structural floor:** those 1,000+ windows span the **full epoch range (0–460 d)** — the cities CAN be
  reached cheaply at many epochs. The obstacle is purely **which predecessor**: to place city c cheaply its
  *immediate tour predecessor* must be one of its ~10 cheap preds (~1.7 % random hit). Random local-search moves
  almost never satisfy this → the cities strand. **It is a sequencing/constraint-satisfaction problem, solvable.**

## The lever built + validated — the cheap-slot move

`cls_loop` MOVE-1 (E-729): when a stranded leg involves a low-degree city (min(|cheap-pred|,|cheap-succ|) ≤ 30),
relocate it into a **cheap slot** — a position where `order[p] ∈ cheap-preds(c)` and `order[p+1] ∈ cheap-succs(c)`
(fallback: cheap entry only). Directly satisfies the rare entry/exit constraint instead of relocating randomly.
**Validated:** broke the bcls **6-strand stall → 5 strands in 21 iterations** (random moves had been stuck at 6
for hundreds of iters). Deployed across the 4-chain fleet.

## How to attack the problem better (the actionable plan)

1. **The hard part is ~6–16 low-degree cities, not the whole 601.** The ~585 high-degree cities (110+ preds)
   place anywhere easily. So **anchor the low-degree cities first** by their cheap pred→c→succ triples, then fill
   the easy majority — a decomposition the constructive methods never did (they place hard cities LAST).
2. The cheap-slot move is the local-search version of this; a constructive version = solve the low-degree
   subgraph as a small sequencing/matching problem, then insert the rest.
3. **Open question for next analysis:** can ALL ~16 low-degree cities be simultaneously cheap-slotted in one
   order (rank-1 reachable), or do their cheap-pred sets conflict (two of them want the same predecessor / a
   cycle), forcing ≥1 long leg (a real rank-1 floor)? = a conflict-graph check on the low-degree cities' cheap
   pred/succ sets. **This is the crux: it decides whether rank-1 is reachable at all.**

Banks held. Sharpens [[E-720-ch2-large-ultradeep-audit]] ("hard cities cost 1.2–4.0 d/leg") with the precise
mechanism (low cheap-degree → predecessor constraint) and a working lever.
