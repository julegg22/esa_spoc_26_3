---
id: E-587
type: experiment
tags: [experiment, ch2, large, kttsp, lkh, td-tsp, epoch-shift-trap, departure-time-lever, bank]
date: 2026-06-13
status: BANKED — large 942.0744 → 934.4452 d (−7.63 d), feasible (viols [0,0,0,0]), independently re-scored + round-trip via scripts/ch2_e586_bank.py. LKH per-component = clean NEGATIVE (epoch-shift trap at per-piece level); win came from the orthogonal E-588 departure-time waiting lever.
instance: ch2-large (hard.kttsp, n=1051)
script: scripts/ch2_e587_large_lkh.py, scripts/ch2_e587b_large_lkh_guarded.py, scripts/ch2_e588_large_waitlever.py (bg agent a5685879)
related: [[E-586-ch2-large-recovered-lns-bank-971]], [[ch2-large-first-bank-topology]], [[E-034-ch2-large-epoch-aware-reorder]], [[M-applying-methodology-triggers]]
---

# E-587/E-588 — Ch2 large: LKH per-component (negative) + departure-time waiting lever (−7.63 d)

## Setup
NEVER-STOP deep-dive on the rank-2 large instance (bank 942.0744 d, r1=424.62
demonstrated by TGMA = 2.2× gap). Goal: try the ONE per-component solver never
applied here — **LKH (Lin-Kernighan-Helsgaun)** — on the epoch-aware 0.005 d-grid
cost matrix, inside the E-562b sequential epoch-aware re-walk loop (which got us
1536→1049 using OR-Tools GLS). Hypothesis: a far stronger TSP solver breaks the
basin where GLS saturated.

## Result 1 — LKH = clean NEGATIVE (the win was elsewhere)
LKH (via `elkai`) applied cleanly per component. On the dominant comp2 sub-pieces
it found *dramatically* shorter **fixed-epoch** tours (piece 0: 72.05 → 8.65 d
fixed-epoch tof-sum). **But the chrono re-walk inflated every one** — piece 0's
LKH-optimal order walked to 951.63 d, **+9.6 d WORSE** than bank. Guarded-accept
(matrix proposes, chrono walk disposes) correctly rejected all of them.

**This sharpens the E-046 finding from the GLOBAL to the PER-PIECE level: the
fixed-epoch cost matrix is provably exact ONLY while the order is unchanged**
(verified: unchanged-order fixed-epoch tof sum = chrono walk to 0.0, max per-leg
error 0.0). The instant LKH reorders, every downstream node's true arrival epoch
shifts, so `find_earliest_transfer` at the *real* epoch returns different (usually
longer) tofs than the matrix promised. LKH minimizes a quantity (fixed-epoch
tof-sum) **orthogonal to the true objective** (chrono-walk makespan) once order
changes — and a *stronger* solver makes it *worse*, exploiting the stale matrix
more aggressively. **Verdict: pure node-reordering on large is a structural dead
end; a better local TSP solver cannot help.** (Reinforces the proxy⊥reality lesson
in [[ch2-large-first-bank-topology]].)

## Result 2 — the WIN: departure-time (waiting) lever (E-588), −7.63 d → BANKED
The orthogonal lever the LKH diagnosis pointed at: the banked chrono walk takes
the **earliest-feasible** transfer at every leg and only waits ≤~2 d as a
*feasibility* fallback — it **never waits to find a SHORTER transfer**. A greedy
departure-time forward pass (at each leg, optionally wait to catch a cheaper
transfer window) → **934.4452 d, feasible, viols=[0,0,0,0], 5/5 exc, valid
1051-perm** (−7.63 d). Independently re-scored + round-trip banked via
scripts/ch2_e586_bank.py (942.0744 → 934.4452; backups .bak.e586 +
/tmp/bank_bak/large_20260613_063717.json). It traded 17.2 d of added idle for
24.8 d less time-of-flight.

## Structural findings on the 2.2× gap to r1=424.62 (NEVER-STOP payoff)
1. **The makespan is NOT in the 5 exception bridges** (they sum only ~11.5 d). It
   is in **intra-component cheap-Δv legs of comp2** (the 601-node component): its 3
   sub-pieces = ~734 d of the 934 (78%). 41 legs have tof>3 d summing 218.7 d,
   single legs up to **18.4 d** tof.
2. **A timing lever exists that node-reordering structurally cannot reach.** 18 of
   43 expensive legs have much cheaper transfers a few days later (leg316
   18.42→6.59 d by +8 d wait; leg697 9.76→4.35 d by +1.5 d). Naive waiting-lever
   headroom ≈ **32.8 d** (floor ~909 d); the greedy pass captured only 7.63 d of
   it — greedy myopia (early waits cost idle now, pay off only downstream) leaves
   the rest.
3. **The residual ~510 d gap to r1 is dominated by JOINT order+timing optimization
   of comp2** — neither pure reorder (epoch-shift trap) nor pure greedy waiting
   (coupling-limited) unlocks it. r1=424.62 almost certainly uses a true
   time-dependent solver co-optimizing node order AND departure epoch. **That
   basin needs a from-scratch global time-dependent solver, NOT a stronger local
   solver bolted onto the patched architecture** — consistent with the three prior
   failed global attacks (E-042/044/046).

## Next lever (launched: agent ae456981)
Non-greedy / DP departure-time optimization on the FIXED 934.45 order (the greedy
E-588 pass is its degenerate special case → clear headroom toward ~909 d), then
small local reorders coupled with timing on comp2's expensive legs, always
evaluated by the chrono walk + waiting (never a fixed-epoch matrix). Seeded from
the new 934.45 bank.

## EV / verdict
Mechanically clean −7.63 d but **point-EV ≈ 0** (large stays rank-2, r2=1143.56,
margin widened). Value is the **method finding**: (a) per-piece LKH negative
closes "use a stronger TSP solver" definitively; (b) the departure-time lever is a
NEW, still-open axis (greedy already paid; DP/joint version unexplored). Scripts:
ch2_e587_large_lkh.py (diagnostic), ch2_e587b_large_lkh_guarded.py (the clean
negative), ch2_e588_large_waitlever.py (the win).
