---
id: C-012
type: concept
status: confirmed
tags: [astrodynamics, ch2, lambert, pattern]
scope: astrodynamics/lambert + algorithm/per-leg-search
confidence: high
created: 2026-05-20
sources:
  - "SpOC4/Challenge 2/utils_users.py (official find_transfer helper)"
  - "[[E-022-ch2-banked-145d-cluster-insertion]]"
related: ["[[C-006-lambert-problem-and-orbital-tsp]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[E-022-ch2-banked-145d-cluster-insertion]]", "[[O-008-ch2-cheap-window-density-per-pair]]"]
---

# C-012 — Earliest-feasible-tof (the `find_transfer` pattern)

*Primer for non-experts: the per-leg search that unlocked Ch2 — pick
the shortest time-of-flight that's still feasible, not the cheapest
delta-v one.*

## Definition

For an ordered tomato pair (i, j) and a *fixed departure epoch*
`t_start`, the **earliest-feasible-tof** is:

```
tof*(i, j, t_start, Δv_max) :=
  min { tof ∈ [min_tof, T] : ΔV(i, j, t_start, tof) ≤ Δv_max }
```

i.e., the *smallest* time-of-flight at which the Lambert-derived ΔV
satisfies the threshold, scanning tof on a fine grid (the official
SpOC4 helper uses 1000 steps over a configurable window).

Crucially this is **not** the same as the global-min-ΔV tof for the
pair: cheap (low-ΔV) windows often sit at long tof (~30 d for our
small instance, [[O-008-ch2-cheap-window-density-per-pair]]), but a
*shorter* tof at a slightly higher ΔV (still ≤ Δv_max) is admissible
and may be much better for *makespan*.

## Why it matters here

Ch2 minimises total mission time, not total ΔV. The naive precompute
(*min-ΔV tof per pair*) gave us a static graph with cheap legs at
median tof = 33 d → 48 cheap legs sum to ~1312 d, far above the
200 d horizon (E-020/E-021). Five chained CP-SAT variants over
point-windows were proven INFEASIBLE precisely because the precompute
had baked in long tofs.

Switching to **earliest-feasible-tof** changes the per-leg trade
fundamentally: each leg now contributes the *minimum time it can*,
at any admissible ΔV ≤ 600. Median tof becomes 4–8 d for many legs,
turning a 1312-d-sum problem into a 70–150 d makespan instance.

This is the inversion that produced the first banked Ch2 small
(E-022, makespan 145.80 d → polished to 143.79 d).

## Mechanics

A scan, not a numerical optimiser:

```python
for tof in np.linspace(min_tof, tof_window, n_steps):
    if compute_transfer(i, j, t_start, tof) <= Δv_max:
        return tof, that_dv
return None
```

- `tof_window`: how long to look (5–18 d typical; longer windows
  catch slower transfers between distant orbits).
- `n_steps`: resolution. The official helper uses 1000 steps; we
  use 120–180 for the parallel greedy (~5–10 ms ΔV resolution
  in tof).
- Often paired with **waiting**: if no `tof*` exists at `t_start`,
  advance `t_start ← t_start + Δ` and retry — sometimes a later
  departure has access to a shorter feasible tof.

## Where to use vs avoid

**Use** when:
- the objective is *time* (makespan, arrival), not ΔV;
- per-leg feasibility threshold dominates (Δv_max constraint with
  budgeted exceptions);
- the (td, tof) ΔV surface is smooth-ish at each fixed t_start.

**Avoid / supplement** when:
- the objective is total ΔV (then min-ΔV tof is the right primitive);
- the chosen leg's tof leaves no out-arc for the next node (a
  greedy trap — needs cluster-aware insertion C-013 to recover).

## In practice

`src/esa_spoc_26/ch2_findtransfer_greedy.find_earliest_transfer`
implements this with a configurable `tof_window` and `n_steps`,
plus a wait-fallback (advance `t_start`) and a cheap-vs-exception
threshold ladder. The parallel constructive search
`greedy_findxfer` calls it for each (cur, j) candidate per step
and picks the j minimising arrival time `t_start + tof*`. Best
partial: 45 of 48 legs from start=34 in 159.4 d, completed via
[[C-013-cluster-bridge-insertion-pattern]].

## References

- SpOC4 official helper `find_transfer(i_from, i_to, t_start,
  dv_threshold, max_time=5.0, n_steps=1000)` in `utils_users.py`.
- E-022 banked makespan 145.80 d (polished to 143.79 d).
