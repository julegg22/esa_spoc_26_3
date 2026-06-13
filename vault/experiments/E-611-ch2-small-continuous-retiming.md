---
id: E-611
type: experiment
status: done
tags: [ch2, small, kttsp, timing, continuous-retiming, breakthrough, e610-correction, anti-oscillation, hostile-default]

hypothesis: "E-610 declared the Ch2-small evaluator layer CLOSED, bounding the
remaining flight-reduction lever at 1.02 d. But that bound was measured at the
bank's OWN fixed departure epochs t_start[k] -- it held the departure schedule
fixed. The departure schedule is itself a free decision variable. Re-optimizing
departures JOINTLY with tofs (forward earliest-arrival continuous sweep, full
<=100 cheap cap, no MARGIN) on the FIXED bank order should recover makespan the
bank's stored timing left on the table -- potentially far more than 1.02 d,
because each leg's minimum feasible tof is strongly epoch-dependent (orbital
phasing) and the bank sampled only one epoch per leg."

created: 2026-06-13
ran_start: 2026-06-13
ran_end: 2026-06-13
duration_runtime: "gate ~108 s; validate ~110 s; full search 4x1500 s"

# reproducibility
code: |
  /tmp/ch2_small_e611_search.py  (table-free beam-DP + parallel SA; ORIGINAL, FLAWED aggregation)
  /tmp/ch2_e612_refine.py        (corrected: continuous re-timing of each candidate order)
  /tmp/ch2_e612_validate.py      (independent reload + manual per-leg audit through a FRESH KTTSP)
inputs: |
  reference/SpOC4/.../problems/easy.kttsp (n=49, n_exc=5, dv_thr=100, dv_exc=600)
  solutions/upload/small.json (bank order + timing, official mk=116.37377)
  kt.compute_transfer (the official multi-rev Lambert Delta-v -- shared by all teams)
outputs: |
  /tmp/ch2_e612.log, /tmp/ch2_e612_search.log
  /tmp/ch2_e612_bankrefined.json (the validated 114.154 d re-timing of the bank order)
seed: SA seeds 0..3; refiner deterministic (continuous scan + 10x refine)
env: micromamba spoc26, PYTHONPATH=src, OMP_NUM_THREADS=1
---

## The E-611 flaw (why a table-free search reported a false null)
E-611 ran a beam-DP + parallel-SA table-free search to look for a better ORDER.
Its correctness check (line 214) compared the SA's best **coarse-DP-timed**
official makespan (120.578, on a DT=0.1 d departure grid) against the bank's
**continuous** official makespan (116.374) and concluded "nothing beats the
bank" -- apples to oranges. The coarse grid handicaps every candidate ~5-6 d, so
the search discarded its best order. (Flagged as a verification caveat at launch;
confirmed exactly.)

## The E-612 correction + the breakthrough
`ch2_e612_refine.py` re-times each candidate order CONTINUOUSLY via a forward
earliest-arrival sweep: for leg k, scan departure waits w in [0,2] at 0.03 d and
find the shortest tof with dv<=cap (cap=600 if k is a bridge else **100, full,
no MARGIN**); pick (w,tof) minimizing arrival; carry arrival forward. Greedy
earliest-arrival is provably makespan-optimal for a FIXED order+bridge set (each
leg depends only on prev arrival + own departure).

**Correctness gate (the headline):** continuously re-timing the BANK ORDER
itself yields **mk = 114.154 d, feasible** vs the bank's stored **116.374 d** =
**-2.2198 d** on the bank's OWN order. The bank's stored timing was suboptimal
for its own route.

## Independent validation (fresh instance, manual per-leg audit)
`ch2_e612_validate.py` reconstructs x, reloads through a FRESH `KTTSP(easy.kttsp)`
(kt2), and audits every constraint by hand -- NOT trusting the refiner's own path:

