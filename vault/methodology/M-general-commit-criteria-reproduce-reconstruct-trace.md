---
date: 2026-06-23
tags: [methodology, meta, version-control, reproducibility, provenance, hygiene]
status: ACTIVE — codified from the 2026-06-23 commit-hygiene pass after the E-710 breakthrough
related: ["[[M-general-instrument-experiments-before-launch]]", "[[feedback-persist-partials-survive-reboot]]", "[[M-general-foundation-then-search]]"]
---
# Commit criteria: reproduce + reconstruct + trace

## The rule (one line)

> **Commit everything necessary to *reproduce*, *reconstruct*, and *trace*
> the results — and nothing else.** A regenerable byproduct is not a
> result.

This is the decision procedure for "what goes in git" in a research
campaign that produces far more files (logs, caches, backups) than it
produces durable artifacts.

## The three things that MUST be committed

1. **Reproduce** — the *source* needed to re-run the work from scratch:
   every script, the environment spec (`environment.yml`), seeds, and any
   small input/config the scripts depend on. Test: *could a fresh clone
   regenerate the result by running committed code?* If a result depends
   on an uncommitted script, you cannot reproduce it — commit the script.

2. **Reconstruct** — the *result artifacts* that are expensive to
   regenerate and that downstream steps consume: the banked solution
   JSONs (`solutions/upload/*.json`). These are the deliverables; losing
   them costs real compute or a re-search.

3. **Trace** — the *provenance/reasoning*: the vault journals (E-/H-/L-/
   C-/M- nodes) that record what was tried, what the numbers were, and
   why a verdict was reached. The journal — not the raw log — is the
   authoritative trace; it cites the key numbers and links the artifacts.

## What is deliberately EXCLUDED (and why it's safe)

- **Regenerable caches** (`cache/*.npz`, precomputed tables) — gitignored.
  Safe **iff** the precompute script is committed (criterion 1). The
  exclusion of a 22 h dense table is only legitimate because
  `ch2_giant_precompute_1d.py` is in the repo. *Excluding a cache obliges
  you to commit its generator.*
- **Run logs** (`runs/*.log`) — byproducts. Their *conclusions* live in
  the trace journals; the raw log is regenerable by re-running. (Caveat:
  if a number lives ONLY in a log and nowhere in a journal, the trace is
  incomplete — fix the journal, don't commit the log.)
- **Operational backups** (`*.bak`, `*.bak.r2`, timestamped guard-bank
  copies) — transient safety nets. The bank progression they capture is
  recorded in journals; the final JSON is the result.
- **Machine-local runtime state** (watchdog `active_runs.json`, lock
  files, `loop-state.md`) — per-session, not a result.

## Procedure (each commit/push)

1. `git status` — bucket every change into reproduce / reconstruct /
   trace / excluded.
2. **Stage explicitly by name or directory** (never `git add -A`; CLAUDE.md
   §6) so excluded byproducts can't sneak in.
3. Prefer **focused commits** that mirror the buckets (e.g. one for
   source, one for journal+bank) — keeps history legible and bisectable.
4. **Self-check before declaring done:** *"Could someone reproduce every
   committed result from a fresh clone, and trace why each verdict was
   reached, using only what's in git?"* If no → something in 1–3 is
   missing. If a result needs a file you're about to exclude → it's not a
   byproduct, commit it.
5. **Vault completeness gate:** `git status vault/` should be empty at the
   end of a documented session. An uncommitted journal means an untraceable
   result.

## Why this matters here

The campaign accreted 220+ run logs, dozens of `.bak` files, and multi-hour
caches across sessions. Committing all of it buries the signal; committing
none of it loses reproducibility. The reproduce/reconstruct/trace test
draws the line crisply: **source + deliverables + journals in; regenerable
byproducts out, provided their generators are in.** The one failure mode to
watch is excluding a cache whose generator is *also* uncommitted — then the
result is neither stored nor reproducible. The self-check in step 4 catches
exactly that.
