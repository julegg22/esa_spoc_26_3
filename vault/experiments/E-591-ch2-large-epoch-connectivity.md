---
id: E-591
type: experiment
tags: [experiment, ch2, large, kttsp, epoch-connectivity, cheap-graph, r1-gap, sampling-artifact]
date: 2026-06-13
status: DIAGNOSTIC (no bank change) — heavy nodes are NOT intrinsically expensive; the 2.2× r1 gap is a ROUTING/PARTITION problem (cheap neighbors exist at every epoch but were consumed earlier in the bank tour). BUT the gap is dominated by the 305 medium 1–3 d legs (450 d), not the 36 heavy legs (159 d) — so closing it needs a global re-partition, not heavy-tail relocation.
instance: ch2-large (hard.kttsp, n=1051)
scripts: scripts/ch2_e591_epochconn_heavy.py, scripts/ch2_e591_epochconn_alltargets.py
logs: runs/ch2_e591_epochconn.log, runs/ch2_e591_alltargets.log
data: /tmp/ch2_large_epoch_conn.json, /tmp/ch2_large_epoch_conn_alltargets.json
related: [[E-589-ch2-large-retime-dp-timing-floor]], [[E-590-ch2-large-endgame-reorder-null]], [[E-587-ch2-large-lkh-trap-and-waiting-lever]], [[E-034-ch2-large-epoch-aware-reorder]]
---

# E-591 — Ch2 large: the r1 gap is ROUTING/PARTITION, not intrinsic-node connectivity

## Question
After E-587 (LKH reorder = epoch-shift trap), E-589 (retime-DP floors timing),
E-590 (endgame reorder NULL), every bounded lever on the fixed 5-exc topology is
exhausted at bank 932.53 d. E-590's structural finding: the heavy-tof tail nodes
(flagged 739, 343, 753) had **0/20 cheap transfers to RANDOM targets at their bank
epochs**. Hypothesis to test: do these nodes have cheap transfers at SOME OTHER
epoch (⇒ epoch-assignment problem, a global TD rebuild could exploit it), or at NO
epoch (⇒ instance-inherent)?

## Bank makespan decomposition (the decisive macro-fact)
Bank = **932.5304 d**, feasible, viols [0,0,0,0], 5/5 exc bridges. Re-confirmed.
Walking the bank decision vector directly (it carries explicit times/tofs):

| leg bucket | count | tof sum | % of makespan |
|---|---|---|---|
| short, tof ≤ 1 d | 709 | 293.5 d | 31% |
| **medium, 1 < tof ≤ 3 d** | **305** | **450.4 d** | **48%** |
| heavy, tof > 3 d | 36 | 159.0 d | 17% |
| idle / waiting (makespan − Σtof) | — | 29.6 d | 3% |
| **total** | 1050 | 902.9 d Σtof | 932.5 d |

**All 36 heavy legs use Δv ≈ 99.x m/s (just under the 100 cheap threshold) — none
are exception bridges.** They are "barely-cheap, long-tof" transfers the chrono
walker accepted as the cheapest sub-100 option available at that point in the tour.

**Even zeroing ALL 36 heavy legs only reaches ~773 d** — still 1.82× r1. The gap to
r1=424.62 (508 d to close) is dominated by the **305 medium 1–3 d legs**, i.e. the
bank's *average leg is ~0.86 d* but r1 implies ~0.40 d/leg (424/1050). The whole
tour's per-leg cost is ~2× too long. **This is a global partition/ordering problem,
not a heavy-tail-relocation problem.**

## Epoch-connectivity scan + the sampling-artifact correction
**Scan A (broad, 25-target random sample):** 37 nodes × 75 epochs over [0,3000 d],
count cheap (Δv<100) outgoing transfers to 25 random targets. Result: 14 "epoch-
flexible", 22 "0/75 at every epoch" — INCLUDING all of 739/343/753. This *appeared*
to say the heavy nodes are intrinsically expensive.

