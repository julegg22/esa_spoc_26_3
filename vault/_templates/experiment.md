---
id: E-NNN
type: experiment
status: draft            # draft | running | done | invalidated
tags: []

# link
hypothesis:              # [[H-NNN]]

# chronology (tool-stamped — §2)
created:
ran_start:
ran_end:
duration_runtime:

# reproducibility (replayable a year from now — §2)
code:                    # repo-relative entrypoint path
commit:                  # git SHA at run time
inputs:                  # instance files / params
outputs:                 # path(s) to result artefacts (E-NNN/ folder if heavy)
plots: []                # path(s) — >= 1 plot required for quantitative results (§2)
seed:
env:                     # env name / lockfile / OS

# provenance (§4, §15) — repo-relative source paths the run depended on
code_dependencies: []    # path | {path: ..., verified_by: [[L-NNN]] | [[E-NNN-smoke]]}

# resources (§8)
compute:
  cpu_seconds:
  peak_memory_mb:
  cores:
effort_person_hours:

# result
metrics: {}              # free-form dict
verdict:                 # supports | refutes | inconclusive

# supersession (nullable — §15 cascade; original verdict NOT rewritten)
invalidation:
  invalidated_by:        # [[L-NNN]]
  superseded_by:         # [[E-NNN-redo]]
  invalidated_at:
  notes:
---

# E-NNN — <what this run tests>

## Setup

<Instance, parameters, hardware, env. Enough to replay exactly.>

## Procedure

<What was run, in order.>

## Results

<Metrics table + **>= 1 embedded plot** (invariant: plot on
quantitative result).>

![plot](E-NNN/plot.png)

## Verdict + analysis (2–5 lines — §6)

**verdict:** supports | refutes | inconclusive

<Why the metrics imply that verdict, against the H's prediction.>
