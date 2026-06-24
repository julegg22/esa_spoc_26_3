---
date: 2026-06-24
tags: [methodology, meta, vault, links, naming, hygiene, process]
status: ACTIVE — root-cause analysis of the 129 dangling links found & fixed 2026-06-23/24
related: ["[[M-general-housekeeping-cadence]]", "[[M-general-commit-criteria-reproduce-reconstruct-trace]]", "[[M-001-proactive-concept-capture]]", "[[M-general-retraction-annotation]]"]
---
# Vault link & note-naming hygiene

The housekeeping pass surfaced **129 dangling `[[wikilinks]]`** (76 auto/manually fixed; the rest
memory-slugs or never-written notes). This note diagnoses *why* they accumulated and sets conventions so
they don't recur. It is the naming/link companion to [[M-general-housekeeping-cadence]] (when to check).

## Root-cause analysis (evidence-grounded)

| # | cause | evidence | share |
|---|---|---|---|
| 1 | **Mutable / reassigned IDs** | the commit *"Add non-expert concept primers C-001..C-004"* reassigned IDs: links written against the prior scheme (`[[C-006-lambert-problem-and-orbital-tsp]]`) now resolve to a *different* concept (C-001 = `cr3bp-and-bicircular-problem`). No file `*lambert-two-point-bvp*` ever existed. | ~36 links |
| 2 | **Bare-ID ≠ filename stem** | `[[C-015-fcmaes-coordinated-retry]]` doesn't resolve to `C-015-fcmaes-coordinated-retry` under strict matching. | ~25 |
| 3 | **Two parallel namespaces** | vault uses typed-ID stems (`M-general-…`); the auto-memory dir uses bare topic-slugs (`anti-oscillation-discipline`). Vault docs linked the memory slugs, which are not vault nodes (and the memory dir isn't in the repo). | ~129 refs (most legit-but-dangling) |
| 4 | **Link-syntax drift** | four coexisting forms: `[[concepts/C-031-…]]` (path-prefixed, 214×), `[[M-general-…]]` (stem), `[[M-general-anti-oscillation-discipline]]` (memory slug, 129×), and table-escaped `[[…\]]`. Heterogeneity = fragility. | — |
| 5 | **Forward-refs to unwritten notes** | `[[H-016-beam-search-easy]]`, `[[E-707-…]]` — planned hypotheses/experiments linked before (or instead of) being written. | ~30 |
| 6 | **No integrity gate** | nothing checked dangling links until 2026-06-23, so 1–5 compounded silently across renames and sessions. | root multiplier |

**The dominant cause is #1 (mutable IDs).** A rename of the *slug* breaks only the links to that one note; a
reassignment of an *ID* silently re-points every inbound link to the wrong concept — the worst failure mode
because the links still "resolve," just to the wrong thing.

## Conventions (rules to prevent recurrence)

### Identifiers
- **IDs are immutable and append-only.** Once `C-017` is assigned, it is never reused, renumbered, or
  reassigned to a different topic. Need to retire a note? Set `status: superseded` and link the successor
  ([[M-general-retraction-annotation]]) — never recycle its number.
- **One ID per type, monotonic.** Types: C (concept), E (experiment), L (lesson), M (methodology),
  T (takeaway), O (observation), H (hypothesis), Q (question), S (session), A (analysis). S/A are
  date-keyed (`S-YYYY-MM-DD-…`); the rest are `<TYPE>-<NNN>-…`.

### File & link naming
- **Filename = `<TYPE>-<ID>-<kebab-slug>.md`.** Slug lowercase-kebab, descriptive, *stable*.
- **Link by the full canonical stem: `[[C-017-subtour-bridge-insertion-large-clusters]]`.** This is the
  Obsidian-native, unambiguous form. **No** bare-ID (`[[C-017-subtour-bridge-insertion-large-clusters]]`), **no** path prefix
  (`[[concepts/…]]`), **no** `.md` suffix, **no** escaped brackets.
- Need a readable label? Use an alias: `[[C-017-…|subtour bridges]]` — the target stays canonical.
- **Renaming a slug is a migration, not an edit:** run `fix_dangling_links.py` (or rewrite all backlinks)
  **in the same commit** so no inbound link is left dangling.

### Cross-namespace (vault ↔ auto-memory)
- **Vault-internal links point to vault nodes only.** Do not link auto-memory bare-slugs
  (`[[E-040-ch2-medium-ultrafine-retime]]`) from committed vault docs — the memory dir is machine-local and absent from the
  repo, so such links are dangling-by-construction. Link the corresponding vault node
  (`[[E-040-…]]` / `[[M-general-…]]`) instead. (Legacy memory-slug links are mapped in
  `fix_dangling_links.py`'s `MANUAL_MAP`.)

### Forward references
- **A `[[wikilink]]` must resolve to an existing note.** To reference work not yet written, either create a
  stub (frontmatter + one-line intent) or use plain text / a `TODO:` marker — not wiki-link syntax. An
  intended-but-unwritten `[[link]]` is a silent debt; a stub or TODO is a tracked one.

### Tables & code
- Don't put wiki-links in markdown table cells that force bracket-escaping (`\]]`); if a table must
  reference a node, use an alias or restructure. Never wiki-link code identifiers (`[[dv0x,dv0y,dv0z]]`).

## Orphan notes (0 inbound links)
An orphan is a consistency smell, not always a defect. Triage by type:
- **Concepts / analyses / methodology** orphaned → **a real gap**: a concept nothing references, or an
  analysis no experiment cites, is under-integrated. Link it from the note(s) that use it (e.g. the WSB
  concepts `C-021..C-025` were embedded into `[[A-2026-05-29-coherent-physics-model]]`).
- **Follow-up experiments** orphaned → link from their parent (`[[E-713-…]]` from `[[E-710-…]]`).
- **Refuted / terminal experiments** orphaned → **acceptable leaves.** A dead-end experiment nothing built
  on *should* be a leaf; that accurately documents the exploration. Don't fabricate inbound links to satisfy
  a metric — they stay findable by ID/search/git.
Rule: connect orphan concepts/analyses/methodology and live follow-ups; leave refuted dead-ends as leaves.

## The gate (enforcement)
`scripts/housekeeping_check.py` flags dangling links every `/loop` tick, at session boundaries, and in the
weekly cloud routine ([[M-general-housekeeping-cadence]]). Rules:
- **Dangling links are a tracked backlog, fixed promptly — never allowed to accumulate.**
- Fix with `scripts/fix_dangling_links.py` (bare-ID→canonical, exact topic-suffix across reassigned IDs,
  same-ID reslug, memory-slug→vault-node map, escaped-link repair). It applies only *confident* rewrites and
  reports ambiguous/missing for human triage — never guesses (a wrong link is worse than a dangling one).
- The checker ignores `_templates/`, `NNN` placeholders, code-block fragments and YAML-list artifacts, so
  the count reflects *real* drift.

## One-line takeaway
**Immutable IDs + one canonical link form + a dangling-link gate.** The 129 links came almost entirely from
violating the first two without the third to catch it.
