# E-653 — Ch2 A1 FALSIFIED: cheap-edge tables truncated below ToF=0.025 (all 3 instances)

**Result of the S2/M2/L2 short-ToF probes proposed in [[E-650-ch2-small-assumption-audit]] /
[[E-651-ch2-large-assumption-audit]] / [[E-652-ch2-medium-assumption-audit]].** Run 2026-06-18.

## Finding

The precomputed cheap-edge tables (E-526 small, E-531 medium, large precompute) were all built
with a ToF grid floored at **0.025 d**, but the problems allow ToF ≥ 0.01 (small/medium) / 0.0007
(large). The probes scanned the UNSAMPLED short regime and found cheap (ΔV≤100) edges below the
floor that the order searches never had:

- **S2 small:** 6 cheap edges < 0.025 d (e.g. 17→11 ΔV=45.5 @ tof=0.0245; 16→27 ΔV=94.9 @ 0.0245).
  Mostly near the 0.0245 ceiling of the probe → modest per-leg gain, but real.
- **M2 medium:** **207** cheap edges below the floor (e.g. 48→68 ΔV=35.3 @ 0.0245; 40→179 ΔV=36.6).
- **L2 large:** genuinely SHORT cheap edges via wide-epoch sweep — **766→591 cheap @ tof=0.006 vs
  walked 0.783 d** (≈130× faster at the right epoch); 180→890 @ 0.0166 vs 0.766. These directly
  attack the ~562 d epoch-misalignment flight inflation E-651 identified.

⇒ **A1 ("the candidate edge set is complete") is FALSE.** Every Ch2 order search (greedy / LKH /
DP-ALNS / e617) optimized over a TRUNCATED candidate set. This is the Ch2 analog of the Ch1
sparse-candidate-matrix flaw (3.8% dense) that, once densified, banked +26.7k kg.

## Why e617 was basin-locked (confirms the diagnosis)

Launched e617 (4-chain ILS order-search) on the OLD table as the persistent occupant: `accepted=0`,
state pinned at 112.9960 over 600+ iters/chain. Not a bug — the improving moves (shorter-ToF legs)
are absent from its candidate set. Stopped it; the truncated-table search cannot break the floor.

## Fix (in progress)

`scripts/ch2_augment_small_shorttof.py` — merge-min the shortest cheap/exc ToF in [0.001,0.024) into
the small ultrafine table (→ `..._v2.npz`, ~47 min). `scripts/ch2_corrected_table_research.sh`
self-chains: swap corrected table into the load path → e617 4-chain 48h on the CORRECTED edge set.
**Decisive test:** does the corrected table break 112.996? If yes → scale to medium (207 edges) and
large (the high-EV one — short-epoch legs could approach the ~340 d static LB < live r1 424 ⇒ rank-1
candidate, overturning the architecture-conditional EV≈0 in [[E-034-ch2-large-epoch-aware-reorder]]).

## Follow-up (2026-06-18 11:22): corrected table necessary but NOT sufficient for small

Built the corrected small table (524 cheap cells shortened, ToF≥0.001) and ran the order search
(e617) on it. e617 was first FROZEN (accept-band 1% < kick size ⇒ accepted=0); widened RRT_DEV
0.01→0.06 ⇒ it then explored hard (**~6,400 accepted moves over 54 min, 4 chains**) but **best never
left 112.9960 — zero descent.** Combined with S1 (bank-order optimum = 112.996 on the LIVE evaluator,
i.e. already including short edges) ⇒ **Ch2-small is BASIN-ISOLATED at 112.996.** Local search
(destroy-k + cheapest-insertion), even with corrected edges + wide uphill acceptance, cannot reach
the competitor's 101.65 — it lives in a structurally distant basin needing a different CONSTRUCTION
(LKH time-expanded), confirming [[M-general-basin-overarching-search]] / [[O-014-2026-06-07-competitor-algorithm-inference]].

**LARGE architecture-gate (assessed, FAILED):** rank-1 needs makespan HALVING (932→<424) via
near-optimal joint order+epoch on n=1051 — the SAME construction-basin difficulty just shown
unsolved on tiny n=49 small, the corrected table for n=1051 is intractably large, and there is no
intermediate rank (anything short of full halving = 0 pts). Probability of rank 1 = LOW, not HIGH ⇒
do NOT commit cores to a full large corrected-table build (gate per [[M-general-architecture-change-on-large-gaps]]).

**Pivot (lever UNBLOCKED):** `elkai` (LKH wrapper) IS installed in env spoc26. Build = LKH constructs
structurally-different orders on the corrected-table static cost → DP-retime each via the
metric-correct `evaluate_perm_dp` (scores bank=112.9960) → guard-bank if <112.996. Positive control
(LKH/DP must reproduce 112.996 on the bank perm) guards against the e609/e538 metric mismatch
(those reference a coarse 116.37 ≠ official 112.996). NOTE: no standalone LKH binary on PATH; use elkai.

## ★★ CORRECTION (2026-06-18 11:40): "basin-isolated" was an EVALUATOR-MISMATCH ARTIFACT — RETRACTED

A mandatory positive control in the new LKH pipeline caught it: **DP-on-ultrafine-table(bank perm)
= 118.5255, but official bank = 112.9960 — a +5.529d grid-discretization offset.** e617 seeded
`best=112.996` (official) but evaluated candidates with the DP (~117-119) ⇒ no candidate could ever
"beat" 112.996 ⇒ it LOOKED basin-locked. It was a **metric mismatch INSIDE the search** (the exact
"evaluator metric must match SA baseline metric" / "audit the evaluator before blaming search"
trigger — see [[M-general-foundation-then-search]]). e617's chains were sitting at DP-mk 117.1,
i.e. **orders strictly BETTER than the bank's DP-mk 118.53 that it discarded.** "Small basin-isolated"
is RETRACTED.

**Fix (committed):** e617 now baselines in DP-space (`best=DP(bank)=118.53`), dumps every order
< DP(bank) to `/tmp/ch2_e617_dpspace_cand.jsonl`, and the reseed-from-official-bank (which re-froze
it) is disabled. Validated: best descends 118.53→116.38 within 1 min, candidates dumping. The DP
schedule is +5.5d unrefined, so it cannot bank directly — **stage 2 = CMA-refine each dumped order
on the official evaluator (S1 machinery), guard-bank if official mk <112.996.** A 116.38 DP-order
→ ~110.9 official is plausible (< 112.996 ⇒ would beat the floor). This is the joint sequence(LKH/
ILS in DP-space)+epoch(CMA official) search — the never-built lever, now correctly decomposed.
elkai LKH hit an internal precision assertion (deferred); the ILS DP-space search needs no elkai.

## Methodology

Fits the gap decomposition (not a free-floating "new lever"): the short/wide-epoch edges are exactly
the missing rows behind the flight-time inflation E-651/E-652 quantified. Probes were instrumented
per [[M-general-instrument-experiments-before-launch]] (startup control + per-chunk progress + verdict line).
