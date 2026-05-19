---
id: O-007
type: observation
status: confirmed
tags: [ch2, structure, framing]
source: "edges_small.npz (hi-accuracy precompute 2026-05-19) + scipy connected_components + ch2_kttsp.opar"
created: 2026-05-19
referenced_by: ["[[H-003-ch2-small-lambert-metaheuristic]]", "[[T-006-ch2-method-time-optimal-edges-plus-routing]]"]
supersedes:
superseded_by:
---

# O-007 — Ch2 small structure fully characterized

## Observation

**(Q1) Cheap-edge graph is robust, not under-resolved.** Hi-accuracy
edge precompute (fine `t_dep` over the full 200-d horizon × long
multi-rev TOF × 15 refine seeds × Nelder-Mead) returned **identical
counts to the 1.5-d global probe**: 138 ≤100 m/s edges, 837 in
(100,600], 0 dead-end nodes. → E-017's "under-resolved" hypothesis
is **refuted at ≤100**. Density grows slowly with threshold:

| thr | edges | components | sizes | med out-deg |
|---|---|---|---|---|
| 50 | 54 | 33 | [5,4,4,3,3,3,…] | 0 |
| 100 | 138 | **4** | **[40,3,3,3]** | 2 |
| 150 | 220 | 4 | [40,3,3,3] | 4 |
| 200 | 298 | 4 | [40,3,3,3] | 6 |
| 300 | 440 | 4 | [40,3,3,3] | 10 |
| 600 | 975 | 1 | [49] | 20 |

The 4-component structure is **stable up to ~300 m/s** — the
clusters are physically separated by a ~300–500 m/s Δv gap.

## Orbital identity of the clusters (Q5)

| cluster | size | a (m) | i (rad) | meaning |
|---|---|---|---|---|
| 0 | 40 | 1.498e7 (σ=2.3e4) | mixed [-0.03, 3.17] | "high" orbit |
| 1 | 3 | 3.747e6 | **1.558 ≈ π/2** | polar low orbit |
| 2 | 3 | 3.746e6 | **~0** | equatorial low orbit |
| 3 | 3 | 3.743e6 | **3.150 ≈ π** | retrograde low orbit |

The 3 small clusters are at the **same semi-major axis** (a≈3.74e6,
4× lower than the big cluster's 1.5e7) but at **different
inclinations** (0, π/2, π).

## Inter-cluster Δv (decisive)

| from | to | min Δv (m/s) | edges ≤600 |
|---|---|---|---|
| big (40) | any small | ~**512–513** | 24–38 per pair |
| small | small | **≥ 1580** | **0 — FORBIDDEN** |

The 3 small clusters are **mutually unreachable** within the 600
m/s exception cap. Bridging requires going via the big cluster.

## Why it matters — the right Hamiltonian structure

A feasible Ham-path visiting all 4 clusters with ≤5 exception
bridges *must* have small↔small separated by big-cluster blocks ⇒
the **big cluster is split into ≥2 contiguous sub-paths**, with
small clusters interleaved. Minimum cluster-transitions = **4**
(achievable: `s_a → B₁ → s_b → B₂ → s_c` with 2 smalls at the path
endpoints and the third "sandwiched"). 4 ≤ 5 budget ✓.

This **refutes the prior `ch2_cluster` design** (each cluster as one
contiguous block ⇒ 3 transitions, but those 3 must include
small↔small which is forbidden, hence its "no stitching" failure
across all enumerated orderings). The correct model is a **global
Hamiltonian path with a ≤5-exception budget** (CP-SAT
[[concepts/C-009-constraint-programming-cp-sat]] over the ≤600
graph), which naturally allows splitting the big cluster. E-015's
prior CP-SAT failure was *not* the model — it was the **14-day
re-timing window** instead of the full-horizon decoder
([[concepts/C-010-constrained-hamiltonian-time-dependent-routing]]).
Patched `ch2_cpsat` to use the verified `ch2_lns.decode` full-
horizon timing; re-run pending.
