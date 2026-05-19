---
id: O-008
type: observation
status: confirmed
tags: [ch2, structure, time-windows]
source: "src/esa_spoc_26/ch2_kttsp.py compute_transfer; 0.25-d t_dep scan over [0,200] at static-tof for 6 sample pairs"
created: 2026-05-19
referenced_by: ["[[T-008-ch2-right-approach-and-heavy-compute-targets]]", "[[E-018-ch2-cpsat-fullhorizon-still-infeasible]]"]
supersedes:
superseded_by:
---

# O-008 — Cheap pairs have **~100 recurring windows**; expensive pairs none

## Observation

Δv(t_dep, tof=static_tof) scanned over [0, 200] d at 0.25-d step
for 6 representative pairs:

| pair | static (td, tof, Δv) | #≤100 wins | #≤200 | #≤600 | min Δv | median |
|---|---|---|---|---|---|---|
| (30,29) | (5.6, 36.4, **60.0**) | **103** | 51 | 14 | 60 | 105 |
| (25, 2) | (166.0, 33.5, **59.8**) | **121** | 49 | 3 | 60 | 97 |
| (42, 7) | (15.0, 30.9, **60.8**) | **105** | 56 | 19 | 61 | 102 |
| (0, 28) | (163.9, 16.2, 301.9) | 0 | 0 | 175 | 302 | 857 |
| (3, 8) | (153.6, 28.9, 459.4) | 0 | 0 | 149 | 459 | 710 |
| (1, 17) | (103.0, 5.2, 515.7) | 0 | 0 | 67 | 523 | 1111 |

(window-count = number of contiguous t_dep regions where Δv ≤ thr;
fewer at higher thr because regions merge.)

## Why it matters — the heavy-compute target validated

1. **Cheap pairs (Δv_min ≤ 100): ~100 recurring narrow windows in
   [0, 200]** — the synodic-beat period of two near-co-orbital
   tomatoes is ~2 days, so cheap-transfer windows recur ~100 times.
2. **Expensive pairs: no cheap window at any time** — their physics
   floor is Δv_min ≥ 300 m/s; they only enter as exception edges
   (within ≤600), and have many wide windows there.
3. **E-018's single-window CP-SAT was artificially restricted** to
   *one* (t_dep, tof) per used edge — that's why chronology broke.
   **Multi-window CP-SAT has ~100×-flexibility** per cheap edge to
   pick a window compatible with the chronological order.

## Implication (heavy compute, T-008)

The right heavy-compute target is concrete and bounded:
- **Multi-window precompute**: per pair, extract its cheap-window
  list (e.g., up to K=8 well-separated windows per pair). For small:
  138 cheap pairs × 8 + 837 exception-eligible pairs × ~5 ≈ 5–6 k
  windows; parallel mp.Pool — minutes.
- **Multi-window CP-SAT**: arc-window BoolVars + chronology
  (`T_i ≤ td_k, T_j = td_k+tof_k` if window k of arc (i,j) used) +
  exactly-one-window-per-used-arc + ≤5 exceptions + min makespan.
  Same structure as `ch2_cpsat_tw` but with multiple windows per
  arc → enormously more flexibility.
