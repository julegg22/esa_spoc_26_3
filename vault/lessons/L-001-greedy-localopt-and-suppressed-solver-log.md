---
id: L-001
type: lesson
status: confirmed
tags: [ch1, optimization, gotcha, env]
kind: gotcha
scope: optimization/3d-matching + tooling/highs-watchdog
severity: warning
confidence: high
created: 2026-05-18
source: "[[experiments/E-001-ch1-matching-first-attempts]]"
supersedes:
superseded_by:
effort_person_hours: 0.3
---

# L-001 — Greedy is a hard local optimum; and never suppress a long solver's log

## Context

H-001 / E-001: weighted 3-D matching on Ch1 `matching-i`/`matching-ii`.

## The lesson

**(1) Algorithmic gotcha — the dominant one.** Weight-descending
greedy for weighted 3-D matching is a *strict* local optimum for the
"add one excluded transfer, eject its ≤3 conflicting selected
transfers" neighbourhood. Proof: greedy excludes transfer *i* only
because a higher-or-equal-weight transfer already owns one of
*i*'s e/l/d nodes, so `wᵢ − Σ w(conflicts) ≤ 0` for every excluded
*i*. Consequences observed empirically (0 improvement):

- ruin + weight-greedy-recreate LNS → greedy is a **fixed point**
  (re-adds the same transfers in the same order).
- 1-in/≤3-out ejection improvement → no positive-gain move exists.

Escaping requires moves greedy cannot reverse: **worse-accepting**
search (SA/Tabu), **long ejection chains** (multi-step, net gain
evaluated over the chain), **MIP-based LNS** (exact sub-solve over a
destroyed region), or a **strong exact solver**. This generalises:
expect strong local optima across SpOC4 (confirmed by user from past
SpOC experience — see [[user]] *Conservative expectations*).

**(2) Tooling gotcha.** `highspy` with `output_flag=False` and no
`log_file` produces *zero* progress output, which blinded the 5×
wall-time watchdog (META.md §2) during a 600 s MIP — could not tell
"working" from "stuck". **Always route a long solver's log to a
file** (`setOptionValue("log_file", path)`, `output_flag` off for
stdout) so the watchdog can inspect incumbent/gap/nodes.

## Impact / scope

Affects every Ch1 matching attempt and any future greedy-seeded
local search. Not foundational-code-buggy (no cascade) — it is a
design constraint. Fix forward: solver/log observability + stronger
search operators (see [[takeaways/T-001-ch1-matching-needs-strong-search]]).

## Fix / workaround

- Solver runs: set `log_file`; arm watchdog on the log, not silence.
- Search: drop pure greedy-recreate / 1-step ejection as a *closure*
  method; use them only as warm starts for stronger parallel search.
