# tools/ — process & scaffolding (and the full scaffolding inventory)

Code and definitions that support **how we work**, not the science. This file is
the **canonical inventory** of all non-experiment (scaffolding / method / process)
files in the repo. Distinct from `scripts/` (experiment entrypoints that produce
scientific results / E-nodes) and `src/esa_spoc_26/` (the shared library). See
META §12 and `doc_methodology.md` (source map) for the three-tier split.

Scaffolding files are **not experiments**: they produce process actions, not
results, so they carry **no run-time provenance stamp** and map to no E-node.
They are still committed and tracked.

## 1. Process / scaffolding scripts — `tools/`
- **`housekeeping_check.py`** — mechanical drift check (uncommitted vault,
  dangling links, MEMORY.md pointer rot, cache-without-generator, un-triaged
  assumptions, missing-commit reproducibility gaps). Run at resume / wind-down /
  every loop tick; the `/housekeeping` command wraps it with judgment + cascade.
- **`fetch_leaderboards.py`** — read-only leaderboard fetch (stub; live fetching
  is done via direct read-only GraphQL queries).
- **`fix_dangling_links.py`** — vault-link maintenance (repoint / de-link dangling
  `[[wikilinks]]`).

## 2. Shared experiment helpers — `scripts/_*.py` (underscore-prefixed)
Imported *by* experiments; live next to them by convention (not experiments
themselves, not in `tools/`).
- **`_prov.py`** — run-time provenance stamp (`_prov.stamp(__file__)` → the
  `[PROV] commit=<sha>[+DIRTY]` log line). The keystone of reproducibility.
- (`_audit_hard32_scan.py` is a *throwaway diagnostic*, not a shared helper —
  it stays as a one-off experiment/audit.)

## 3. Method command definitions — `.claude/commands/`
- **`deepaudit.md`** — the deep single-prompt audit (ladder-structured).
- **`housekeeping.md`** — `/housekeeping [push]`: the full hygiene cadence in one pass.
- *(proposed, not yet built: `/cascade`, `/sweep` — see `doc_methodology.md` §7.4.)*

## 4. Process / methodology docs
- Root: **`doc_methodology.md`** (operating model — read first), **`doc_lessons.md`**
  (case library), **`CLAUDE.md`** (always-loaded hot rules), **`META.md`**
  (scientific-loop mechanics), **`GOALS.md`** (what we optimize).
- **`vault/methodology/M-general-*.md`** — atomic deep-dives (the ladder audit,
  assumption provenance, resource gate, cadence, etc.).
- **`vault/assumptions.md`** — the live Assumption Register.

## Rule for placing a new file
- Produces a scientific result (→ an E-node)? → **`scripts/`** (reproducibility
  discipline applies: `_prov.stamp`, clean-tree-before-bank).
- Shared infrastructure imported by experiments? → **`src/esa_spoc_26/`**.
- Supports the process (housekeeping, vault maintenance, workflow, reporting)?
  → **`tools/`** (add it to §1 above in the same commit).
