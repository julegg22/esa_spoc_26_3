---
id: E-708
type: experiment
status: BANKED — audit lever 3. Targeted extended-tof re-sweep of the 88 worst high-ΔV trajectory
  transfers (E-707 showed long coast reduces ΔV most on the worst geometries). 58/88 improved (guarded,
  ΔV-only), +24,820 m/s ΔV saved. Assembled + re-ran the idd Hungarian (E-706) since extended dt shifts
  the cap. Trajectory 347,648 -> 356,550 kg (+8,902), officially validated. Session total +93,431.
date: 2026-06-23
tags: [ch1, trajectory, extended-tof, low-energy, audit, banked]
related: [[E-708-ch1-trajectory-extended-tof-sweep]], E-706-ch1-idd-reassign, [[E-701-ch1-eccentric-departure-solver-fix]]
---
# E-708 — Ch1 trajectory: extended-tof re-sweep (audit lever 3)

## Chain
The deep audit (user: "find the flaw, not the optimum") overturned the "exhausted" verdict and produced
three trajectory levers: E-701 eccentric-departure fix (+67,742), E-706 idd/cap re-assignment (+16,786),
and this. E-707 probed whether extended tof reduces ΔV: mixed fleet-wide (mean ~−78 m/s) but the WORST
high-ΔV transfers benefit substantially (the BCP geometry has slack at long coast). So a TARGETED sweep.

## Method & result
`ch1_longtof_sweep.py`: re-solve each filled transfer with ΔV>4400 (88 of them) via the backward-shoot
eccentric solver with tof bound extended to ~130d; guard = keep the new row ONLY if ΔV strictly lower
(pure upside). 3 shards, checkpointed. **58/88 improved, +24,820 m/s ΔV saved** (worst transfers
biggest: 5125→4192 +333kg). `ch1_longtof_assemble.py` swapped them + re-ran the idd Hungarian (extended
dt shifts the cap): raw 353,788 → **356,550** after idd re-opt (+2,762 from re-opt alone, confirming the
cap-coupling). Guard-banked, official + round-trip.

## Standing
Trajectory **263,119 → 356,550 (+93,431 this session)**, rank 6; rank-5 floor 372,729 is now **+16,179**
away (was +42k at audit start). The three levers are all "flaw-finding" wins (mis-scoped objective +
solver-bounded regimes), not grinding. Remaining gap to rank-5 is ~16k of further per-pair ΔV the
backward-shoot solver may still leave (diminishing) + the structurally-different basin E-707 flagged.
