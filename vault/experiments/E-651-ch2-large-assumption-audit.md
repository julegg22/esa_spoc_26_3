# E-651 — Ch2-large assumption audit (user-driven, 2026-06-17)

**Premise (user):** r1=424.62 is 2× our 932.53 ⇒ "no further gains" is false; find
the flaw, not optimize further. Same KTTSP class as small; scores indicate an
alternative architecture (as Ch1-trajectory + Ch2-small).

## Ground truth

- `hard.kttsp`: n=1051, **min_tof=0.0007 d**, max_time=3000, dv_thr=100, dv_exc=600,
  n_exc=5. Bank 932.53 (rank 2); r1=424.62 (lone outlier).
- **Bank makespan = flight Σtof 902.9 d (97%) + waits Σ 29.6 d (3%)**, first_dep=0.
  median ToF=0.633 d, max wait only 1.31 d (hostile-default cap). **Flight-dominated**
  (opposite of small, where waits were the lever).
- Precompute (`ch2_precompute_fine`) samples **ToF [0.025,8] d, epoch [0,200] d** — but
  problem allows ToF≥0.0007 and the timeline runs to ~932 d ⇒ short-ToF AND most of
  the epoch axis unsampled by that table.
- **Static cheap order ≈ 340 d** (best ToF per leg, free epochs) — *below* r1=424 ⇒ a
  walkable ~424 order exists; our forward-walk inflates the same to 932.

## The flaw

Every branch minimizes a **static/nominal proxy** (cheap-graph tour length / fixed-epoch
matrix — what LKH E-587 optimized, making it worse), then walks epochs forward (waits
capped ~1 d). The static order already nails the routing (340), but the **walked makespan**
— the real objective — blew up to 932. We optimized the proxy, never the walked time.
Prior "epoch-shift-trap = moonshot wall, EV≈0" verdict was architecture-conditional and
wrongly reported as a wall.

## Gap accounting

Static optimum ≈ **340 d**; walked flight **902.9 d** ⇒ **loss ≈ 562 d of flight-time
inflation, ~100% from epoch misalignment** (legs forced into long-ToF windows by forward
propagation), NOT tour quality and NOT waiting. r1≈1.25× the static LB; we sit at **2.74×**.
Loss concentrated entirely in the time-dependent SCHEDULE. Same meta-shape as Ch1 (per-pair
ΔV not assignment) and Ch2-small (order not schedule): optimized a proxy, never the objective.

## Assumptions (violating-solution italic)

- **A1** table captures useful transfers. *A leg at ToF<0.025 d or epoch>200 d.*
- **A2** order chosen by static proxy, epochs walked after. *Order chosen to minimize the
  forward-WALKED makespan.*
- **A3** epochs/waits greedy forward (wait≤~1 d). *Order + optimized waits: long strategic
  waits buying much shorter downstream legs.*
- **A4** route on cheap graph / minimize ΔV. *Minimize TIME: fastest feasible transfer each step.*
- **A5** 5 exceptions = connectivity bridges. *Exceptions placed where they cut most flight time.*
- **A6** epoch-shift trap is a wall (340 unwalkable ⇒ 932 floor). *Time-expanded construction
  keeps legs in short-ToF windows ⇒ 340-class order walks at ~424.*

## Plan (assumption-falsifying, by info gain) — PROPOSED (build after S1/S2 de-risk)

1. **L1** time-expanded retiming with UNBOUNDED waiting on the static-optimal order
   (falsifies A3/A6). If min walkable makespan ≪932 (→~424) ⇒ timing/walk architecture is
   the lever, not the order. (Check E-589 retime-DP allowed generous waiting; if not, new.)
2. **L2** short-ToF + wide-epoch edge probe (falsifies A1): scan ToF [0.0007,0.025) and
   epoch>200 on sample legs; count faster cheap edges the table misses.
3. **L3** (build) time-expanded greedy construction: step by min ARRIVAL time from
   (city,epoch) — walkable + time-minimal by construction (falsifies A2/A4); competitor arch.

Relates to [[ch2-large-first-bank-topology]] (prior moonshot verdict = architecture-conditional),
[[E-650-ch2-small-assumption-audit]] (same flaw), [[M-general-instrument-experiments-before-launch]].
