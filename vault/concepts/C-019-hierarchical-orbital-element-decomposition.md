---
id: C-019
type: concept
status: tentative
tags: [optimization, ch2, scale, clustering, orbital-mechanics]
scope: optimization/decomposition + orbital-mechanics
confidence: medium
created: 2026-05-22
sources:
  - "[[E-030-ch2-large-hierarchical-decomp]]"
  - "[[O-010-m003-family-rethink-after-claimed-exhaustion]]"
  - "M-003 (orthogonal-family inventory)"
related: ["[[C-006-lambert-problem-and-orbital-tsp]]", "[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-017-subtour-bridge-insertion-large-clusters]]"]
---

# C-019 — Hierarchical orbital-element decomposition for large-n TSP

*Primer: collapse a 1000+ node orbital TSP into a ~50-node meta-TSP
by clustering on orbital elements; solve meta-route with existing
tools; expand each supernode into its intra-cluster sub-tour.*

## Why a new concept

Greedy + cluster-bridge insertion (C-017) scales to n ~ 200. For
n=1051 (Ch2 large) it does not — the single-greedy alone took 1.6 h
for 14% coverage. The structure exploitable: 1051 orbits NATURALLY
cluster into orbit families (per O-007). Decompose hierarchically.

## The decomposition

1. **Cluster nodes by orbital elements.** For each node i, extract
   the Keplerian tuple `(a, e, i_inc, RAAN, ω, M)` via
   `kt.tom[i].orbital_elements`. Skip M (mean anomaly = phase, not
   family identity). Build the 5-D feature vector:
   ```
   x_i = [a, e, sin(i_inc) cos(RAAN), sin(i_inc) sin(RAAN), cos(ω)]
   ```
   (Trig wrap of i_inc/RAAN avoids the (0, 2π) discontinuity.)
2. **K-means** (k ≈ √n typical). For n=1051, k=50 gives ~21 nodes
   per cluster average.
3. **Intra-cluster sub-tour**: greedy through cluster nodes only.
   Cluster members are co-orbital → cheap internal arcs typically
   exist. Scan multiple `t_start` values (phase rotates with
   orbital period; some t_start values give better cluster Lambert
   geometry).
4. **Meta-route**: treat each cluster's sub-tour as a "supernode"
   with entry-node and exit-node. Apply C-013/C-017 at the meta
   level (k_meta ≈ 50, tractable).
5. **Expand & stitch**: concatenate sub-tours via the meta-route.

## Why orbital elements work

Two co-orbital satellites (same a, e, i, RAAN, ω) have transfers
with Δv that depends only on phase difference (true anomaly). For
nearly-co-orbital pairs, Lambert transfers are cheap for most
(td, tof) values — the kind of arcs greedy_findxfer naturally
picks. Inclination + RAAN difference is the main "expensive" axis
(it's where exception arcs go).

Skipping mean anomaly M from clustering is critical: M varies with
time, so two satellites with similar (a, e, i, Ω, ω) but 180°
phase difference at t=0 are 180° apart in true anomaly and need
either long-tof transfers or to be visited at different times.
Clustering on M would split true orbit families artificially.

## When the decomposition wins

- **n ≥ 500**: greedy O(n²) scans become slow; sub-clustering
  reduces to k × O((n/k)²) = O(n²/k), an n/k × speedup.
- **Strong cluster structure**: the orbits actually DO cluster
  (low silhouette score = bad fit, high = good).
- **Cheap intra-cluster, expensive inter-cluster**: matches Δv-threshold
  problems (Ch2 family).

## Caveats

- **Sub-tour failure**: at t=0 some clusters may not admit a
  feasible cheap sub-tour due to phase mismatch. Mitigate by
  scanning multiple `t_start` values and allowing ≤ 1 internal
  exception per cluster.
- **Bridge feasibility**: meta-route between supernodes consumes
  excs in the FULL budget. Plan for k_meta − 1 bridges; if most
  must be cheap, exception budget bounds k_meta.
- **Cluster boundary node choice**: a sub-tour has 2 endpoints
  (entry, exit). Different endpoints give different feasibility
  against the next cluster. Optionally search over (entry, exit)
  pairs per supernode.

## In practice

`src/esa_spoc_26/ch2_hierarchical_large.py` implements this for
Ch2 large. v1 (no phase scan): 11/50 clusters fully covered, 150
nodes total at t=112d. v2 (8 start times × 4 start nodes per
cluster + max_exc=1 internal): launched E-030, result pending.

## References

- E-030 (Ch2 large hierarchical attempt).
- O-007 (cluster structure on Ch2 small).
- C-013, C-017 (the meta-route primitives).
- C-009 (CP-SAT could be applied to the meta-TSP if greedy
  fails at k ≈ 50).