| check | result |
|---|---|
| official kt2.fitness makespan | **114.154000** |
| kt2.is_feasible | **True** (fitness vector [114.154,0,0,0,0]) |
| exception legs (dv in (100,600]) | **5** (limit 5; bridges {2,17,26,29,45}) |
| dv>600 violations | 0 |
| max cheap-leg dv | **99.998** (cap 100) |
| chronological violations | 0 (worst slack 0.000000) |
| makespan = times[-1]+tofs[-1] | 114.154000 |
| Sigma tof (flight) | 106.354 d | 
| Sigma wait (idle) | 7.800 d |
| **VERDICT** | **VALID + BEATS BANK by 2.2198 d** |

## Why E-610's "CLOSED" was premature (the methodology lesson)
E-610 measured the flight-reduction lever at the bank's **fixed** departure
epochs and bounded it at 1.02 d -- then declared the evaluator layer closed. But:

| quantity | bank | E-612 re-timing | delta |
|---|---|---|---|
| flight Sigma_tof | 109.99 d | **106.35 d** | **-3.64 d** |
| wait Sigma_idle | 6.38 d | 7.80 d | +1.42 d |
| makespan | 116.374 d | **114.154 d** | **-2.22 d** |

The flight reduction (3.64 d) is **3.6x larger** than E-610's "optimistic" 1.02 d
bound -- because E-610 held **departures fixed**, and a leg's minimum feasible
tof is strongly epoch-dependent. Departing slightly later (net +1.42 d idle) buys
a much shorter realizable tof on several legs (net -3.64 d flight). E-610's
hostile-default audit missed that "departures = bank values" was itself an
unjustified default. **The timing sub-layer was open, not closed.**

## Rank consequence (sober)
114.154 d is a strict improvement but does **not** by itself change the submitted
rank: r5 (R3) = 111.79 d, so 114.154 is still rank #6 (5.00 pts, same as the
116.374 bank). It shrinks the R3 gap from 4.59 d to **2.37 d** -- materially
closer, and it reopens a lever E-610 had declared dead. The full E-612 order
search (4x1500 s, running) tests whether any order beyond the bank's, when
continuously re-timed, crosses 111.79 d into rank #5.

## Full order search result (E-612, 4x1500 s) — a BETTER order, validated
Continuous-refining 14 distinct SA-collected orders found a route that beats the
bank order: **112.996 d feasible, +3.378 d over bank** (independently validated
through a fresh KTTSP + manual per-leg audit: exc 5/5, max cheap dv 99.998, 0
viol, flight 105.616 + wait 7.380). Supersedes the 114.154 bank-order retiming.
Still rank #6 (r5=111.79) but the gap to rank #5 is now **1.21 d** (was 4.59 d).

**Metric-mismatch diagnosis (the methodology trigger "evaluator metric must
match SA baseline metric"):** the winner (cand 13) had a WORSE coarse-DP score
(122.738) than the bank order (122.378) yet refined BEST (112.996). The SA
accepts/rejects by coarse-DP makespan, but the true objective is the
continuous-refined makespan -- so good orders are filtered out before refinement.
Coarse mk is a biased proxy. **Fix = E-613** (/tmp/ch2_e613_deepsearch.py):
decouple cheap coarse EXPLORATION from expensive SELECTION -- keep a wide band
(top-24/chain), seed from both bank and the 112.996 winner, and PARALLEL-refine
all distinct candidates. Targets crossing 111.79 d into rank #5.

## Status / follow-ups
- 114.154 d candidate at /tmp/ch2_e612_bankrefined.json -- VALIDATED, NOT banked
  (bank overwrite is user-gated; escalated). Strict improvement, not yet rank-up.
- Full order search running; if a refined order < 111.79 d emerges -> rank #5 EV.
- E-610's closure claim is CORRECTED here: order/edge/granularity rows hold, but
  the **timing row was not closed**. The transfer-MODEL row (Ch2 A0) remains the
  larger residual to R1, but is no longer the ONLY open row.

links: [[E-610-ch2-small-tof-granularity-bound]] [[E-609-ch2-small-global-order-search]]
[[E-606-ch2-small-edge-resolution]] [[ch2-small-floor-14292]]
[[foundation-then-search-methodology]] [[methodology-triggers]]
[[anti-oscillation-discipline]]
