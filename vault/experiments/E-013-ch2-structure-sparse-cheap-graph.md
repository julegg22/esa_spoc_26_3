---
id: E-013
type: experiment
status: done
tags: [ch2, lambert, structure]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~2× probe (coarse + refined)
code: src/esa_spoc_26/ch2_kttsp.py (analyze_structure)
commit: (committed with this E)
inputs: "easy.kttsp (small, N=49); pairwise min-Δv over (t_dep,tof,rev)"
outputs: structural statistics
seed: "coarse grid; refined = grid seed + Nelder-Mead per pair"
env: spoc26
code_dependencies: [src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 180, peak_memory_mb: 350, cores: 1}
effort_person_hours: 0.6
metrics:
  pairs: 2352
  edges_le100_coarse: 74
  edges_le100_refined: 89
  edges_100_600_refined: 846
  median_min_dv_m_s: 720
  median_outdeg_le100: 2
  dead_end_nodes_le100: 3
verdict: inconclusive
---

# E-013 — Ch2 is a sparse, time-coupled constrained-Hamiltonian-path

## Result (M-002 ultrathink probe)

Pairwise true-ish min-Δv (grid + per-pair Nelder-Mead): only
**89 / 2352** ordered pairs ≤ 100 m/s (3.8 %), median 720 m/s,
median ≤100 out-degree **2**, 3 nodes with no ≤100 out-edge.
Refinement over coarse grid recovered +15 cheap edges and cut
dead-ends 9→3 — and is still a *lower bound on cheapness* (the
grid seed only spans [0,20] d of the 200-d horizon).

## Verdict + analysis

**verdict: inconclusive** for H-003's metaheuristic framing, but
structurally **decisive**: Ch2 is **not** a metric TSP. Feasibility
needs ≥ 43 of 48 legs ≤ 100 m/s + ≤ 5 exception legs (≤ 600). The
≤100 graph is sparse and clustered ⇒ it is a **constrained
Hamiltonian-path** problem on a sparse cheap-edge graph, with ≤ 5
"exception" bridges between clusters. Naive/greedy constructors
strand themselves (E-012) by ignoring connectivity.

**The binding hurdle (M-002):** the true edge cost is
`min over t_dep∈[0,200 d], tof, rev` of the Lambert Δv — cheap
windows are *narrow and recurring* with the ~0.2–1.9 d orbital
periods. A coarse/local search under-counts cheap edges and makes
the instance look infeasible when it is not (rank-3 = 111.76 d ⇒
good feasible tours exist). Method →
[[takeaways/T-006-ch2-method-time-optimal-edges-plus-routing|T-006]].
