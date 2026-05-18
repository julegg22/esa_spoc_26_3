---
id: L-NNN
type: lesson
status: draft            # draft | confirmed | superseded
tags: []
kind:                    # gotcha | decision | tip | workaround
scope:                   # module / tool / workflow affected
severity:                # blocker | warning | tip
confidence:              # low | medium | high
created:                 # written when the surprise is fresh (§2)
source:                  # [[E-NNN]] / [[H-NNN]] / commit SHA / URL
supersedes:              # [[L-NNN]]
superseded_by:           # [[L-NNN]]
effort_person_hours:
---

# L-NNN — <one-line engineering lesson>

## Context

<What we were doing when this surfaced.>

## The lesson

<Expected vs actual behaviour. Atomic — about our *means* (code,
env, tooling), not the problem (that is a takeaway).>

## Impact / scope

<Which modules / E depend on this. For `severity: blocker` on
foundational code, this triggers the §15 cascade — list the
affected E set here.>

## Fix / workaround

<Commit SHA of the fix, or the kludge and its known scope.>
