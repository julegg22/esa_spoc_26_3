---
id: L-004
type: lesson
status: confirmed
tags: [workflow, gotcha, env]
kind: gotcha
scope: workflow/background-runs
severity: warning
confidence: high
created: 2026-05-19
source: "structure-probe failure 2026-05-19 (Path NameError + mamba lock)"
supersedes:
superseded_by:
effort_person_hours: 0.1
---

# L-004 — Verify before backgrounding; one `micromamba run` at a time

## Context

The first medium/large structure probe was launched as a background
job *immediately after editing* `ch2_kttsp.py`, **before** ruff ran.
ruff then caught a `Path` NameError — but the background job had
already started on the broken code and crashed (wasted run). It was
also launched as two parallel `micromamba run` calls, which
contended on the mamba lock (`Could not set lock libmamba`).

## The lesson

1. **Always `ruff` + a quick smoke (or at least an import check) of
   the exact code path BEFORE `run_in_background`.** A background
   job freezes the code at launch; a lint/typo caught seconds later
   doesn't help the already-running (broken) job — pure wasted
   wall-time, and the failure surfaces late.
2. **One `micromamba run -n <env>` process at a time.** Parallel
   `micromamba run` invocations fight over `~/.cache/mamba/proc`.
   For parallelism, use a *single* `micromamba run python …` whose
   script does the multiprocessing internally (Pool), not N shell
   `micromamba run` calls.

## Impact / scope

Workflow-wide (every background launch this campaign). Cost was one
wasted probe (~minutes) — cheap, but recurring if not codified.

## Fix / workaround

Pre-launch checklist: `ruff check` clean → 1-iteration/import smoke
→ then `run_in_background`. Parallel compute = internal `mp.Pool`
under one `micromamba run`.
