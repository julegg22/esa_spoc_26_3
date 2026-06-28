---
id: E-735
type: experiment
tags: [ch2, large, deep-audit, order-search, labeling-dp, reorder-trap, rank-2]
date: 2026-06-28
status: ACTIVE — 3rd /deepaudit ch2-large; finds the load-bearing flaw the two prior audits (E-720, E-726) shared
corrects: [E-587, E-591]
reframes: [E-720, E-726, E-727]
related: ["[[ch2-large-first-bank-topology]]", "[[ch2-medium-bank]]", "[[E-734-ch2-medium-rank1-reclaimed-182]]", "[[ch2-large-time-ordering-wall]]"]
---
# E-735 — /deepaudit ch2-large: the medium rank-1 machinery was never applied to large's complete tour

Third deep audit (after E-720 ultradeep, E-726 ultrathink). **Y = 932.53d bank** (unsubmitted). Live board moved:
**r1=391.17 (0.373 d/leg), r2=682.19 (0.650), [us 932.53 = 0.888], r3=1028.59.** Two teams now below us ⇒
submitting today = rank-3. The 682 INTERMEDIATE refutes the long-standing "no intermediate rank ⇒ EV≈0".

## Step 0 — the verdict chain (questioned)
A 10-deep chain of REACHABLE↔WALLED flips (E-709→E-729), all about **forward-constructing** a complete 601-node
comp0 path: greedy strands 367/601 → fine-tof beam 558/601 @0.51 d/leg (E-710) → under-count fix 575 (E-721) →
insertion/CLS 17-19 strands @~1352d (E-728). Live walls (E-727/729): faithful forward construction + local
repair cascade-defeats (1 city → 300 strands); "rank-1 needs a globally-tight TD 601-order".

## Phase 2 — measured on the bank (kt.fitness pos-control: reproduces 932.5304 exactly)
- makespan = sum_tof **902.9d** + idle **29.6d** ⇒ **97% flight, 3% wait. Timing/waiting is NOT the lever**
  (confirms the E-589 "timing floored" finding — but that was always the wrong axis).
- **Routing is the whole gap.** Per-leg tof: 321 legs ≤0.3d (51d), 388 @0.3-1d (242d), **305 @1-3d = 450d (50%
  of makespan)**, 36 @3-8d (159d), 0 exc. To beat 682 = **−250d**, all reachable from the 305 medium-tof legs.
- **Short hops are abundant** (321 legs already ≤0.3d; E-591/E-726: short-tof subgraph is 601/601 strongly
  connected, 10-30 cheap neighbours/node/epoch). The bank simply ROUTES through 1-3d edges where ≤0.3d edges to
  *other* unvisited nodes exist. This is a pure time-dependent ROUTING/ORDER problem on an already-COMPLETE tour.

## Phase 1 — the load-bearing assumption both prior audits shared
**A-FORWARD: "improving large requires forward-constructing a complete comp0 order from scratch (beam/insertion/
GTSP); the existing complete 932 tour cannot be locally re-ordered to a better makespan because reorder is the
epoch-shift trap (E-587 LKH-per-piece made it worse) and timing is floored (E-589)."**

Why it is the flaw: **the "reorder = epoch-shift trap" verdict (E-587/591) was measured with a FIXED-EPOCH cost
matrix + LKH** — a method that, by construction, *lies* when the order changes (downstream epochs shift, the
matrix no longer holds). That is a property of the *fixed-matrix method*, not of reorder. **The Ch2-medium rank-1
win hours ago (E-734: 189.10→182.11) broke the byte-for-byte identical verdict** ("medium retime-floored at
189.10") using a DIFFERENT evaluator: an **exact labeling DP** (continuous time, track min-arrival per exception
level — waiting allowed ⇒ earliest-arrival dominates) that **re-times faithfully on every candidate order**, so
it has NO epoch-shift trap, driving or-opt/2-opt order search restricted to cheap edges. **This exact machinery
was NEVER applied to large's complete tour.** E-725 started "a faithful order search" but reported no makespan
and was not the medium labeling-DP seeded from the complete bank. Large is the SAME problem (KTTSP, ≤5 exc,
waiting allowed, makespan) at n=1051 — and the faithful cheap-edge windows already exist
(`cache/ch2_giant_faithful_windows.npz`, 141MB).

## Phase 3 — paradigm inventory
| paradigm | touched on large? | survives scrutiny? |
|---|---|---|
| forward beam/insertion/GTSP construction | YES (E-710/713/718/727) | walled (cascade); but it's the HARD way |
| fixed-epoch-matrix LKH reorder | YES (E-587) | trap-bound — but the trap is the *method's*, not reorder's |
| **exact-labeling-DP order search on the COMPLETE bank tour (the medium E-734 method)** | **NO** | **the untried lever — no fixed-matrix lie, faithful per-order retime, starts complete so no completion wall** |
| recompute components on faithful graph + multi-path decomp | partial (E-721 edges; never re-segmented) | open secondary |

