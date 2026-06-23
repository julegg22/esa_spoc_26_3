---
id: T-008
type: takeaway
status: confirmed
tags: [ch2, framing, decision-rationale, methodology]
hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"
created: 2026-05-19
updated: 2026-05-20
supports_verdict: critical-reframe
confidence: high
generalizability: subgoal-wide
goal_contribution: "Identifies the right Ch2 approach as continuous-time per-leg + permutation metaheuristic, *not* discrete CP-SAT — banked from the 6-hour autonomous research window."
effort_person_hours: 9
superseded_by:
invalidated_by:
invalidated_at:
---

# T-008 — Ch2: the right approach (after the 6h research window)

*Finalised from the autonomous compute window 2026-05-19–20. The
final answer is structurally different from the draft version: heavy
compute should NOT go into more elaborate discrete CP-SAT models. It
should go into a continuous-time per-leg optimisation engine + a
permutation metaheuristic.*

## What 9 person-hours of research established

After 9+ method iterations and 7 instrumented experiments
(E-014 → E-021), the binding constraint on Ch2 is now precisely
isolated:

1. ✓ **Graph topology is fine** — static Ham-path with ≤5 exceptions
   exists (CP-SAT diagnostic OPTIMAL). 4-cluster structure
   ([[O-007-ch2-small-structure-characterized]]), no dead-ends at ≤600.
2. ✓ **Edge cost precompute is saturated** — E-019: 16× more compute
   yields ZERO new cheap edges. The 138 ≤100 + 837 (100,600] arcs
   are essentially complete.
3. ✓ **Sum-of-min-tofs Ham-path = 73 d** (CP-SAT diagnostic) — well
   under the 200 d horizon → the *physical* problem permits a tour
   in time.
4. ✗ **Chronologically-consistent discrete-window CP-SAT INFEASIBLE**
   on small with 200 d horizon at multiple sampling densities:
   - E-018: single-window (one td, one tof per pair) → INFEASIBLE
   - E-020: multi-td single-tof, K=8 (6 634 windows) → INFEASIBLE
   - E-021: joint (td, tof) K=12 (9 431 windows) → INFEASIBLE
5. ✓ **Leaderboard rank-3 = 112 d** ⇒ feasible solutions exist; they
   are found by methods that handle (td, tof) **continuously**, not
   discretely.

## The right approach (replaces draft conclusion)

**Continuous-time per-leg optimisation + permutation metaheuristic.**

| layer | responsibility | technology |
|---|---|---|
| permutation | which order to visit tomatoes | LNS / 2-opt / Or-opt / ruin-recreate over Π |
| per-leg | optimal (td, tof, Δv) given chronological predecessor | NLP: `scipy.minimize(Δv | t_dep ≥ T_prev, tof ∈ [tof_min, max_time-t_dep])` |
| feasibility | ≤5 exceptions, ΣTOF ≤ 200 | hard constraints in permutation acceptance |

This **inverts** the original `H-003` model (precompute static edges,
metaheuristic over permutations with table-lookup costs):
the table lookup mistakes the continuous (td, tof) plane for a
finite cost matrix.

## Where heavy compute pays — final ranking

| target | marginal value | rationale |
|---|---|---|
| **Continuous-time per-leg NLP framework** | **HIGHEST** | The binding constraint (E-018→E-021); matches what rank-3 competitors must use. Build effort ~1–2 days. |
| **Permutation LNS over the continuous-cost path** | **HIGH** | Standard TSP metaheuristic mounted on the continuous engine. C-011 + C-010. ~0.5 day build. |
| Denser discrete windows (v3, K=24, finer grid) | **LOW** | Tested as fallback (E-021): even 4× more windows likely still INFEASIBLE because the issue is point-wise constraints, not coverage. |
| PWL approximation of Δv(td, tof) per arc | MEDIUM | Linearise the cost surface; usable in CP-SAT/MIP but adds Δv-error. ~1 day build. |
| Time-expanded DAG | MEDIUM | Per (tomato, time-bucket) node + shortest-Ham-path; cleanest discrete formulation but huge state space. |
| Edge-search resolution | **ZERO** | E-019: flat. |

## Why discrete CP-SAT cannot work here (the binding-finding)

CP-SAT requires finite-domain variables. Per arc, we pre-list K
windows `(td_k, tof_k, Δv_k)` and enforce `T_j = td_k + tof_k`
*exactly* when window k chosen. This **forces T_j to one of K
specific values**. With 48 sequential arcs, the chain of forced T's
must align — each window's td_k must equal some predecessor's
td_k'+tof_k' (or be ≥, with waiting). With K=12–24 grid points
across [0, 200] d, the probability of a chronologically-aligned
chain across 48 arcs is structurally low — and CP-SAT proves it
infeasible.

The continuous (td, tof) formulation has **infinite resolution**:
once a permutation is fixed, for each leg we solve a small NLP
finding the (td*, tof*) that minimises Δv subject to chronology.
This is what rank-3 competitors must be doing.

## Position vs goal (per `GOALS.md §3`)

- **Banked**: ~11 pts (Ch1 matching-i/ii locked).
- **Methodology deliverable**: very strong — 11+ concept nodes,
  M-001/M-002 codified, 9 experiments + 8 observations + 8 takeaways
  with full data trail and *productive* reframes (the M-002
  ultrathink turns at E-014, E-018, E-021 each re-aimed the work).
- **Ch2 endgame**: needs the continuous-time engine. Reuses the
  hi-accuracy edge precompute as a seed/upper-bound; reuses CP-SAT
  diagnostic for connectivity. Estimated 2–3 days to a banked
  feasible Ch2 small at rank-10–rank-3 range.

## What this means for the user's investment decision

The 6-hour window's value: the **right reframe is now banked as a
direction**. The naive "precompute edges + CP-SAT" path is closed
(7 explicit experiments). The continuous-time path is opened with
specific build steps. Without this research, a default investment
would have continued chasing denser-and-denser discrete grids; the
finding cuts that branch and points to the principled successor.
