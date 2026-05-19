---
id: E-017
type: experiment
status: done
tags: [ch2, dead-end, framing]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: ~few min
code: src/esa_spoc_26/ch2_cluster.py
commit: de920cf
inputs: "small, edges_small.npz"
outputs: none feasible
env: spoc26 + ortools
code_dependencies: [src/esa_spoc_26/ch2_cluster.py, src/esa_spoc_26/ch2_lns.py]
compute: {cpu_seconds: 200, peak_memory_mb: 600, cores: 8}
effort_person_hours: 0.5
metrics:
  clusters: "[40,3,3,3] (≤100 graph)"
  result: "no ≤600 stitching within ≤5-exception budget"
  ch2_methods_tried: 6
verdict: refutes
---

# E-017 — Cluster-decomposition infeasible; root cause identified

## Result

CP-SAT found per-cluster paths but no cluster ordering stitches the
4 clusters with ≤5 exception bridges. **Sixth** distinct Ch2 method
infeasible (greedy, greedy-wait, structure-router, static CP-SAT,
joint-LNS, cluster-decomp).

## Verdict + analysis (M-002 root cause)

**verdict: refutes** all methods *built on `edges_small.npz`*. The
consistent failure cause is now clear: the **cheap-edge graph is
under-resolved**. `edges_small.npz` used a 1.5-d global `t_dep`
scan, TOF ≤ ~30 d, 6 refine seeds — but:

- the README **allows arbitrary waiting** at any tomato (free in
  Δv, only time; 200-d budget);
- the scorer uses **multi-revolution Lambert** (`max_revs=20`):
  long-TOF multi-rev arcs at the right phase are very cheap.

So the true ≤100 graph is **denser** than the 138 edges we found;
the 40-node cluster likely *is* Ham-traceable on truly-cheap edges
once timing/phasing is computed accurately. This is the designed
"analytical-capacity hurdle": **accurate time-optimal per-edge Δv
(fine `t_dep` phasing × long multi-rev TOF × strong local opt over
the full 200-d horizon) is THE lever** — every routing method is
only as good as its edge graph.

Concrete next: a high-accuracy parallel edge precompute (fine
`t_dep` over [0,200], TOF to ~100+ d incl. multi-rev, robust local
optimisation) → re-probe density → cluster/CP solver. Heavy compute,
uncertain. Escalating ROI vs the solid ~11-pt floor + methodology
deliverable.