**Scan B (decisive, ALL 1050 targets) for 739/343/753:** 16 epochs × every target.
This OVERTURNS scan A's read for the flagged nodes:

| node | cheap (Δv<100) targets per epoch (min–max over 16 epochs) | total hits | verdict |
|---|---|---|---|
| 739 | **14–29** | 305 | NOT intrinsic — cheap at every epoch |
| 343 | **10–16** | 239 | NOT intrinsic — cheap at every epoch |
| 753 | **7–16** | 231 | NOT intrinsic — cheap at every epoch |

The "0/75" in scan A was a **small-random-sample artifact**: each node's cheap
neighbors are a SPECIFIC sparse set (739→{984,571,893,198,346,...},
343→{947,819,131,945,...}), and a 25/1050 (2.4%) random draw systematically missed
them. Spot-checking the realized transfers: **739→984 is a 0.45 d / 81 m/s cheap
leg; 343→131 is 1.25 d; 343→945 is 1.35 d** — short-tof cheap transfers DO exist,
just to specific nodes. The same artifact almost certainly inflates scan A's "22
intrinsic" count across the other heavy sources too.

## Verdict (corrected)
**(a/b) The heavy nodes are NOT intrinsically expensive — they are routing-locked.**
739/343/753 each have ~7–29 cheap (and several short-tof) neighbors at *every* epoch
across the whole horizon. The bank used a 4–7 d heavy leg out of them only because
those cheap neighbors had already been visited earlier in the bank's chrono walk
(an ordering/partition constraint), not because cheap transfers don't exist.

**(c) The r1 gap is an ACCESSIBLE routing/partition problem in principle, but its
mass is in the 305 medium legs, not the heavy tail.** A different
partition + visit-order (co-optimized under a chrono walk) that pairs each node with
one of its short-tof cheap neighbors *at the time it is visited* is what r1 must be
doing. This is exactly the "from-scratch global time-dependent solver" hypothesis —
and the connectivity data SUPPORTS that it could work, contra E-590's intrinsic
reading. There is no proven physics floor at ~882 d; the cheap-graph is rich enough
(every node has ~10–30 cheap neighbors at all epochs) to admit a much shorter tour
IF the global order/partition co-optimization finds it.

**(d) Rough floor estimate.** Lower bound is NOT well-approximated by "relocate the
36 heavy legs" (that only buys ~159 d → 773 d). The real question is whether the
*whole* tour can drop from 0.86 to ~0.40 d/leg. r1=424.62 demonstrates a 1051-node
tour at ~0.40 d/leg IS achievable on this instance, and our connectivity data shows
the cheap-edge supply (10–30 cheap neighbors/node/epoch) is sufficient in principle.
So ~424 d is *plausibly reachable* — but only via a global re-partition + re-order
that our bounded LNS/LKH/retime levers structurally cannot reach (they perturb a
fixed partition; they don't rebuild it). **The lever is a from-scratch global TD
constructor (cluster-decomp + LKH/Concorde on a chrono-correct cost, the inferred
TGMA approach), worth a multi-day attempt — NOT another within-topology polish.**

## Caveats / honesty
- Scan A's 25-target verdict (14/22) is in `/tmp/ch2_large_epoch_conn.json` but is
  unreliable for the "intrinsic" label (sampling artifact, proven by Scan B). Trust
  Scan B's all-targets result for the flagged nodes.
- "Cheap neighbor exists at every epoch" ⇏ "a feasible 1051-node Hamiltonian tour at
  ~0.4 d/leg exists" — that's a global constraint this per-node scan cannot prove.
  It only rules OUT the intrinsic-floor objection and re-opens the global-rebuild
  path. Building the actual short tour is the (multi-day) follow-up, not this
  diagnostic.
- No bank change. No feasible <932.53 d candidate was found (none sought; diagnostic).
- Compute: Scan A ~1120 s, Scan B ~1199 s, 2 cores.
