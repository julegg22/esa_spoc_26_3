---
id: E-031
type: experiment
status: done (round 1; round 2 in progress)
tags: [ch2, small, slsqp, perm-search, c6-fix, evaluator-substrate, bank-update]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-03
ran_start: 2026-06-03
ran_end: 2026-06-04
duration_runtime: "round 1: 28.5 min wall, 6 workers, 5000 candidates"

# reproducibility
code: scripts/ch2_e521_slsqp_perm_search.py
commit: 4dcd1ec (pre-launch)
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp
  solutions/upload/small.json (current bank: 142.8359 d)
outputs: |
  runs/ch2/e521_full.log
  /tmp/ch2_e521_result.json
  /tmp/ch2_e521_history.jsonl  (every candidate's walk_mk + slsqp_mk)
plots: []
seed: 0
env: micromamba spoc26, python 3.13.13

code_dependencies:
  - src/esa_spoc_26/ch2_kttsp.py
  - src/esa_spoc_26/ch2_insert_lns.py
  - scripts/ch2_e520_slsqp_multistart.py  (penalty-objective formulation)

compute:
  cpu_seconds:
  peak_memory_mb:
  cores: 6
  wall_budget_min: 60

effort_person_hours:

metrics:
  round1_bank_entry_d: 142.8359
  round1_bank_exit_d: 142.2897
  round1_shaved_d: 0.5462                  # 10× E-519b's shave
  round1_n_candidates: 5000
  round1_n_walk_ok: 109                    # 2.2 % walk-feasible rate
  round1_n_slsqp_polished: 76              # those with walk_mk ≤ 150 d
  round1_n_polished_feasible: 70           # 92 % SLSQP-feasibility retention
  round1_n_under_bank: 1                   # only 1 new perm < bank
  round1_wall_min: 28.5
verdict: refutes (bank-as-local-perm-opt; SLSQP-aware perm search finds non-bank perms)

invalidation:
  invalidated_by:
  superseded_by:
  invalidated_at:
  notes:
---

# E-031 — Ch2 small: perm search with SLSQP-polished evaluation

## Why this experiment exists

E-519b (2026-06-03) banked 142.8359 d, proving walk_perm_chrono had
been a suboptimal evaluator (bug C6). Every prior perm comparison
(E-509's 30k+ perms, E-516's 24h GA) used walk_perm_chrono and is
therefore in distorted units. The principled fix is to replace the
evaluator with **walk_perm_chrono + SLSQP polish**, then redo a
perm search on top.

E-520 (today): SLSQP from bank seed reproduces 142.8359 d (8 random
perturbations all fell infeasible). Bank IS in a tight (times, tofs)
local opt.

E-521 (this): bank-anchored 2-opt + or-opt perm mutations, each
evaluated via walk → SLSQP polish. Look for any perm whose polished
mk beats 142.8359 d.

## Hypothesis (pre-registered)

1. **Decomposition row addressed**: perm choice (C1 in-comp Hamilton
   slack + C2/C6 schedule slack jointly). Tests whether non-bank
   perms exist that, after correct (SLSQP) polish, beat bank.
2. **Empirical signature**: of N mutated perms, ≥1 with SLSQP-polished
   makespan < 142.8359 d.
3. **Predicted magnitude**: 0.05 – 5 d. The E-519b improvement on
   bank's single leg was 0.055 d. Different perms may have multiple
   shavable legs → could compound.

## Setup

- N candidates: 5000 (~30 min wall, 6 workers).
- Mutations: 2-opt segment reverse (60%), or-opt move L∈{1,2} (30%),
  swap (10%). 1–3 mutations per candidate starting from bank perm.
- Evaluator pipeline per candidate:
  1. walk_perm_chrono(perm) — cheap filter (~1-2s/call). Skip if
     infeasible or walk_mk > 150 d.
  2. Identify exc set from walk's dvs.
  3. SLSQP polish: minimize penalized objective (mk + PEN_CHRONO ×
     chrono_violation + PEN_DV × dv_violation) with bounds.
     `maxiter=120, ftol=1e-7`.
  4. UDP validate via `kt.fitness`; if feasible and mk < 142.8359,
     auto-bank.
- Atomic bank: `solutions/upload/small.json` + backup
  `solutions/upload/small.json.bak.20260603.e521`.

## Pre-registered failure modes

- **F1** — walk_perm_chrono feasibility rate < 1%. **Mitigation**:
  smaller mutation footprint (single-move, not chained).
- **F2** — SLSQP polish always returns infeasible on non-bank perms
  (the basin radius is universally small). **Reading**: bank is
  globally optimal among bank-adjacent perms; pivot to far-perm
  search (E-516 GA style but with SLSQP).
- **F3** — Polished mk < bank but UDP rejects (constraint
  formulation gap). Need explicit constraints via `trust-constr`.

## Procedure (round 1)

1. Generate 5000 candidate perms via bank-anchored 2-opt (60%) +
   or-opt L∈{1,2} (30%) + swap (10%) mutations; 1–3 mutations chained
   per candidate. Bank's first/last node preserved by mutation logic
   (mutates interior only).
2. For each candidate: walk_perm_chrono → if `walk_mk ≤ 150 d`,
   identify exc-leg set from walk's dvs, then SLSQP polish 96-dim
   (times, tofs) with penalty objective.
3. UDP validate via `kt.fitness`; bank if `feasible AND mk <
   142.8359`.
4. 6 worker processes, mp.Pool, ~3 candidates/sec aggregate.

## Results (round 1)

| Metric | Value |
|---|---|
| Bank entry | 142.8359 d |
| **Bank exit** | **142.2897 d** |
| Shaved | **−0.5462 d** (≈ 10× the E-519b leg-only shave on bank itself) |
| Candidates | 5000 |
| Walk-feasible | 109 (2.2 %) |
| SLSQP-polished | 76 (those with `walk_mk ≤ 150`) |
| Polished-feasible | 70 (92 % retention) |
| Under bank | 1 |
| Wall | 28.5 min, 6 cores |
| Banked perm | start=34, end=32, exc count=5 (unchanged structure) |

The single under-bank perm has the same first 5 and last node as bank
(start=34, end=32 → ` [34, 23, 18, 46, 12, …, 14, 33, 16, 27, 32]`)
— a bank-adjacent interior mutation, not a structural rewrite.

## Verdict + analysis (round 1)

**verdict:** refutes "bank is locally optimal in (perm × times ×
tofs) joint space" — earlier claims (memory file `ch2-small-floor-...`,
audit §1) were artifacts of the broken walk_perm_chrono evaluator.

The decisive finding: only 1 of 70 SLSQP-polished-feasible candidates
beat bank, BUT that one shaved 0.55 d — significantly larger than the
leg-level shave on bank itself (0.055 d). This pattern says the
under-bank perm has multiple legs with realizable slack that bank
doesn't have access to (presumably because bank's specific (times,
tofs) basin is locally optimal but not globally so).

**Methodological implication**: the C6 evaluator fix has compounding
returns. Each new bank found via SLSQP-aware search is itself a
target for further SLSQP-aware search (round 2 launched).

## Round 2

Same script, same params, with NEW bank (142.2897) as seed for
mutations. In progress; report on completion.