## Verdict
**The "932 is reorder-trapped / rank-1 needs intractable from-scratch global TD construction" verdict is FALSE as
stated — it is conditional on the fixed-epoch-matrix METHOD.** The 250d to beat r2=682 is pure routing (305
medium-tof legs, short hops abundant), and the **exact labeling-DP order search that just broke the identical
medium "floor" was never run on large's complete 932 tour.** This sidesteps the entire forward-construction
completion wall (we START complete). Not a guaranteed win, but the single highest-information untried lever, and
it reuses validated machinery.

## Further exploration paths (cheapest information-gain first)
1. **Medium-machinery order search on the complete 932 large tour** — violates A-FORWARD. Generalize
   `ch2_medium_order_search.py` to n=1051 with `ch2_giant_faithful_windows.npz`: exact labeling DP (min-arrival
   per exc level) + or-opt/2-opt restricted to cheap edges, **seed = the complete bank order** (already 601-
   complete, no completion problem). **Binary:** makespan descends below 932 (toward 682) ⇒ reorder trap was a
   method-artifact, the medium lever transfers, rank-2 live. Stalls at 932 with no feasible improving move ⇒ the
   trap is real for large. Cheap (machinery exists; hours to adapt+run).
2. **Same labeling-DP search seeded from the E-710 558/601 beam orders** — violates "completion needs forward
   construction". Let reorder (not forward beam) close 558→601 by relocating the 43 stranded cities into a
   complete tour. **Binary:** reaches 601-complete at <682 pace ⇒ the completion wall was a forward-construction
   artifact; ⇒ confirms forward beam was the wrong frame.
3. **Recompute the 4-component decomposition on the FAITHFUL fine-tof graph, then a 2-segment comp0 split** —
   violates "comp0 = one mandatory contiguous Hamiltonian path" + "components inherited from the blind 8-probe
   graph". **Binary:** faithful graph permits a 2-path comp0 decomposition (each tour-optimizable independently
   then bridged) that beats the single-path beam ⇒ the single-path framing was self-imposed.

Diagnostic only — no bank change, nothing submitted (user-gated). Per CLAUDE.md §5b + the 8h autonomous window,
building probe #1 now.

---
## Probe #1 RESULT (2026-06-28, in progress) — fine oracle works; faithful reorder helps but is decelerating

Built the medium-machinery order search for large; the path produced three concrete results:

1. **Dense-table evaluator is mis-resolutioned (NOT the answer).** Built a full faithful window table (epoch
   0-960, tof≤4d, dep_step 0.5d, sharded 3×, 25,601 edges, 289MB). The bank's comp0 segments STRAND on it: the
   coarse 0.5d departure grid + 4d tof cap makes the greedy walk take long-tof entries, drift ~2d/leg, and
   strand. Re-confirms E-710's "need fine resolution" — but see #2.
2. **E-710's "~0.002d narrow cheap-tof bands" claim is REFUTED.** Measured cheap-departure bands at 0.005d
   resolution on 4 comp0 edges: cheap departures are **WIDE** — (2,847),(224,34),(351,106) are cheap across
   ~100% of a 40d window; (374,1040) 99%. The bands are not the obstacle; the coarse table was.
3. **A FINE LOCAL oracle reproduces the bank faithfully and is fast enough.** `earliest(i,j,t)` =
   `cheap_first_tof` over [t,t+6] at 0.02d, tof≤8.5d, cached by 0.2d epoch-bucket. Walks the bank's s0 segment
   (267c) to **379.3d vs bank 380.4d** — faithful, ~10s. (`scripts/ch2_giant_comp0_finesearch.py`.)

**Faithful reorder lever — measured (segmented, fixed endpoints + entry epochs):** or-opt/2-opt per comp0
segment from its bank entry epoch. After ~25min: s0 −16.7d (1.174→1.111 d/leg), s1 −8.6d, s2 −8.6d =
**~34d total and still dropping, but clearly DECELERATING** (most of s0's gain by it~800). To beat r2=682 needs
comp0 **−250d** (segments to ~0.65 d/leg); the segmented reorder is tracking toward a plateau **far short** of
that. **Tentative verdict (b): faithful local reorder gives a genuine but MARGINAL gain — it refutes the absolute
"reorder is trapped" claim (E-587), but does NOT reach rank-2; beating 682 needs a globally-tight TD optimizer
(free segment boundaries / inter-segment moves / the competitor's solver), which the segmented probe deliberately
does not attempt.** Full plateau still accumulating (2opt + thread-capped restart running). The ~34d+ IS a real
improvement to the 932 bank (→ ~900d) but does not change rank (still >682). Continuing to pin the plateau before
finalizing (b) and deciding probe #3 (global free-boundary reorder / faithful-oracle beam completion).
