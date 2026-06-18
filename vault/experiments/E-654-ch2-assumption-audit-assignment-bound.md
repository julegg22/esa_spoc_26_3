# E-654 — Ch2 deep audit: the loss is epoch-PHASING + fragment-MERGE, not edges (assignment-LB, never computed before)

User pushback 2026-06-18: "NOT a definitive frontier — better solutions exist ⇒ need basin-overarching;
is the LKH build the right next step?" 4-phase audit + cheap probes. Retracts "small at floor".

## Phase 2 result — assignment lower bound (the bound we NEVER computed in the whole campaign)

Min-cost successor assignment (Hungarian) on the per-epoch-min cheap-tof matrix (relaxes subtour +
epoch-chaining). Cheap (O(n³)).

| inst | assignment LB | our bank | competitor | LB/leg | bank/leg | #fragments (subtours) |
|---|---|---|---|---|---|---|
| small | **66.82** | 113.0 | r1 101.65 | 1.364 | 2.306 | 22 (sizes ≤3) |
| medium | **17.23** | 189.10 (r1) | live 192.11 | 0.095 | 1.045 | 69 (sizes ≤17) |

**Gap decomposition (small):** LB 66.82 → +34.83 (epoch-chaining + optimal merge) → r1 101.65 → **+11.35 OUR excess** → 113.
**Medium:** bank 189.10 = LB 17.2 + **171.9 phasing/merge overhead**; cheap 0.095d/leg edges EXIST but
the bank flies 1.045d/leg = **11× inflation** from being at the wrong epoch. Medium is rank 1 ⇒ its 171.9d
overhead is ~irreducible (near-optimal); small has 11.35d of recoverable excess.

**⇒ The loss is NOT per-leg edge choice (we already use near-min-tof edges). It is concentrated in
(a) EPOCH-PHASING (flying legs far from their per-epoch min tof) and (b) MERGING the fragmented
min-tof structure (22/69 subtours) into one Hamiltonian tour with consistent epochs.**

## Phase 3 result — epoch-connectivity audit (exp 3) FALSIFIES the "components dissolve" hope

Medium cheap-graph components per-epoch (sampled every 100 of 1000) = [4,4,4,4,4,4,4,4,4,4]; static = 4.
**The 4-component structure is STABLE across epochs — NOT an epoch artifact (A4 holds, not violated).**
Large is the same (601+3×150, stable). ⇒ Any method MUST respect the hard 4-component + ≤5-exception
bridge structure; it will not dissolve at the right epochs.

## Phase 1/3 — load-bearing assumptions across ALL branches

A2 (order-primary, never time-expanded) and A-bound (optimized for weeks without ever computing a bound)
are the flaws. Untouched paradigms: exact/relaxation/reformulation — skipped as "too big", but the
assignment LB ran in seconds for n=1051 and cluster sub-TSPs are small. LKH = one metaheuristic still
keeping A2 intact; NOT obviously the best next step.

## Verdict: is the LKH build the most promising next step? NO (not first)

The grounded lever is **epoch-phasing + fragment-merge on a time-expanded representation that RESPECTS
the hard 4-component/exception structure** — more specific than a generic LKH permutation search. Concrete
next builds, cheapest-first:
1. **Fragment-merge reformulation** (NEW): treat the assignment's 22/69 min-tof fragments as super-nodes,
   solve the much-smaller merge-order TSP + epoch alignment. Far smaller search than the full permutation.
2. **Time-expanded per-component DP/min-cost-flow** (exp 2): explicit (city × time) graph WITHIN each of
   the 4 components (which are small), optimal exception-bridge stitch. Handles epoch-chaining that our
   permutation search cannot.
3. LKH/metaheuristic on time-expanded edges — only if 1–2 falsify.

Recover targets: small 11.35d (→ rank 4→1 region), large the 508d excess (→ toward 424). Medium near-opt.
See [[basin-overarching-search]], [[deep-single-prompt-audit]], [[ch2-find-transfer-pattern]].

## ★★ UNIFYING STRUCTURE (2026-06-18, E-655 follow-up) — all Ch2 = GIANT + satellites

Lever #1 (naive fragment-merge) FALSIFIED in the informative way: it merged the 22 assignment fragments
freely and produced infeasible tours (slow Lambert on hopeless legs). Root cause found via cheap-component
analysis: **small cheap graph = 4 components, sizes [40, 3, 3, 3]** — the SAME dominant-giant+satellites
shape as medium (4 comps) and large (601+3×150). 4 comps need only 3 bridges ≤ 5-exc budget ⇒ feasible.
Free merge ignored this and blew the exc budget.

**⇒ All three Ch2 instances share ONE structure: a dominant GIANT cheap-component + tiny satellites,
bridged by ≤5 exceptions. The lever is identical: optimize the GIANT's internal order with EPOCH-AWARE
(time-expanded) phasing** — the part local search can't crack (S1/faithful = 172 neighbors stuck; the 11×
epoch inflation lives inside the giant). **Small's 40-city giant is the tractable TESTBED** (40-city
time-dependent TSP; vs large's 601). Build = time-expanded beam/DP or LKH on the giant + cheap satellite
insertion + 3 exc-bridges. This is lever #2, now correctly scoped. NEXT: build it on small's 40-giant;
if it beats 112.996 → scale to large's 601-giant (the rank-2→1 path).
