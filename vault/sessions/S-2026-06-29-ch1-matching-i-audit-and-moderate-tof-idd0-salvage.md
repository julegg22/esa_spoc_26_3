# Session 2026-06-29 — Ch1 matching-i deep audit (walled) + moderate-TOF idD=0 bug → lever salvaged

Autonomous window (user away 2h, "keep optimizing, never stop"). Submissions stay gated.

## What happened

### 1. matching-i deep audit (E-756) — WALLED, gap is BASIN not neighborhood
User asked `/deepaudit ch1 matching-i` (missed attacks / alternative optimization). Measured:
- Candidate set FULL (25,000 triples, 5 per E-node) — pruning is not the flaw.
- Bank 33,490.458 is a **MAXIMAL matching** (0 free insertions); 521 nodes unmatched.
- LP relaxation **34,120.53, 45% fractional** (loose) ⇒ LP-based methods (CP-SAT, rounding) weak.
- Leader +65 (0.19%); leader is 1.66% under the LP ⇒ a better PRIMAL by better SEARCH (not exact
  solver), same as E-673 matching-II.

Ran all 3 audit experiments (+ a 4th neighborhood):
- Cardinality-augmenting ejection trees (best-choice, depth-5, double-conflict branching): **0** wins.
- Same-cardinality k-cycle exchange (depth-5): **0** wins.
- Lagrangian dual-guided primal (reused E-673b `ch1_lagrangian_auction.py i`): **30,245 = −3,245**.
- Ruin-and-recreate LNS (related-removal + perturbed exact CP-SAT rebuild + SA, `ch1_matching_ruin_recreate.py`):
  bank is cluster-optimal under un-noised rebuild (K≤250); perturbed basin-crosser ran 40+ min / 100k+
  iters across seeds 7/13/29 → **never crossed 33,490**.

⇒ Bank 33,490 is locally optimal under SIX neighborhoods. The +65 is a **different-basin** gap
([[basin-overarching-search]]), not reachable by any local move or aggressive diversification we have.
Verdict: effectively walled for our reach (corrects E-615 "ceiling" framing → basin-lock). Basin-crosser
left running (cheap, low prob).

### 2. moderate-TOF fleet (E-757) — idD=0 validation bug → fleet refuted, but LEVER SALVAGED
Assembling the E-754 moderate-TOF fleet gains applied **0/246**. Root cause: `ch1_backshoot_ecc.py:71`
`official_row` hardcodes **idD=0**, so mass uses `cld[idL,0]` not the assigned delivery → inflated.
All 4 fleet "winners" (+611 kg) are **losses** at the real idD (e.g. (381,104): reported 747, real 421
< bank 545). The assembler's correct-idD revalidation already rejected them (bank 365,597 safe). Fleet
stopped (freed 3 cores). **Classic faithful-evaluator bug, caught per CLAUDE.md §5a.**

BUT the cargo cap is NOT the wall: all 250 circular pairs are **rocket-mass-limited**, cargo cap ≫ mass
(5,000–11,000 vs ~800 kg even at dt=40). And the correct-idD forced-test confirms **(125,329): ΔV
4799→4126 @36d (−673 m/s)** — moderate TOF genuinely lowers circular-capture ΔV ⇒ converts to mass.
⇒ Built `ch1_moderate_fleet_v2.py` (REAL-idD validation, lowest-mass-first) and launched (shards 0,1).
This is the salvaged top live Ch1 lever (trajectory is rank 7, big room). Multi-hour, resumable, banks
to `cache/ch1_moderate_v2_fleet_w*of3.json`, assemble with `ch1_stm_assemble.py`.

## Banks (unchanged this session; all HELD/submitted as before)
medium 182.11 (r1 held), large 879.53 (r3 held), small 112.996 (r6), ch1 traj 365,597 (r7),
matching-i 33,490 (r4), matching-ii 73,253 (r4). Sandbags submitted for medium/large.

## Left running at session end
- `ch1_moderate_fleet_v2.py` shards 0,1 — salvaged trajectory lever (the productive one).
- `ch1_matching_ruin_recreate.py` seed7 — matching-i basin-crosser (walled, low prob).

## Next
- When v2 fleet accumulates wins: `ch1_stm_assemble.py` → updated trajectory.json → escalate resubmit.
- Launch v2 shard 2 when a core frees (matching-i basin-crosser can be killed if needed).
- Deadline reveals (medium 182.11 r1, large 879.53 r3) remain the dominant guaranteed points.
