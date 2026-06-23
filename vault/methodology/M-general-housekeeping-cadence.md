---
date: 2026-06-23
tags: [methodology, meta, process, hygiene, vault, version-control, cadence]
status: ACTIVE — codified 2026-06-23 after a commit-hygiene pass found 19 untracked scripts, an orphan journal, 128 dangling links
related: ["[[M-general-commit-criteria-reproduce-reconstruct-trace]]", "[[M-001-proactive-concept-capture]]", "[[feedback-loop-doc-commit-submission-policy]]"]
---
# Housekeeping cadence: keeping the vault + git from drifting

## The problem

A fast research campaign accretes drift that is invisible until something
looks for it: untracked source scripts (reproducibility gaps), uncommitted
journals (untraceable results), unpushed commits, dangling `[[wikilinks]]`,
`MEMORY.md` pointer rot, and gitignored caches with no committed generator.
None of these surface in normal work; all of them corrode
reproduce/reconstruct/trace ([[M-general-commit-criteria-reproduce-reconstruct-trace]]).

## The split: mechanical vs judgment

- **Mechanical** (deterministic, scriptable, ~1 s) → `scripts/housekeeping_check.py`.
  Detects: uncommitted vault, untracked scripts, unpushed commits, dangling
  links, MEMORY.md pointer drift, cache-without-generator. Exit 1 on drift so
  it can gate a tick or CI. It **flags**, it does not decide.
- **Judgment** (agent only) → did this session introduce a reusable
  technique/insight that deserves a C-/L-/M- note ([[M-001-proactive-concept-capture]])?
  Are journals complete (numbers cited, verdict recorded)? Is the session note
  written? The script can't answer these; the agent must.

## The three-tier cadence

1. **Every `/loop` tick (mechanical gate).** Run `housekeeping_check.py`. If it
   exits non-zero, fix the flagged mechanics *that tick* (commit the journal,
   add the untracked script, push) before moving on. Cheap; rides the existing
   campaign heartbeat — no separate schedule for the common case.
2. **Session boundaries (judgment review).** On wind-down (and at resume): run
   the script, then the M-001 capture-check — "what did we learn that isn't yet
   a node?" Write the session note. `git status vault/` must end empty.
3. **Weekly (cloud cron, consolidation).** A scheduled headless job runs the
   full audit, triages accumulated drift (e.g. the dangling-link backlog), and
   writes the `vault/reviews/` weekly rollup that META.md §14 specifies. Runs in
   the cloud so it fires even on idle days / closed sessions.

## Operating rules

- **Fix mechanical drift immediately; never batch it.** A flagged item left for
  "later" is how 19 scripts went untracked.
- **Excluding a cache obliges committing its generator** — the script's
  cache-without-generator check enforces exactly this trap.
- **Dangling links are a backlog, not a blocker.** Triage them in the weekly
  pass (many are historical renames); don't let 100+ legacy links gate a tick.
- **The script gates; the agent captures.** A clean mechanical run does NOT mean
  housekeeping is done — the judgment review (M-001) is the part that turns
  insight into durable nodes.

## In practice

- `scripts/housekeeping_check.py` — the mechanical checker (run anytime;
  `--memory-dir` to point at the auto-memory dir).
- Loop prompt: add "run housekeeping_check.py; fix any drift this tick."
- Cron: weekly headless review → `vault/reviews/`.
