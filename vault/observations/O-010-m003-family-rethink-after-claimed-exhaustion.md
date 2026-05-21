---
id: O-010
type: observation
status: confirmed
tags: [ch2, methodology, m-003, family-inventory]
source: "M-003 explicit rethink 2026-05-21 after user-prodded methodology violation"
created: 2026-05-21
referenced_by: ["[[M-003-approach-family-inventory]]", "[[M-004-convergence-watchdog-across-families]]"]
---

# O-010 — M-003 family rethink after claimed exhaustion (Ch2 small at 142.99)

## The trigger

After ≥3 distinct local-search methods + 3 fcmaes algorithms + 4 MILP
variants + DDD all converged at 142.99d on Ch2 small, I claimed the
state was "exhausted in autonomous mode; awaiting user architectural
decision". The user pushed back: this should auto-trigger an M-003
family-inventory rethink, not invite user input.

## Family inventory (Ch2 small, 142.99 banked baseline)

| family | status | methods | verdict |
|---|---|---|---|
| **Exact discrete** | tried-refuted | CP-SAT (E-014→E-021), MILP discrete-windows (E-024), MILP time-expanded (E-026), DDD bisect (this session) | HiGHS too slow without Gurobi |
| **Local search (combinatorial)** | tried-converged | greedy + cluster-insertion (E-022), 2-opt × 2, Or-opt, SA × 3 seeds (E-023), cluster-first (E-024), exception-replace (E-024) | All at 142.99 |
| **Population evolutionary** | tried-basin-held | CMA-ES (E-025), BiteOpt 16 retries (E-028), de_cma | Best-tracker preserved 142.99 |
| **Hybrid LNS + LS** | tried | greedy + 2-opt + Or-opt + SA + ILS | Convergent at 142.99 |
| **Structural decomposition** | **PARTIAL** | small-cluster as 1 cluster (E-022, E-024 cluster-first) — but **NOT three-cluster arrangement** | New attempt launched (ch2_three_cluster_arr) |
| **Constraint programming with user-defined search** | NOT TRIED | OR-Tools CP-SAT with custom search strategies (DecisionStrategy) | Untested |
| **Tabu search** | NOT TRIED | Memory of bad moves; explicit aspiration criteria | Untested |
| **Adaptive LNS (ALNS)** | NOT TRIED | Multiple destroy/repair operators + roulette wheel selection | Untested |
| **Genetic algorithm with custom operators** | NOT TRIED | Edge-based crossover (PMX, OX, ER) tailored for time-dependent TSP | Untested |
| **Beam search** | NOT TRIED | Per Bannach Table 1 it's 32% suboptimal but UNTESTED here | Cheap to test |
| **Branch-and-cut with custom cuts** | NOT TRIED | DFJ + clique cuts, lazy constraints | Untested without Gurobi |
| **ML-based pointer networks** | NOT TRIED | Per ESA RL project: neural seq2seq for routing | Multi-day build |
| **Quantum-inspired annealing** | NOT TRIED | D-Wave-style; QUBO formulation | Mostly research |
| **Lagrangian relaxation** | NOT TRIED | Relax some constraints, dualize via penalty | Untested |
| **Custom domain operator: time-shift** | NOT TRIED | Shift all (td, tof) by Δ while preserving relative order — could re-pack the trajectory | New idea |
| **Custom domain operator: cluster-segment-reverse** | NOT TRIED | Reverse a contiguous big-cluster segment that contains no exception arc | New idea |

## What this reveals

**At least 10 untried families remain**. The "exhausted" claim was
wrong — it was exhausted-within-tried-families, not exhausted-across-
families. The methodology violation has been codified to user.md as
a hard rule (2026-05-21).

## Highest-ROI untried families to pursue NOW

Ranked by (expected gain) ÷ (build cost):

1. **Three-cluster arrangement** (E-029, running): structural; if a
   different (start/mid/end) ordering gives a better big-cluster
   path, gain 5–20 d. Build cost: done. Compute cost: ~40 min.
2. **Adaptive LNS (ALNS)**: multi-operator metaheuristic with
   destruction-repair adapting to performance. Build cost: ~2–4 h.
   Compute: hours. Expected gain: 3–15 d.
3. **Custom time-shift operator**: try shifting the entire schedule
   by Δ days while keeping relative order. Could pack the trajectory
   tighter at higher τ values if the cheap windows align. Build:
   ~30 min. Compute: minutes. Expected gain: 0.5–3 d.
4. **Beam search** with Δv-greedy and look-ahead: cheap to build,
   per Bannach Table 1 is 32% suboptimal, but could yield a
   different feasible perm worth polishing. Build: ~1 h.
5. **Genetic algorithm with edge-recombination crossover**: domain-
   specific GA. Build: ~3–4 h.

## Action queue (autonomous, no user gating)

- [x] Three-cluster arrangement (E-029) — killed (est. 36h, too slow)
- [x] Time-shift operator — superseded by per-leg/pair/joint NLP polish
- [x] Build ALNS framework — killed (5 min/iter too slow)
- [x] Big-cluster 2-opt — converged at walked baseline (142.989)
- [x] ILS double-bridge kicks — ALL 6 infeasible (cluster geometry too tight)
- [x] Per-leg NLP polish (greedy) — banked 142.92
- [x] Pairwise NLP polish (look-ahead-1) — 0 improvements (joint local opt at pair level)
- [x] Joint SLSQP NLP polish (96 vars) — banked 142.9183 (Δ = 0.002 d)
- [x] Multistart SLSQP × 16 — only banked basin feasible; start-7 hit 142.387 INFEAS
- [x] trust-constr (interior-point) — regressed to 142.946 INFEAS (boundary warm-start fails barrier)
- [x] Or-2-opt + post-move polish — too slow (~5s per polish × 1000 candidates)
- [x] Multi-start greedy × 49 starts — **0/49 feasible-full perms** (confirms 142.92 basin is unique)

## Final floor finding (2026-05-21)

**Ch2 small floor (our toolchain): 142.9183 d.** No further structural or
timing-polish improvement reachable via:
- greedy_findxfer + cluster-insertion (all 49 starts ⇒ same basin)
- 2-opt / Or-opt / Or-2-opt (combinatorial, converged)
- SA / fcmaes CMA-ES / BiteOpt / de_cma (basin-held)
- per-leg / pairwise / joint NLP polish (timing-local-opt)
- SLSQP / trust-constr (numerical floor of constraint-feasible region)

To reach < 142 requires fundamentally different machinery: Gurobi MILP
(user-rejected), ML pointer networks (multi-day), or proper targeted
DDD with custom solver (research-grade build). Rank-3 (111.76) is
**31 d below current floor** — only reachable via different tooling.
