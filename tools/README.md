# tools/ — process & scaffolding scripts

Code that supports **how we work**, not the science. Distinct from `scripts/`
(experiment entrypoints that produce scientific results / E-nodes) and
`src/esa_spoc_26/` (the shared library). See META §12 for the three-tier split.

Files here are **not experiments**: they produce process actions, not results, so
they carry **no run-time provenance stamp** and map to no E-node. They are still
committed and tracked.

- `housekeeping_check.py` — mechanical drift check (uncommitted vault, dangling
  links, MEMORY.md pointer rot, cache-without-generator, un-triaged assumptions,
  missing-commit reproducibility gaps). Run at resume / wind-down / every loop
  tick; the `/housekeeping` command wraps it with the judgment + cascade steps.
- `fetch_leaderboards.py` — read-only leaderboard fetch (stub; live fetching is
  done via direct read-only GraphQL queries).

**Rule:** a new script is a `tool` iff it supports the process (housekeeping,
vault maintenance, workflow orchestration, leaderboard/reporting) and produces no
scientific result. If it produces a result → `scripts/`. If it's shared
infrastructure imported by experiments → `src/esa_spoc_26/`.
