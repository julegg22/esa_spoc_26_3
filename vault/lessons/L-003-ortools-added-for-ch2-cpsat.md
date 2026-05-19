---
id: L-003
type: lesson
status: confirmed
tags: [env, decision, ch2]
kind: decision
scope: env/spoc26
severity: tip
confidence: high
created: 2026-05-19
source: "user-approved 2026-05-19 (Ch2 CP-SAT decision); E-014/T-006"
supersedes:
superseded_by:
effort_person_hours: 0.1
---

# L-003 — `ortools` added to spoc26 for Ch2 CP-SAT

## Context

E-014/T-006: Ch2 is a constrained-Hamiltonian-path; constructive
heuristics refuted; an exact constraint solver is required.

## The lesson (ADR)

`ortools` (9.15.6755) `pip`-installed into the `spoc26` micromamba
env, user-approved. CP-SAT (`ortools.sat.python.cp_model`) verified
importable. Rationale: CP-SAT models the Ch2 path + ≤5-exception
budget + makespan natively; the inherited glossary already
anticipated it (CP-SAT/OR-Tools). Pulled via `conda-forge` env's
`pip:` section so the env stays reproducible.

## Impact / scope

`environment.yml` updated (`pip: [ortools]`). Used by
`src/esa_spoc_26/ch2_cpsat.py`. Not foundational to prior results
(no cascade). Re-create env: `micromamba create -f environment.yml`.

## Fix / workaround

If a fresh env lacks it: `micromamba run -n spoc26 pip install ortools`.
