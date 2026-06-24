---
id: E-043
type: experiment
tags: [experiment, ch2, large, kttsp, diagnostic, phase-miss, ring-sweep, topology]
date: 2026-06-12
status: DECISIVE — ~500d of the 624d gap to r1 is intra-ring phase-miss (ordering), not forced; bridges are cheap; ring-sweep construction justified, windowed-LNS refuted
instance: hard.kttsp (n=1051)
script: scripts/ch2_e579_large_legslack.py
related: [[E-041-ch2-large-gap-decomposition]], [[E-042-ch2-large-td-tsp-characterization]], [[E-034-ch2-large-epoch-aware-reorder]], [[E-034-ch2-large-epoch-aware-reorder]], [[E-034-ch2-large-epoch-aware-reorder]]
---

# E-043 — Ch2 large: per-leg slack + ring-membership decomposition

## Instance geometry (read directly from hard.kttsp)

n=1051 tomatoes in **two physical co-orbital shells**, near-circular
(e≤0.01), shared node line (RAAN≈0):

- **small shell**: a≈3747 km, period **0.238 d**, **450 nodes**, planes
  at inc {0°(150), 90°(150), 180°(150)}.
- **big shell**: a≈14989 km, period **1.906 d**, **601 nodes**, dense
  planes at {0°(~156), 90°(163), 180°(157)} + 13-node minor planes every
  15°.

Within a shell+plane "ring", all members share `a` (±0.3%) → relative
phases drift only on ~75 d timescales → a ring is a near-fixed circular
arrangement of targets. A within-ring hop is a **phasing maneuver**:
catching a target *ahead* in phase is cheap (≈0.05–0.15 d); catching one
*behind* costs nearly a full relative lap (1–2 d). The E-533 "4
components, 0 cheap inter-component edges" are these physical rings, NOT a
clustering artifact of one epoch.

## Diagnostic (E-579, decisive, not a search)

For each of the 1050 realized bank legs, at the bank's own departure
epoch, compared realized tof against the cheapest `find_earliest_transfer`
to any still-**unvisited** node (candidate set = same-shell ring members
+ random control; faithful because cheapest reachable is always
same-ring). Tagged each leg intra-ring vs cross-ring.

| quantity | value |
|---|---|
| bank tof_sum (= makespan, idle 0) | **1049.0 d** |
| Σ best-reachable-unvisited over legs | **524.4 d** |
| recoverable slack Σ max(0, realized−best) | **499.2 d over 665 legs** |
| long legs >0.5 d that had a cheaper unvisited option | **518 / 650** |
| └ recoverable on those | 463.0 d |
| **cross-ring (bridge) legs** | **43 legs, 123.9 d total** |
| intra-ring legs | 1007 legs, 925.1 d |
| **intra-ring legs >0.5 d (phase-miss)** | **617 legs, 513.5 d excess over 0.5** |

## Conclusion

**~500 d of the 624 d gap to r1=424.62 is intra-ring phase-miss —
ordering, not a physical floor.** On 518 of 650 long legs a cheaper
unvisited hop existed at that very epoch; the bridges (cross-ring) are
already cheap and few (43 legs, 124 d). The bank routes ring members out
of phase order and pays 0.5–3 d catch-up legs repeatedly.

Note Σ best-greedy = 524 d sits *above* r1=424: greedy-cheapest-each-step
is itself myopic (scatters far ring members to the endgame). The global
**phase-sweep optimum** is below greedy → r1≈424 is plausibly the clean
sweep floor, reachable by a global construction, not by local repair.

## Refutes / justifies

- **REFUTES E-578 windowed-LNS-from-bank** as a pole-position lever: it
  repairs local windows but cannot reorder the *global* phase sequence;
  every local gain is wiped by the downstream epoch cascade (consistent
  with E-577's 26,347 dead relocations). Killed both seeds (0 marginal
  pts anyway — our 1048.98 bank already beats r2=1143.56; anything in
  (424.62, 1048.98) stays rank 2).
- **JUSTIFIES E-044 ring-sweep construction**: per (shell, plane) ring,
  sort members by relative phase in the drift direction and hop forward
  (every leg a short catch-up); order rings by bridge phasing; spend the
  5 exceptions on inter-ring bridges; DP/walk re-time; LNS polish on top.
  Matches TGMA's one-shot 1143→424 jump (June 5) = a structural
  construction, not LNS grind.

## Lesson

Decompose a makespan gap by *cause* and by *structural membership* before
choosing a search. Here a ~12 min read-only probe converted "624 d
research frontier" into "≈500 d is intra-ring phase ordering; bridges are
fine" — which names the exact construction to build (phase sweep) and
kills the wrong one (windowed LNS).
