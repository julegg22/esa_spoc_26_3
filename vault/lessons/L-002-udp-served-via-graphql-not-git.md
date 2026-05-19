---
id: L-002
type: lesson
status: confirmed
tags: [env, gotcha, ch1, decision]
kind: gotcha
scope: spoc4-grounding / validator-provenance
severity: blocker
confidence: high
created: 2026-05-19
source: "user challenge 2026-05-19; GraphQL ProblemType.udpFile; reference/spoc4_udp/*.py"
supersedes:
superseded_by:
effort_person_hours: 0.4
---

# L-002 — Per-problem UDP/validator is served via GraphQL `udpFile`, not the git repo

## Context

I asserted (O-003, `ch1_trajectory.py` v1, S-2026-05-18, several
commit msgs) that **Ch1 ships no validator code** because the cloned
`reference/SpOC4` repo has Python only for Ch2/Ch3. The user pushed
back ("there usually is one"). They were right.

## The lesson

Every SpOC4 problem exposes its official UDP/validator at
`ProblemType.udpFile` via the GraphQL API — a per-problem URL like
`https://api.optimize.esa.int/media/problems/<challenge>-<problem>-<ts>.py`.
The git starter kit is **not** the source of truth for validators;
it omits Ch1 entirely. **Always fetch `udpFile` for every problem
before implementing any fitness/dynamics.** Query:
`{challenge(id:…){problems{id udpFile}}}`; download read-only.

Why blocker-class: the Ch1 trajectory README's BCP table gives
`μ_s = 3.3294604877306713E5`, but the official UDP uses
`BCP_MU_S = MU_SUN/(MU_MOON+MU_EARTH) ≈ 3.289E5` (and
`μ = MU_MOON/(MU_MOON+MU_EARTH)`). Building H-002 on the README
constants would have produced trajectories the server **silently
scores 0** (orbit-match tol 1e-6) — an undetectable-without-the-UDP
failure. The official `propagate`/`state2earth`/`state2moon`/
`fitness` (with `pk.ic2par`, Earth/Moon impact events) are the only
correct oracle.

## Impact / scope (cascade per §15)

- **Matching (H-001/004/005/006, E-001–005, T-001–004): NOT
  affected.** The official `matching-i`/`matching-ii` UDP fitness
  (`max Σw, each a/b/c ≤1, invalid→0, negated`) is identical to our
  ILP. Banked artifacts 33 338 / 72 018 remain valid. No cascade.
- **H-002 (trajectory): foundation only, no results yet.**
  `ch1_trajectory.py` v1 BCP rebuilt to mirror the official UDP
  exactly (constants + propagate + state2*). EOM *form* I derived
  was correct; constants/validation were not.
- O-003's "no provided UDP/validator for Ch1" corrected by
  [[observations/O-004-ch1-udp-via-api-correction]] (append-only).

## Fix / workaround

UDPs fetched to `reference/spoc4_udp/` (gitignored, upstream).
H-002 optimises against the official `fitness`/`propagate` as the
truth oracle. Grounding checklist updated: for any new problem,
fetch `udpFile` first.
