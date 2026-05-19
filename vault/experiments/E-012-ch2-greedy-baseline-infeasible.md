---
id: E-012
type: experiment
status: done
tags: [ch2, lambert, baseline]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~1m
code: src/esa_spoc_26/ch2_kttsp.py
commit: (committed with this E)
inputs: "easy.kttsp (small, N=49)"
outputs: none (infeasible)
seed: "no-wait greedy nearest-Δv, tof grid 0.2–30 d, start=0"
env: spoc26 (pykep multi-rev Lambert)
code_dependencies: [src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 60, peak_memory_mb: 300, cores: 1}
effort_person_hours: 0.4
metrics:
  feasible: false
  failure: "greedy found no feasible next leg (all unvisited > 600 m/s at accumulated t)"
verdict: refutes
---

# E-012 — Ch2 no-wait greedy baseline is infeasible

## Result

Official-mirrored KTTSP scorer built and verified (loads, fitness,
multi-rev Lambert per O-005). The **no-wait greedy** (depart on
arrival; pick min-Δv next over a tof grid) **fails to complete a
tour** on `small` (N=49): at some point every unvisited tomato
needs Δv > 600 m/s for all grid TOFs.

## Verdict + analysis

**verdict: refutes** the naive no-wait greedy. Diagnosis: Ch2
feasibility (≤100 m/s normal, ≤5 exception legs ≤600, the rest
infeasible) is tight and **time-coupled** — Δv depends strongly on
*when* you depart. Depart-immediately discards the main lever
(**waiting** to a favourable phase) and a fixed start/order ignores
the routing structure. Next (H-003): precompute a
**time-resolved feasible-edge graph** (Lambert Δv over a (t, tof)
grid per pair) → route on the feasible graph with waiting allowed
(nearest-feasible + cheapest-insertion / LNS), multi-start over the
first tomato; bank `small` (rank-3 ≤ 111.76 d, O-002). Concept:
[[concepts/C-006-lambert-problem-and-orbital-tsp|C-006]].
