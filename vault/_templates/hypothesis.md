---
id: H-NNN
type: hypothesis
status: draft            # draft | open | testing | analyzed | corroborated | refuted | abandoned | invalidated
tags: []

# links (META.md §9 — every H links up)
parent:                  # [[H-NNN]] or [[Q-NNN]]
question:                # [[Q-NNN]]
children_experiments: [] # [[E-NNN]]
children_hypotheses: []  # [[H-NNN]]
concurrent_with: []      # [[H-NNN]] siblings held open / considered together (§16, §2)

# chronology (timestamps stamped by tool, not reconstructed — §2)
created:
tested_start:
tested_end:
duration_testing:

# accounting (§8)
effort_person_hours:
expected_points:         # GOALS.md §7 — SpOC4 leaderboard points
estimated_effort_h:
priority:                # 1 (highest) .. 5
mode: full               # full | lite — lite only if expected_points<=2 AND single-H AND off-the-shelf (§6)

# content
claim:
falsifiable_prediction:  # "metric >= X (= rank-N cutoff at YYYY-MM-DD)" — set BEFORE first E (§2)
modification_rationale:  # nullable only when rooted directly on a Q (§7) — cite parent [[T-NNN]]

# supersession (nullable — set by §15 cascade, not hand-edited)
invalidated_by:          # [[L-NNN]]
superseded_by:           # [[H-NNN]]
invalidated_at:
backfilled_from:         # "session S-YYYY-MM-DD" / "dialogue YYYY-MM-DD reconstruction" (§16 backfill)
---

# H-NNN — <one-line claim>

## Claim

<What we believe is true. One or two sentences.>

## Falsifiable prediction

<Concrete metric + threshold, calibrated to the live leaderboard
(GOALS.md §4). Written before the first experiment runs.>

## Rationale / approach

<Why this is plausible; the method that will test it. Cite the
parent's `[[T-NNN]]` if this is a continuation.>

## Experiments

- [[E-NNN]] — <one line>

## Analysis (filled at close — §6)

<Terse aggregate over the E set. Links to every E. Never moved to
corroborated/refuted without this block.>

## Next steps / siblings (§16)

<Alternatives < 0.5 h noted here. Alternatives >= 0.5 h become draft
sibling H files on open-paths.md.>
