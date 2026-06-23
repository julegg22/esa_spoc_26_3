---
id: E-705
type: experiment
status: REFUTED (no bank change) — Ch2-small lever (b), the tof>8d table-coverage hypothesis, is dead.
  The ultrafine table caps tof at 8.0d; a cheap decisive probe shows extending tof to 25d adds an
  earlier-arriving cheap edge for only 3/1157 edge pairs (0.26%). The competitor's sub-112.996 does NOT
  come from long-tof transfers (consistent with their ~2.1 d/leg = short legs). The last open Ch2-small
  thread is closed.
date: 2026-06-23
tags: [ch2, small, refuted, tof-coverage, probe, ceiling]
related: [[E-703-ch2-small-cpsat-and-tdtsp-reaudit]], [[ch2-small-floor-14292]]
---
# E-705 — Ch2-small: tof>8d table-coverage hypothesis (lever b) — REFUTED

## Mandate
After E-703 exhausted the fast methods, the lone untested Ch2-small hypothesis was: our ultrafine table
caps tof at 8.0d (bank's longest leg 6.45d), so a better order might use a cheap (dv<=100) tof>8d
transfer we never scan. User greenlit lever (b).

## Cheap decisive probe (before any multi-hour extended rebuild)
A long-tof cheap edge only helps makespan if **departing now on it arrives EARLIER than waiting for the
table's next short cheap window**. `ch2_tof_ext_probe.py`: for each of the 1157 edge pairs at a coarse
epoch grid, scan tof in (8,25]; count pairs where an extended-tof cheap edge arrives earlier than the
8d-cap table's best cheap option from that epoch.

## Result — NEGATIVE
**3/1157 pairs (0.26%)** gain an earlier-arriving cheap edge via tof>8d (29 epoch-instances total).
Far below the ~50-pair bar that would justify the extended-table rebuild. Extending tof adds
essentially no earlier-arrival cheap reachability.

## Why (and the physical prior, confirmed)
Cheap long-tof transfers exist but are SLOW — departing-now on a 10-25d transfer rarely beats the
table's existing short cheap windows. And the competitor's 101.65d = ~2.1 d/leg is LOWER than our
2.3 d/leg, i.e. SHORTER legs / less waiting — long legs would raise the average. So their edge is not
long-tof coverage. Hypothesis refuted.

## Verdict — Ch2-small at our ceiling
Lever (b) closed. Combined with E-702 (joint-basin optimal on the official metric) and E-703 (CP-SAT
intractable, routing coupling-violating, no fast faithful evaluator), **every concrete Ch2-small
hypothesis is now exhausted**. 112.996 is our ceiling (rank 6). The competitor's 101.65 comes from a
construction/search we have neither built nor can cheaply identify; no remaining lever fits our compute.

## Campaign status
Both rank-moving levers refuted this session: (a) trajectory assignment re-match (E-704), (b) Ch2-small
tof>8d (E-705). The session's headline win — the E-701 eccentric-departure fix, **Ch1 trajectory
+67,742 kg (263,119 -> 330,861, 400/400 filled, rank 6)** — stands secure. Campaign at its ceiling for
available methods. Methodology note: the cheap-probe-before-build discipline (E-704 sample, E-705 probe)
correctly killed two multi-hour dead-ends.
