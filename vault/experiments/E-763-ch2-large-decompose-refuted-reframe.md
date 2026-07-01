---
id: E-763
type: experiment
status: analyzed — undirected-cluster decomposition REFUTED; large reframed toward L4 (shared with small/medium)
date: 2026-07-02
level: L3
wall_level: L3                # the specific undirected-cluster decomposition fails; see reframe
assumes: [EVAL-lambert, MODEL-official-feas]
reruns: [STRUCT-large-monolithic]
code: scripts/ch2_large_cluster_solve.py
commit: 4948dee
related: ["[[E-762-ch2-large-cluster-structure-confirmed]]", "[[E-761-ch2-medium-exact-dp-lns-L4-wall]]", "[[E-735-ch2-large-idle]]", "[[assumptions]]"]
---
# E-763 — Ch2-large: undirected-cluster decomposition doesn't yield solvable sub-tours

**What was tried.** decompose→solve→couple: solve each comp0 sub-cluster (E-762
Louvain: [168,160,159,57,57]) as a cheap intra-cluster TD-tour, then couple.
Sub-solver `ch2_large_cluster_solve.py` (exact earliest-cheap-arrival retimer +
greedy/LNS) on the dense1d window source (74208 edges, tof-per-epoch, validated).

**Result (negative, decisive).** On c3 (57 nodes): only **572/3192 directed
intra-edges (18%) are cheap** in the faithful windows, and a **constructive greedy
threads 0/57 starts** → the cluster is **NOT cheap-directed-Hamiltonian**. Both
window sources (dense1d, faithful_full) agree at ~18%.

**Why (the insight).** The clustering (E-762) was **undirected** modularity; a
KTTSP tour needs a **directed, time-feasible** path. comp0's good cheap paths (the
beam threads 558–575/601) **weave *across* the clusters**, so undirected-community
cuts sever exactly the edges the good directed paths use. **Decompose-along-
undirected-communities is the wrong decomposition for a directed-path problem.**
`STRUCT-large-monolithic` REFUTING (E-762) is walked back: the *sub-structure*
exists undirected, but it is **not a solvable decomposition** as built.

**Reframe (the likely real lever).** Large's gap is 879.528→424.62 (rank-1). E-735
showed the large giant is only ~3% idle → makespan is **flight-time (long-tof)
dominated**, exactly like the small/medium **L4 encoding** wall (representation
can't reach the short-tof cheap tours rank-1 uses). Working hypothesis: **all
three Ch2 instances share ONE wall — L4 encoding** — and the large "cluster" detour
was chasing the undirected structure rather than the tof representation. Next: a
ladder sweep on large's 879→424 gap — measure per-leg tof inflation of the large
bank (E-652 analog); if the bank's legs are long-tof vs available short-tof
windows → L4 confirmed shared; the fix is the L4 rebuild for the whole family, not
decomposition.

**L4 reframe REFUTED too (self-correction via measurement).** The tof-inflation
probe on the large bank: median leg tof 0.421 d, and **only 33/588 legs** have a
cheaper short-tof window near the banked epoch (median excess 0.031 d). So the
bank already uses near-minimal tofs — large is **NOT** the small/medium L4
wall. The 879 vs 424 gap is the **long-leg tail** (mean tof 0.81 ≫ median 0.42,
p90 1.94) → a **sequencing (L3) problem**: a better *order* avoids the long legs.
`wall_level: L3` — the original hard large problem (threading/sequencing walls
7+ methods; beam threads 558–575/601), now with the decomposition detour AND the
L4 hypothesis both ruled out. rank-1 424 needs either a **directed/time-aware
decomposition** (cluster by directed cheap-reachability, not undirected
modularity) or a **fundamentally better global sequencer** — genuine research.

**Bank impact.** None. Method/plumbing validated (dense1d source, sub-solver,
greedy) even though both the decomposition and L4 targets were refuted.

