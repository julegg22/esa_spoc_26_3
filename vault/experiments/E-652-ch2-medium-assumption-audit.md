# E-652 — Ch2-medium assumption audit (rank 1, but ~2.13× the bound)

**Premise (user):** apply the audit even though we are rank 1 — rank 1 ≠ optimal.

## Ground truth

- `medium.kttsp`: n=181, **min_tof=0.01, max_time=500**, dv_thr=100, dv_exc=600, n_exc=5.
  Bank **189.10 d (rank 1**, beats live r1=195.68). No competitor above us ⇒ gap is to the
  THEORETICAL bound.
- Bank makespan = **flight Σtof 177.22 (94%) + waits 11.88 (6%)** — flight-dominated (like large).
- **Static-flight LB ≈ 89 d** (sum of each bank leg's min cheap ToF over free epochs; sampled
  ratio walked/static = 1.99). **Makespan 189.10 = 2.13× this bound.**
- Per-leg smoking gun: **walked median ToF 0.804 d vs each leg's best-epoch min cheap ToF
  0.126 d ⇒ ~6× per-leg inflation** from being at the wrong epoch.
- Only 3 branches (E-027 stalls, E-037 cluster-decomp, **E-040/E-568 ultrafine RETIME**).
  Medium reached rank 1 **purely by retiming the OLD walk_perm_chrono+LNS order** (228→192.9
  →189.1) — the order was NEVER globally re-searched for walked time. Precompute ToF grid
  COARSE (E-531: 50 pts, step ~0.24 d, floor 0.025 while min_tof=0.01).

## The flaw (same as Ch1 / small / large)

Optimized a PROXY (cheap-graph cost) and only the SCHEDULE of ONE inherited order; never the
walked-time objective over (order, schedule) jointly. "Retiming converged ⇒ done" is false —
it converged for the wrong order. Rank 1 hides ~30–40% headroom.

## Gap accounting

Static-flight LB ~89 d; we sit at 2.13×. ~88 d of the 189 is flight-time inflation from epoch
misalignment (each leg flown ~6× slower than its best epoch allows), NOT tour quality. By
analogy to Ch2-large (leader ~1.25× its static LB), medium's true optimum is plausibly
~110–130 d ⇒ **even at rank 1 we may leave ~60–80 d (30–40%) on the table.**

## Assumptions (same KTTSP A1–A6 as [[E-650-ch2-small-assumption-audit]] / [[E-651-ch2-large-assumption-audit]])

A1 table (ToF [0.025,12]/50pts, coarse) — *leg at ToF<0.025 or between grid steps*. A2 order
inherited, only retimed — *order chosen for walked makespan*. A3 forward waits — *optimized
waits hitting the 0.126-d window*. A4 ΔV-feasibility not time. A5 exceptions=connectivity.
A6 189.10 is the retiming floor of one order, not the optimum.

## Plan — PROPOSED (the SHARED time-expanded engine serves all 3 Ch2 instances)

- **M1** time-expanded retime with UNBOUNDED waiting on the bank order (falsifies A3/A6):
  how much of the 88 d is recoverable by waiting on the current order vs needs reorder.
- **M2** fine + short-ToF edge probe (falsifies A1): the 6× gap predicts the coarse 0.24-d
  grid + 0.025-d floor miss short cheap ToFs.
- **M3** time-expanded greedy construction (falsifies A2/A4) — SAME engine as small-S3 / large-L3.

## ★ CAMPAIGN-WIDE SYNTHESIS

All three Ch2 instances (small wait-dominated; medium+large flight-dominated) AND Ch1-trajectory
share ONE flaw: **we optimized a proxy, never the real objective** (per-pair ΔV not assignment /
order not schedule / static cheap cost not walked time). The missing lever on small + medium +
large is the SAME: a **time-expanded / joint (order, schedule) global search on the official
evaluator**. Medium is the cleanest proof (rank 1 yet 2.13× the bound, reached by retiming alone).
**Build the time-expanded engine ONCE → validate on medium (strong bank) → retrofit to small +
large.** Highest-leverage move on the board. Ch1-trajectory's analogous fix already banked
+23,583 kg (E-647/649). See [[architecture-change-on-large-gaps]], [[basin-overarching-search]].
