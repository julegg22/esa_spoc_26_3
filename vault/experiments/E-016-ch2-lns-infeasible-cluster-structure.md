---
id: E-016
type: experiment
status: done
tags: [ch2, lns, structure, framing]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~1800s LNS + component probe
code: src/esa_spoc_26/ch2_lns.py
commit: (committed with this E)
inputs: "small (N=49), edges_small.npz"
outputs: none feasible
env: spoc26
code_dependencies: [src/esa_spoc_26/ch2_lns.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 1800, peak_memory_mb: 600, cores: 1}
effort_person_hours: 0.6
metrics:
  lns_iters: 1947
  lns_best: {makespan_d: 218, n_exc: 7, n_bad: 36, feasible: false}
  le100_components: "4 → sizes [40,3,3,3], 0 isolated, out-deg med 2"
verdict: refutes
---

# E-016 — Joint LNS infeasible; ≤100 graph = 4 clusters (decisive)

## Result

Full-commitment joint order+timing LNS ran **1947 iters** (decode
speed adequate) but stayed infeasible — best had **36 legs > 600**.
Blind permutation search can't find the rare feasible orderings.

**Component probe (M-002 audit):** the ≤100 m/s graph of `small`
has **exactly 4 connected components — sizes [40, 3, 3, 3]**, zero
dead-ends, out-degree ~2 (stable up to thr=300; one component at
≤600).

## Verdict + analysis (M-002 reframe)

**verdict: refutes** flat metaheuristic/CP on the whole graph.
The structure is now explicit: a feasible tour is a **clustered
Hamiltonian path** — chain cheap (≤100) edges *within* each of the
4 near-co-orbital clusters, stitched by exactly **3 inter-cluster
bridges** (the only "exception" legs needed; 3 ≤ 5 budget ✓).

**Method (the right decomposition):**
1. clusters = connected components of the ≤100 graph;
2. **CP-SAT Hamiltonian path within each cluster** on its ≤100
   subgraph — now *small & sparse* (≤40 nodes), exactly where
   CP-SAT ([[concepts/C-009-constraint-programming-cp-sat]]) is
   exact & fast (vs E-015's intractable full-graph model);
3. order the 4 clusters + pick the 3 cheapest ≤600 bridges;
4. full-horizon per-leg re-timing → official-mirror validate.

First target = *any* feasible tour (first Ch2 points), then
minimise makespan toward rank-3 (≤111.76 d). Generalises to
medium/large (same structure, O-006). →
[[hypotheses/H-003-ch2-small-lambert-metaheuristic|H-003]] next build.
