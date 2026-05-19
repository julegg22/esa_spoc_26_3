---
id: O-006
type: observation
status: confirmed
tags: [ch2, structure]
source: "structure_quick coarse/sampled probe (src/esa_spoc_26/ch2_kttsp.py) 2026-05-19"
created: 2026-05-19
referenced_by: ["[[H-003-ch2-small-lambert-metaheuristic]]", "[[T-006-ch2-method-time-optimal-edges-plus-routing]]"]
supersedes:
superseded_by:
---

# O-006 — Ch2 medium & large share small's structure

## Observation

Coarse/sampled cheap-edge probe (60-node sample for medium/large):

| inst | N | frac ≤100 | frac ≤600 | med Δv | dead-end ≤100 | med out-deg ≤100 |
|---|---|---|---|---|---|---|
| small | 49 | 0.038 | — | 720 | 0 (full) | ~2 |
| medium | 181 | 0.101 | 0.260 | 1067 | 0.133* | 6 |
| large | 1051 | 0.141 | 0.260 | 1244 | 0.033* | 8 |

(*coarse-grid dead-end fraction; true value lower — small went
9→3→0 as the search refined coarse→local→full-horizon, E-013.)

## Why it matters

All three Ch2 instances are the **same problem class**: sparse
cheap-edge graph (~4–14 % ≤100 m/s), expensive median (~0.7–1.2
km/s), a ≤5-exception constrained-Hamiltonian-path with strong
time-coupling. Larger instances have *more* cheap neighbours per
node (more tomatoes ⇒ denser near-co-orbital families), not fewer —
so they are not structurally harder per-edge, only larger to route.

**Implication:** the joint order+timing solver built for `small`
([[hypotheses/H-003-ch2-small-lambert-metaheuristic|H-003]],
ch2_lns) generalises directly to `medium`/`large` — same
official-mirror scorer and machinery, just rerun with each
instance's edge precompute. Justifies full commitment to `small`
first (user directive 2026-05-19); scoring ×1 / ×4/3 / ×(4/3)².
