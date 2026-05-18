---
id: O-NNN
type: observation
status: confirmed        # confirmed | superseded
tags: []
source:                  # MANDATORY — file path, URL, or [[E-NNN]] (§4)
created:                 # tool-stamped at the moment the fact surfaced (§2)
referenced_by: []        # [[H-NNN]] — every O referenced by >= 1 H or flagged at review (§9)
supersedes:              # [[O-NNN]] (corrections arrive as new O, append-only — §4)
superseded_by:           # [[O-NNN]]
---

# O-NNN — <what was observed>

## Observation

<The measurement / fact. No claim, no interpretation.>

## Source

<file / URL / E-NNN — how this was obtained, verbatim enough to re-fetch.>

## Why it matters

<Which hypotheses / questions this grounds. Append-only: corrections
come as a new O that links back here.>
