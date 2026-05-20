---
id: E-022
type: experiment
status: done
tags: [ch2, breakthrough, banked, find-transfer, cluster-insertion]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-20
ran_start: 2026-05-20
ran_end: 2026-05-20
duration_runtime: "~12 min (greedy 49 starts 6.5 min + insertion LNS 3 min + diagnostics)"
code: src/esa_spoc_26/ch2_findtransfer_greedy.py + ch2_insert_lns.py
commit: 821354e
inputs: "edges_small.npz; windows2d_small.npz (v3, K=24, 18651 windows)"
outputs: solutions/upload/small.json
env: spoc26 (pykep 2.6 + ortools 9.15)
code_dependencies: [src/esa_spoc_26/ch2_kttsp.py, src/esa_spoc_26/ch2_findtransfer_greedy.py, src/esa_spoc_26/ch2_insert_lns.py]
compute: {cpu_seconds: 750, peak_memory_mb: 600, cores: 4}
effort_person_hours: 2.0
metrics:
  makespan_d: 145.80
  perm_c: 0
  dv_c: 0
  time_c: 0
  exc_c: -1   # 4 of 5 exceptions used (1 spare)
  feasible: true
  rank3_small_d: 111.76
  ratio_to_rank3: 1.305
  n_legs: 48
  n_cheap_legs: 44
  n_exception_legs: 4
verdict: confirmed
---

# E-022 — 🎉 Ch2 small BANKED at makespan 145.80 d

## Result

**First banked Ch2 solution.** Decision-vector + fitness:
```
makespan: 145.797 d   (≤ 200 d horizon ✓)
fitness: [145.80, 0, 0, 0, -1]
  perm_c = 0   all 49 tomatoes distinct ✓
  dv_c   = 0   every leg Δv ≤ 600 ✓
  time_c = 0   chronology OK ✓
  exc_c  = -1  4 of 5 exceptions used ✓
```

Saved at `solutions/upload/small.json`.

## The breakthrough — official `find_transfer` pattern

E-018→E-021 chained refutations established that discrete CP-SAT
over precomputed point-windows cannot solve the time-coupled problem.
On re-reading `SpOC4/Challenge 2/utils_users.py`, the official helper
`find_transfer(i, j, t_start, dv_thr, max_time=5.0, n_steps=1000)`
returns the **earliest tof at fixed t_start** where Δv ≤ thr — not
the global-min-Δv tof. This inverts the precompute target:
greedy on arrival-time using min-tof-feasible transfers.

## The algorithm

1. `find_earliest_transfer(i, j, t_start, dv_thr, tof_window, n_steps)`
   — scan tof at fine resolution; return first feasible (tof, Δv).
2. `greedy_findxfer(start)` — at each (cur, t), try cheap (Δv ≤ 100)
   for all unvisited j, pick min-arrival; if no cheap, try exception
   (Δv ≤ 600); if no exception, advance t and retry. Parallel across
   49 starts (mp.Pool n_workers=4).
3. **Best partial = 45 legs from start=34** in 159.4 d, missing the
   3-node small cluster {17, 11, 4} (the polar/equatorial/retrograde
   low-orbit tomatoes from O-007).
4. `ch2_insert_lns.insert_lns(partial, {4, 17, 11})` — enumerate all
   (46 positions × 6 orderings = 276) insertions of the missing-chain
   into the partial perm; chronologically NLP-walk each; keep feasible
   ones. **Best insertion: between positions 25 and 26 (after node 1,
   before node 29) with chain (4, 17, 11), using 2 exception bridges:**
   - `1 → 4` @ 576 m/s (1 exception)
   - `4 → 17` @ 91 m/s (cheap)
   - `17 → 11` @ 96 m/s (cheap)
   - `11 → 29` @ 568 m/s (1 exception)

## Final leg log (highlights)

| range | description | n_legs | makespan |
|---|---|---|---|
| 34 → 1 | big-cluster traversal (with 18→46 exception @ 565 m/s) | 25 | 82.8 d |
| 1 → 4 → 17 → 11 → 29 | small-cluster insertion (2 bridges + 2 internal cheap) | 4 | +5.2 d → 88.0 d |
| 29 → 32 | finish big cluster (with 33→27 exception @ 536 m/s) | 19 | +57.8 d → 145.8 d |

Total 4 exceptions out of 5 budget; 44 cheap legs.

## Position vs rank-3

Rank-3 = 111.76 d. We're at 145.80 d → ratio **1.305** (30 % over).
Expected leaderboard placement: roughly **rank 6–10** (~3–5 pts banked).
Plenty of room for improvement: 2-opt over the cluster-insertion
position, different partial perms (start ∈ {23, 16, 18} reached
43–44 legs), per-leg arrival-time refinement (current `find_earliest_transfer`
greedily picks the first feasible tof rather than the makespan-optimal).

## Final answer to the user's question

**The right Ch2 approach (E-018→E-022)** is concretely:
- **Greedy-on-arrival-time** with `find_earliest_transfer` (the official
  helper's pattern — min-tof not min-Δv per leg).
- **Cluster-aware insertion LNS** to handle the small-cluster
  unreachability detected post-hoc.
- This *replaces* discrete CP-SAT (E-018→E-021).

Heavy compute pays in **cluster-insertion-LNS variants** + **2-opt
polish** + **per-leg makespan-NLP** (improving 145.8 → toward 112).
Same pipeline scales to medium/large with the same cluster-bridge
treatment for each instance's small clusters.
