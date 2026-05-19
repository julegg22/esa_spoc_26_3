---
id: USER
type: user-profile
updated: 2026-04-25T19:30:00+02:00
tags: [user, profile]
---

# User profile — JJ

*Living document. Captures user role, background, and working style
so a fresh session on any machine can orient quickly. Hard rules
promote to `CLAUDE.md` or `META.md` once codified; soft preferences
stay here.*

> [!note] Stealth-mode submission
> Optimise leaderboard alias is **`JJ & CC`** (J = the user, C =
> Claude Code). Public-facing repo content is anonymised: no real
> name, email, or institutional affiliation. The GitHub
> noreply identity on commits is the only persisted pseudonymous
> handle.
>
> The Optimise leaderboard entry **`Team HRI` (Honda Research
> Institute Europe, Germany)** is a **separate team of HRI
> colleagues**, not the user's `JJ & CC` alias. Recorded here so
> future sessions don't confuse "the user's institution appears
> on the leaderboard" with "the user has results posted." We
> don't share methods, intermediate results, or leaderboard
> intel with HRI colleagues; the campaign is an independent
> stealth entry.

## Role and context

- Education: physicist
- Maths: solid background (calculus, linear algebra, ODEs)
- This is the user's **first SpOC challenge**

## Strengths

- Physics-native thinking: equations, dynamics, falsifiable
  predictions.
- Good instincts for Ch1 Advanced (BCP), Ch2 (Keplerian mechanics
  + Lambert), Ch3 (CR3BP, periodic-orbit selection).

## Gaps

- Not a specialist in combinatorial optimization or metaheuristics
  — scaffolding in [[algorithm-menu]].
- First exposure to pygmo patterns; learning them via this campaign.

## Working constraints

- **Primary machine (since 2026-05-06): Linux**, with `uv` and
  `micromamba` working, no admin / App-Control restrictions. Lessons
  L-001 / L-004 / L-006 / L-007 are platform-historical; pykep, pygmo,
  heyoka, gurobipy install cleanly via the `spoc26` micromamba env
  built from `environment.yml`.

## Persistent preferences (hard)

- **5× wall-time watchdog on every long-running compute task.**
  When launching a sim / sweep / optimisation, declare an expected
  wall-time budget up front, then arm a watchdog that fires at
  5× expected. On fire: run a mid-run analysis (process alive?
  observable progress? cost model refuted?), then decide *continue
  / kill+fix / kill+abandon* — never silent. 
- **Idle cores are bugs.** At every end-of-turn, if no productive
  compute stream is running on this machine, justify *why* (queue
  empty? blocked on input? infra hiccup?). Transient infra problems
  get retried or routed around; never let a single failed launch
  end the turn while cores stay idle.
- **Parallelise runs; expect hard.** (User directive 2026-05-18,
  confirmed by [[takeaways/T-001-ch1-matching-needs-strong-search|T-001]].)
  SpOC challenges are *hard* — many local minima, solutions
  non-trivial (past-SpOC experience). Design every solver
  multi-core / multi-start by construction (parallel restarts,
  pygmo archipelago, parallel sub-MIP LNS), not as an afterthought.
  Be **conservative**: `expected_points` and falsifiable thresholds
  biased pessimistic; first results are baselines, not wins; never
  promise a cheap clear of a rank cutoff.

## Persistent preferences (soft)

- **Terse responses.** Data + decisions, minimal fluff.
- **Direct opinions over hedged menus.** When asked for a
  recommendation, give one; user will push back if wrong.
- **Discuss before committing H-files.** Bootstrap pattern in
  META.md §6.
- **Ask-but-never-stall.** (User directive 2026-05-18.) Asking back
  on strategic forks is valued — but if the user may be delayed or
  unavailable, do **not** block waiting. State the decision clearly
  (so it can be vetoed), then proceed on own best judgement and keep
  compute running. Asking and proceeding are not mutually exclusive:
  pose the question, act on the strongest option, course-correct if
  the answer differs. Overrides the *stall* failure mode of
  "discuss before committing", not the discussion itself.
- **Explicit commit / push approval per scope.** Don't auto-commit
  beyond what was asked.
- **No AI-attribution trailer** on commits (also codified in
  `CLAUDE.md §6`; restated here for discoverability).
- **Explanations offered as concept notes.** When the user asks for
  a domain or tool explanation, answer inline and offer to preserve
  it as a `C-NNN` note in `vault/concepts/`. If the user explicitly
  says "save as concept" (or similar), commit without asking.
  Concept type defined in META.md §11.
- **Proactive concept capture (hard, 2026-05-19).** Whenever a *new*
  concept (domain or tool) materially appears in a node/dialogue,
  write its non-expert `C-NNN` primer in the same commit — don't
  wait to be asked. Codified in `META.md §11`; rationale +
  publication framing in
  [[methodology/M-001-proactive-concept-capture|M-001]].

## Strategic preferences (this campaign)

- **Rank-3 on each regular instance is the primary goal** (user
  directive 2026-05-18; supersedes the earlier "top-3 aggregate"
  framing — see GOALS.md §1). Ch3 tie-breaker deferred. Methodology
  validation remains a *parallel* deliverable.
- **Agent never writes to the internet.** No submissions, no
  forum / GitHub / Discord posts, no PRs / issues, no email. The
  agent produces JSON artefacts under `solutions/upload/` and the
  user uploads them manually via the Optimise web UI. Read-only
  HTTP (incl. GraphQL queries to `api.optimize.esa.int`) is fine.

## How to update this file

Append facts, don't delete (unless wrong). When a soft preference
becomes a hard rule, copy it to `CLAUDE.md`/`META.md` and note here
with a "(codified in X)" pointer. The point of this file is that it
never goes stale — session-to-session continuity depends on it.
