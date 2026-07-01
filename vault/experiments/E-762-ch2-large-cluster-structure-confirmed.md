---
id: E-762
type: experiment
status: analyzed — comp0 sub-cluster structure CONFIRMED; decompose→solve→couple viable
date: 2026-07-02
level: L3                      # structure discovery (the ladder's L3 rung for large)
assumes: [STRUCT-cheap-windows, EVAL-lambert]
code: scripts/ch2_large_cluster_probe.py
commit: b0c366d
related: ["[[E-041-ch2-large-gap-decomposition]]", "[[assumptions]]", "[[rank1-method-structure-then-metaheuristic]]", "[[M-general-abstraction-ladder-audit]]"]
---
# E-762 — Ch2-large: comp0 has clean sub-cluster structure (the HRI hint, confirmed)

**Result (Louvain on comp0's cheap graph).** The 601-node cheap giant that walled
every prior method decomposes cleanly:
- **5 sub-clusters**, sizes **[168, 160, 159, 57, 57]**;
- **modularity 0.676** (strong community structure);
- **38,415 intra-cluster edges vs only 89 inter-cluster (coupling) edges**
  (intra-ratio 1.00).

The full instance is [601, 150, 150, 150] at the top level (E-041); comp0 itself
splits into these 5.

**Interpretation.** This is the **HRI "cluster substructures" hint, confirmed
empirically** — and the L3 structure lever for large. The giant is not a
monolith: it's ~5 dense clusters joined by ~89 bridges, so **decompose → solve
each cluster (57–168 nodes, each tractable, unlike the 601-giant) → couple via the
few bridge legs** is a viable path — the method that reaches rank-1 (424 vs bank
879). Flips `STRUCT-large-monolithic` (L3, was *suspect*) toward REFUTED.

**Caveat (the real work).** The clustering is on the *static* cheap-adjacency;
KTTSP is time-dependent, so the coupling requires the 89 bridge legs to be
traversable at aligned epochs across cluster boundaries. Structure is necessary,
not sufficient — the coupling/timing is where the difficulty (and the build) is.

**Next.** Build decompose→solve→couple: (1) per-cluster TD-TSP solver (reuse the
exact-DP+LNS, now tractable at ≤168 nodes), (2) a coupling layer that orders the
clusters + selects bridge legs with epoch alignment. → E-763.
