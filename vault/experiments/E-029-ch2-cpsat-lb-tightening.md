---
id: E-029
type: experiment
status: done             # draft | running | done | invalidated
tags: [ch2, small, lb, cpsat, ortools, time-coupling, ceiling-proof, pre-registration]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-02
ran_start: 2026-06-02
ran_end: 2026-06-02
duration_runtime: "2h 00min (hit wall cap; solver did not prove optimality)"

# reproducibility
code: scripts/ch2_e518_cpsat_lb_tight.py
commit: 4dcd1ec (pre-launch)
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp (n=49, n_exc=5)
  /tmp/ch2_small_tcoupled_fine.npz (fine min-tof table, 400 t × 100 tof quanta)
outputs: |
  runs/ch2/e518_cpsat_lb.log         (wall log incl. CP-SAT search progress)
  /tmp/ch2_e518_result.json          (final LB + status + wall + solution if found)
plots: []
seed: deterministic (CP-SAT default)
env: micromamba spoc26, python 3.13.13

code_dependencies:
  - src/esa_spoc_26/ch2_kttsp.py
  - scripts/ch2_e501_cpsat_lb.py     # frame to extend
  - /tmp/ch2_small_tcoupled_fine.npz # built by ch2_precompute_fine.py

compute:
  cpu_seconds:
  peak_memory_mb:
  cores: 8
  wall_budget_h: 2

effort_person_hours:

metrics:
  cpsat_status: FEASIBLE              # not OPTIMAL — hit wall cap
  lb_d: 66.5                          # BestObjectiveBound × 0.5 d
  cpsat_best_feasible_d: 148.0        # solver's heuristic-found tour, 5 exc
  cpsat_perm_lambert_S1_mk_d: 169.861  # real Lambert validation of CP-SAT perm under wait_dt=1.0
  cpsat_perm_lambert_S2_mk_d: 155.600  # ditto under wait_dt=0.2
  cpsat_perm_lambert_exc_legs: 4      # both substrates, real Lambert
  cpsat_perm_udp_feasible: true       # both substrates
  bank_d: 142.8913                    # for reference, unchanged
  R3_d: 111.76
  relaxation_gap_lb_to_bank_d: 76.39  # = 142.89 − 66.5
  relaxation_underestimate_d: 7.6     # cpsat_best_feasible (148) vs S2-Lambert (155.6)
  wall_s: 7200
  cores: 8
  conflicts: 34186
  booleans: 53321
  branches: 113878
verdict: refutes                      # per pre-reg rule (LB ≤ R3); see analysis

invalidation:
  invalidated_by:
  superseded_by:
  invalidated_at:
  notes:
---

# E-029 — Ch2 small: CP-SAT LB tightening with fine min-tof table

## Why this experiment exists

