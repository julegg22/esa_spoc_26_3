---
id: OPEN-PATHS
type: frontier
updated: 2026-05-18
tags: [frontier]
---

# Frontier — the single list of "what we could do next"

> [!important] Single frontier (META.md §2)
> This is the **only** list of candidate next moves. Ideas living in
> chat do not exist. Selection policy: pick the open H maximizing
> `ROI = expected_points / max(estimated_effort_h, 0.25)`; tie-break
> on time-to-first-signal, then diversity, then unblocking (META.md §5).
> Reprice after every experiment and log the re-pricing below.

## Live view

![[frontier.base]]

## Status: BOOTSTRAP PENDING

The campaign substrate was rebuilt from scratch on **2026-05-18**
(fresh-start scaffold; see narrative log). **No hypotheses exist yet.**
Per META.md §6 *Bootstrapping the frontier*, candidate hypotheses are
**discussed with the user first**, then committed as `H-NNN` files at
`status: draft`, with exactly one promoted to `status: open` per the
§5 ROI selection.

Underlying observations and lessons are committed immediately as they
surface (§2 *Commit on learn*), independent of which H are approved.

### Open (status: open) — at most one active per compute stream (§2)

*(none — bootstrap pending)*

### Drafts (priced siblings, §16) — promote / prune / expire

*(none — bootstrap pending)*

## Narrative log — the frontier has history (§5)

- **2026-05-18** — Repo instance `esa_spoc_26_3`. Methodology
  scaffold (`CLAUDE.md`/`GOALS.md`/`META.md`) and tier-1 docs were
  inherited from a prior mature campaign whose vault nodes
  (H/E/T/C/M/L/O, templates, scripts, frontier) were absent. User
  directed a **fresh-start scaffold rebuild**: created `_templates/`
  (10 node templates), node directories, `open-paths.md`,
  `frontier.base`, `scripts/`, `solutions/upload/`, draft
  `environment.yml`. Frontier is empty; next step is the
  bootstrap discussion (no `H-NNN` committed without it).
