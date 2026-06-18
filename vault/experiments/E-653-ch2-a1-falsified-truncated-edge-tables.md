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
candidate, overturning the architecture-conditional EV≈0 in [[ch2-large-first-bank-topology]]).

## Methodology

Fits the gap decomposition (not a free-floating "new lever"): the short/wide-epoch edges are exactly
the missing rows behind the flight-time inflation E-651/E-652 quantified. Probes were instrumented
per [[feedback-instrument-experiments]] (startup control + per-chunk progress + verdict line).
