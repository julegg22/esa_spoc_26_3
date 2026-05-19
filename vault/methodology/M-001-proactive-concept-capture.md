---
id: M-001
type: methodology
status: confirmed
tags: [methodology, vault-pattern, process]
kind: process-pattern
scope: concept-capture / knowledge-base
severity: warning
confidence: high
generalizability: cross-campaign
created: 2026-05-19
source: "user directive 2026-05-19; session C-001..C-004 concept-primer batch"
supersedes:
superseded_by:
effort_person_hours: 0.3
---

# M-001 — Proactively capture new concepts as notes, as they appear

## What

Whenever a **new concept** materially enters the campaign — a domain
idea (BCP, LOI, weighted 3-D matching) or a tool/method (MIP-LNS,
differential correction) — a `C-NNN` concept note is written **at the
moment it appears**, written for a **non-expert** reader, not deferred
until someone asks. Concept capture is a continuous obligation, the
same discipline as *commit-on-learn* (`META.md §2`) and
*lesson-on-surprise*, applied to prior-knowledge substrate.

## Why it matters

The campaign is Human + Claude Code over a long horizon with context
loss between sessions and a methodology-validation publication goal
(`GOALS.md §3`). Concepts referenced but unwritten become silent
comprehension debt: a fresh-context agent (or a non-specialist
reader/reviewer of the eventual paper) cannot follow H/E/T/L bodies
that lean on undefined fundamentals. Writing the primer when the
concept is fresh is cheap (~5–10 min) and the explanation is sharper;
reconstructing it later is costly and lossy. Non-expert framing also
forces genuine understanding and makes the research legible — a
publication asset, not overhead.

## Evidence

- Session 2026-05-19: BCP/CR3BP/LOI/Δv/3-D-matching/MIP-LNS were used
  across H-001…H-006 / E-001…E-006 *before* any primer existed; a
  fresh agent hit exactly this gap. Batch C-001…C-004 closed it.
- `[[L-002-udp-served-via-graphql-not-git]]`: a wrong BCP assumption
  went unnoticed partly because the BCP was never written down as a
  checkable concept until forced.

## Implication

**Standing rule (now codified):** when a new concept appears in any
node body or dialogue, create its `C-NNN` note in the same working
unit (commit), non-expert audience, per the `META.md §11` template.
Migrated to `META.md §11` (hard rule) and `[[user]]` (portable
pointer). Applies to every campaign reusing this methodology.
Index new M nodes in `vault/methodology/README.md`.
