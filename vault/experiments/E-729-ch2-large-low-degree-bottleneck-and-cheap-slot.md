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

## Conflict-graph check result (the crux) — NO structural floor, but a 118-city contended subgraph

Ran the conflict check (distinct-cheap-predecessor bipartite matching + "all cheap-preds also low-degree?"):
- **The low-degree population is LARGE: 118/601 cities have ≤20 cheap pred/succ** (not the 6–16 that happened to
  strand in two orders — those were just the tail symptoms). ~20% of the giant is low-degree.
- **It is a CONTENDED, internally-connected subgraph:** ~93/118 low-degree cities have cheap-preds that are ALL
  *also* low-degree — i.e. they can only be entered cheaply *from each other*. So they are NOT independently
  sandwichable between abundant high-degree cities (my "anchor 16 cities" plan was too optimistic); they must be
  threaded as a coherent low-degree cluster embedded among the ~480 easy high-degree cities.
- **BUT there is NO Hall-level obstruction:** a perfect distinct-cheap-predecessor matching exists (118/118).
  So rank-1 is **not structurally blocked** at the matching level — a consistent predecessor assignment exists.
  (Caveat: matching ⊉ Hamiltonian path — the arcs may form subtours; matching is a necessary, not sufficient,
  condition. Full Hamiltonicity is NP-hard. But no *trivial* impossibility was found.)

**Verdict:** rank-1 is a **hard SEARCH problem on a 118-city contended low-degree subgraph**, not a proven floor.
The sharper attack this implies: **decompose** — extract the 118-city low-degree subgraph, find a cheap
(short-tof) Hamiltonian path through it using its internal cheap edges, then insert the ~480 easy high-degree
cities into that backbone. This is the one constructive decomposition never tried (constructive methods place
hard cities last; this makes them the skeleton). The cheap-slot move is the local-search analogue and is already
descending. NB: the bank-basin CLS chains optimise toward rank-2 (long-tof seed); rank-1 needs this short-tof
118-subgraph solved.

## Skeleton constructor — TRIED, FAILED (the obstacle is timing, not edge choice)

Hypothesis: a short-tof order that threads the low-degree subgraph as a backbone would seed the CLS far better
than the min-DV staticLKH (153 strands). Built greedy NN on the cheap short-tof (min-tof) graph, with and without
low-degree-first priority. **Result: min-tof greedy = 165 strands, low-degree-first = 215 — both WORSE than
staticLKH's 153.** Decisive lesson: **static seeds are all ~150–215 strands regardless of edge-cheapness
heuristic, because the strands come from TIMING/phasing infeasibility, not edge selection.** A "better static
order" cannot help — the obstacle is time-dependent. So the decompose-skeleton idea is refuted *as a static
constructor*; the time-aware CLS (which has the retimer in its objective) remains the only tool that addresses
phasing.

## Honest consolidated state (two separable obstacles)

The CLS objective (strands, makespan) exposes that rank-1 has TWO obstacles, and we're only beating one:
1. **Strand count** (are all legs short-tof-feasible?) — the cheap-slot move WORKS: bcls 6→3 strands, descending.
2. **Makespan / waits** (tight phasing — arriving as each window opens, minimal waiting) — UNSOLVED. bcls at 3
   strands is ~982 d ≈ rank-2 pace: the legs are short-tof but the WAITS between them are large. Rank-1 (424 d)
   needs ~560 d of waits removed = global tight phasing — the genuine hard core, and the bank basin can't reach
   it (basin separation, [[E-720-ch2-large-ultradeep-audit]]).

So: CLS+cheap-slot is converging toward a robust **rank-2** reproduction (short-tof legs, loose phasing). Rank-1
remains walled on **tight global phasing**, now precisely separated from the (solved) leg-feasibility obstacle.

## Capstone: EXTREME TIMING FRAGILITY (why rank-1 can't be reached by perturbation)

Tried an ILS kick to escape the bank chains' 2-strand plateau. **Both kick strengths catastrophically cascade:**
a double-bridge took 2 strands → 151; a *gentle* 3-city relocation took 2 strands → **107**. Reverted (net-
harmful). The cause is structural: the retimer is a forward sweep and short-tof windows are rare (~6% of epochs
open), so relocating *any* early-positioned city shifts every downstream arrival and the rare windows close →
mass strand cascade. **The feasible solution is a knife-edge: its phasing is globally coherent and cannot be
perturbed into or out of without shattering.** This explains, at the deepest level, the whole campaign's
Ch2-large difficulty: local search can only make non-cascading (tail / timing-preserving) moves, deep local
minima can't be escaped by kicks, and rank-1 must be *constructed* with globally-coherent timing — it cannot be
reached by improving a rank-2 solution (basin separation is really *timing rigidity*). The CLS+cheap-slot reaches
2 strands (near rank-2) and there it sticks; that is the floor of perturbative methods on this problem.

Banks held. Sharpens [[E-720-ch2-large-ultradeep-audit]] ("hard cities cost 1.2–4.0 d/leg") with the precise
mechanism (low cheap-degree → predecessor constraint), a working lever (cheap-slot, strand side only), and the
timing-fragility reason perturbative rank-1 attacks fail.
