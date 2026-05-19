---
id: E-018
type: experiment
status: done
tags: [ch2, cpsat, time-coupling, framing]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
ran_start: 2026-05-19
ran_end: 2026-05-19
duration_runtime: "<5 min"
code: src/esa_spoc_26/ch2_cpsat.py (patched with L.decode)
commit: (committed with this E)
inputs: "small, hi-accuracy edges_small.npz"
outputs: none feasible
env: spoc26 + ortools
code_dependencies: [src/esa_spoc_26/ch2_cpsat.py, src/esa_spoc_26/ch2_lns.py, src/esa_spoc_26/ch2_kttsp.py]
compute: {cpu_seconds: 180, peak_memory_mb: 700, cores: 8}
effort_person_hours: 0.5
metrics:
  cpsat_status: OPTIMAL (status 4)
  static_exc: 5 (= budget)
  retimed_bad_legs: 42_of_48
  retimed_exc_used: 1
  makespan_after_decode: 220.5_d
verdict: refutes
---

# E-018 — CP-SAT optimal + FULL-horizon decode: still infeasible

## Result

CP-SAT (≤600 graph, ≤5-exception constraint, min Σ-TF) found an
**optimal** static path on the hi-accuracy `edges_small.npz`.
Replacing E-015's 14-d retiming with the **full-horizon decoder**
`ch2_lns.decode` (search [t_ready, max_time] per leg) still
yielded **42 of 48 legs > 600 m/s** after chronological chaining.

## Verdict + analysis — the time-ordering crux

**verdict: refutes** the assumption "full-horizon timing always
finds a cheap window if one exists somewhere." It doesn't: each
edge's cheap window is at a *specific* absolute epoch in [0, 200];
the CP-SAT static-optimum chose edges whose cheap windows are
**scattered across the horizon in an order incompatible with
chronological chaining**. By the time `t_ready` passes an edge's
cheap window, that window is **gone** — and recurrences may be
absent in [t_ready, 200] for that specific pair.

The genuine model required: **time-windowed CP-SAT / scheduling
on a DAG** — pre-extract the cheap (`t_dep`, tof) *windows* per
ordered pair from the precompute and enforce chronological
window-selection in the model. Or: a path-search on a
*time-expanded* DAG where nodes = (tomato, time-bucket) and arcs
encode feasibility + chronology natively. Either is a substantial
build; structurally well-posed
([[concepts/C-010-constrained-hamiltonian-time-dependent-routing]]).

## Position vs the 6h research program

This isolates THE core difficulty: not edge cost computation
(O-007: ≤100 graph is correct + stable), not cluster decomposition
(O-007), not CP-SAT search (E-018: it solves the static model
optimally). It is the **time-coupling**: edges' cheap windows are
scattered in absolute time and must be visited in time-order
chronology — the order-of-windows problem. *That* is where heavy
compute pays.