After E-516 (24 h GA, 0 improvement) and E-028 (component-aware bridge
enum, refuted — bank's 4-inter-comp structure is hard-required), the
remaining decisive question for Ch2 small is **information-theoretic,
not search**: is the bank makespan of 142.8913 d at or near the
architecture ceiling, or is R3 = 111.76 d reachable in principle and
we're just failing to find a perm?

E-501 (2026-05-30) attempted this: reported a relaxed LB of 74.33 d
via CP-SAT on the coarse min-tof matrix (`/tmp/ch2_small_mtc.npy`).
That bound is too loose to distinguish "ceiling proven" from
"headroom exists". E-029 tightens the LB by using:

1. The **fine** min-tof table (`/tmp/ch2_small_tcoupled_fine.npz`),
   400 t-quanta × 100 tof-quanta — finer than E-501's coarse table.
2. Time-coupled costs via `AddElement`: each edge (i,j) used at
   t_node[i] consumes a tof = `fine_cheap[i, j, t_bucket(t_node[i])]`
   rather than the t-min over all t.
3. The 5-exception budget retained.
4. 2 h wall budget (vs E-501's 10 min) for CP-SAT's bound-and-cut to
   improve the LB.

## Hypothesis (pre-registered, 3-sentence guardrail)

1. **Decomposition row addressed**: the audit's open question — does
   the gap (bank 142.89 vs R3 111.76 = −31.16 d) reflect an
   architecture ceiling or a search/structural failure?
2. **Empirical signature**: CP-SAT will return one of three outcomes
   after wall cap: (a) **LB ≥ 142.89 d** → ceiling proven, R3
   unreachable in the impulsive architecture with this exception
   budget; (b) **LB ≤ 111.76 d** → R3 reachable in principle, gap is
   a search problem (justifies further heavy-compute); (c)
   **111.76 ≤ LB ≤ 142.89** → ambiguous, but the gap size between LB
   and bank quantifies achievable headroom.
3. **Predicted magnitude**: based on E-501's 74 d relaxed LB and
   bank's per-leg LB of 84.82 d from the audit, a realistic tightened
   LB is in the **80–110 d** range. This would place us in outcome
   (b) or (c). A jump to 142+ would be surprising (would imply
   chronological coupling adds 30+ d of true unrecoverable structural
   slack).

## Setup

**Model variables**
- `x[i,j] ∈ {0,1}` — directed Hamiltonian-path edge (CP-SAT AddCircuit
  with dummy depot node n)
- `use_exc[i,j] ∈ {0,1}` — edge consumes one exception slot
- `t_node[i] ∈ [0, Q_MAX]` — departure time from node i, integer 0.5 d
  quanta (Q_MAX = 400 = max_time / 0.5)
- `makespan ∈ [0, Q_MAX]` — max over all t_node[i]

**Constraints**
- `AddCircuit` over arcs (covers Hamiltonian-path-with-dummy-depot)
- `sum(use_exc) ≤ kt.n_exc` (= 5)
- For each (i, j) with `x[i,j] = 1`:
  - if cheap is feasible at t-bucket: `t_node[j] >= t_node[i] +
    fine_cheap[i, j, t_bucket(t_node[i])]` (Element constraint)
  - if exception is used: `t_node[j] >= t_node[i] +
    fine_exc[i, j, t_bucket(t_node[i])]`

**Tightening over E-501**
- E-501: uses `min over t` of edge cost (loose).
- E-029: uses `cost(t_bucket(t_node[i]))` via Element → tighter but
  more variables.

**Objective**
- `minimize makespan`

**Solver**
- OR-Tools CP-SAT, `num_search_workers=8`, `log_search_progress=True`,
  `max_time_in_seconds=7200`.
- LB tracked via `solver.BestObjectiveBound()` throughout.

## Success criteria

- [ ] CP-SAT builds model without OOM (estimate: ~49² × 400 = ~960 k
      element-table cells per direction; should fit).
- [ ] Solver runs for ≥1 h before timeout or returns OPTIMAL/INFEASIBLE.
- [ ] Final `BestObjectiveBound` reported.
- [ ] Verdict-mapping:
      - LB ≥ 142.89 → **verdict: supports** "ceiling at bank";
      - LB ≤ 111.76 → **verdict: refutes** "ceiling at bank" (R3
        reachable in relaxation);
      - 111.76 < LB < 142.89 → **verdict: inconclusive**, quantifies
        achievable headroom.

## Pre-registered failure modes

- **F1** — Model too large to build (memory). Mitigation: drop tof-quanta
  resolution to 200 t-buckets instead of 400.
- **F2** — Solver returns INFEASIBLE before exploring (over-constrained
  Element interaction with AddCircuit). Mitigation: fall back to
  E-501-style without Element constraint (use min-over-t edge cost from
  fine table); produces a looser-but-valid LB.
- **F3** — Solver runs full 2h without improving LB beyond E-501's 74 d.
  Reading: CP-SAT relaxation is inherently too loose for this problem;
  next pivot is a stronger LP relaxation (Held-Karp 1-tree) or accepting
  bank as ceiling without proof.

## Procedure (actual)

1. Built fine cost tables from `/tmp/ch2_small_tcoupled_fine.npz` at
   0.5 d quanta (Q_MAX = 400 buckets, 200 d horizon). Tables built in
   0.1 s.
2. Constructed CP-SAT model: 2 042 boolean edge/exception vars, 50
   integer t_node vars, 1 944 Element constraints (one per
   directed-reachable pair × {cheap, exc}), 1 AddCircuit with dummy
   depot, exception-budget sum constraint ≤ 5. Build wall: 0.3 s.
3. Solved with `num_search_workers=8`, `max_time_in_seconds=7200`,
   `log_search_progress=True`. Solver hit wall cap (not OPTIMAL).
4. Post-hoc: validated CP-SAT's best feasible perm via
   `walk_perm_chrono` under both substrates (S1: wait_dt=1.0; S2:
   wait_dt=0.2) → both Lambert-feasible, UDP-feasible.

## Results

| Metric | Value | Reference |
|---|---|---|
| Status | **FEASIBLE** (timeout) | — |
| BestObjectiveBound (LB) | **66.5 d** | objective_bound × 0.5 d |
| CP-SAT best feasible (relaxed) | **148.0 d** | with 5 exc |
| Real Lambert mk @ S1 wait_dt=1.0 | **169.86 d** | 4 exc legs, UDP-feasible |
| Real Lambert mk @ S2 wait_dt=0.2 | **155.60 d** | 4 exc legs, UDP-feasible |
| Bank (unchanged) | 142.8913 d | reference |
| R3 (leaderboard cut-off) | 111.76 d | reference |
| Relaxation gap LB → bank | **−76.4 d** | bank − LB |
| Relaxation underestimate | **−7.6 d** | real-S2 (155.6) − relaxed (148.0) |
| Wall | 7 200 s | hit cap, 8 cores |
| Conflicts | 34 186 | CP-SAT search depth proxy |

## Verdict + analysis (2–5 lines)

**verdict:** refutes (per pre-registered rule LB ≤ R3 → "R3 reachable
in relaxation"); but see honest reading below.

**Honest reading.** The pre-registered rule maps LB = 66.5 d ≤ R3 =
111.76 d to "refutes ceiling at bank". Technically correct, but the
rule's intent — "we now know the gap is a search problem" — is **not
established**: the LB is too loose (76.4 d below bank) to actually
prove the gap is search-bound. This is failure mode **F3** from the
pre-registration ("CP-SAT relaxation inherently too loose to be
decisive"). The CP-SAT formulation here (per-bucket min-tof via
Element, no Held-Karp 1-tree cuts) gives a weak LP relaxation in this
domain; 2 h of bound-and-cut moved the LB from CP-SAT's initial
trivial value to 66.5 d but no further.

A real signal: CP-SAT's heuristic found a Lambert-real tour at
**155.6 d** (S2) that uses only **4 exceptions**, vs bank's 5 exc at
142.89 d. Lower exc count + worse mk reinforces E-028's finding:
within this architecture, the 5-exc structure of bank is at or near
locally optimal — fewer-exc tours exist but are longer.

## What this rules out / leaves open

- **CP-SAT with per-bucket Element cost is not the LB-tightening
  mechanism.** F3 confirmed; relaxation is too loose. Stronger LB
  needs Held-Karp 1-tree, Lagrangean relaxation of subtour
  constraints, or a different formulation entirely.
- **Bank-as-ceiling remains unproven** — neither E-028 nor E-029
  proves bank is at the architecture limit, but no method tried has
  ever beaten 142.89 d. The empirical convergence across 12+ method
  families is the only "ceiling" evidence we have.
- **R3 = 111.76 d remains unjustified** by any reproducible method we
  control. It came from an external leaderboard; reaching it likely
  requires either a substantially different physics model (e.g.,
  multi-rev Lambert beyond max_revs=20) or a published solver we
  haven't implemented.

## Methodology trigger fired

This is the third negative result in a row for Ch2 small (E-516
24-h GA → 0 improvement, E-028 component-aware enum → 0 feasible,
E-029 LB-tightening → F3 inconclusive). Per
`vault/methodology/M-applying-methodology-triggers.md`, the next
action is **not** another solver variant. The methodology says: at
this point we either (a) pivot to an explicitly different domain
(external intel survey — find what HRI did to reach 101.65), or (b)
declare 142.89 the project bank and shift compute to other challenges
(Ch1 R3 paths, Ch3).
