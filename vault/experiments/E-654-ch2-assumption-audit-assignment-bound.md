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
