# GOALS.md — campaign-specific objectives

`META.md` specifies *how* we learn and record (the scientific
methodology). This file specifies *what* we are trying to achieve in
this particular campaign and the goal-domain conventions that follow.
Together with `CLAUDE.md` (how to code) and `META.md` (how to learn),
this is the third leg: **what to learn for**.

If you re-use the methodology in `META.md` for another campaign,
fork this file. `META.md` should remain unchanged.

## 1. Root goal

**Reach rank-3 (top-3) standing on every *regular* SpOC4 instance by
2026-06-30 AoE.**

User directive 2026-05-18: the target is competitive (rank-3-or-better)
standing on **each** of the six regular instances — Ch1 `matching-i`,
`matching-ii`, `trajectory-matching` and Ch2 `small`, `medium`,
`large`. Ch3 (`tie-breaker`) is **deferred** — addressed only after
the regular instances are secured, and primarily because the global
tie-break uses it. This supersedes the prior "top-3 *aggregate*"
framing (kept in git history); a per-instance rank-3 portfolio
dominates the aggregate anyway since each scoring instance contributes.
Late submissions (after 2026-06-30 AoE) don't count.

The current rank-3 cutoff per instance (live leaderboard, read-only
GraphQL `https://api.optimize.esa.int/graphql/`; snapshot
[[observations/O-002-leaderboard-2026-05-18|O-002]]) is the binding
falsifiability anchor for every active hypothesis.
`scripts/fetch_leaderboards.py` is a stub — fetching is currently done
via direct read-only GraphQL queries. Internal proxies are
*diagnostic*, not closure criteria.

## 2. Sub-goals — challenges

SpOC4 has three challenges; each has graded sub-instances with
escalating point weights.

Real instance ids (GraphQL-confirmed, [[observations/O-001-spoc4-problem-grounding|O-001]]):

- **Challenge 1 — Luna Tomato Logistics (mandatory)** #ch1
  - `matching-i` — A_1, ×1 (weighted 3-D matching ILP, dim 25000)
  - `matching-ii` — A_1, ×1 (same, dim 92103)
  - `trajectory-matching` — A_3, ×(4/3)² (BCP trajectories, dim 8400)
- **Challenge 2 — Keplerian Tomato TSP (mandatory)** #ch2
  - `small` — A_1, ×1 (time-dependent ATSP, N=49)
  - `medium` — A_2, ×4/3 (N=181)
  - `large` — A_3, ×(4/3)² (N=1051)
- **Challenge 3 — Luna Tomato Advertising (tie-breaker, deferred)** #ch3
  - `tie-breaker` — A_0

Top 10 per instance score points. Challenge 3 breaks global ties.
See `vault/observations/` for grounding; `vault/index.md` is the
canonical campaign root with current best scores.

## 3. Strategic / parallel goal

The campaign's secondary deliverable is a **methodology-validation
publication**: documenting the Human + Claude Code research-loop
patterns, dialogue patterns, and decision discipline that make the
process work. See `vault/user.md` (*Strategic preferences*) for the
user-side rationale; `vault/methodology/` (M-NNN nodes) is the
primary raw material. This is why the M-NNN track exists alongside
T / L / C in `META.md §11`.

**Reframing on 2026-05-06**: methodology validation is now a
*parallel* deliverable alongside the leaderboard root goal, not an
override. The original M-001 framing
(`[[methodology/M-001-methodology-validation-is-primary]]`) elevated
methodology-purity over leaderboard points as the campaign's primary
metric; the directive shift redirects the *primary* metric to
aggregate leaderboard standing while keeping the publication track
running concurrently. Methodology evidence accumulates as a side
product of the leaderboard push; on tradeoffs, top-3 aggregate
takes precedence.

## 4. Goal-specific invariants

Layered on top of the goal-agnostic invariants in `META.md §2`:

> [!important] Agent never writes to the internet
> The agent never submits, posts, comments, opens issues / PRs, or
> sends any HTTP request that mutates remote state. Read-only HTTP
> (incl. GraphQL `query` operations against
> `https://api.optimize.esa.int/graphql/`) is fine. **All submissions
> are user-only**, performed manually via the Optimise web UI. The
> "establish-baseline-early" invariant of `META.md §2` is reinterpreted
> as *produce a valid JSON artefact in `solutions/upload/<problem>.json`
> early*; the user uploads it on their own cadence.

> [!important] Leaderboard score is the only truth
> Every active H's `falsifiable_prediction` is calibrated against an
> observed leaderboard score or rank threshold from the most recent
> snapshot in `vault/observations/O-NNN-leaderboard-YYYY-MM-DD.md`.
> Closure of any H to `corroborated`/`refuted` cites the live
> leaderboard at closure time. Predictions are written in the form
> "score ≥ X (= rank-N cutoff at YYYY-MM-DD)".

## 5. Spirit vs letter of SpOC rules

The SpOC4 README encourages metaheuristic algorithms. Scoring is on
objective value only — any tool producing valid JSON is fair game.
Pragmatic stance:

- Use whatever gets the best objective. **HiGHS MILP on Ch1 Beginner
  is allowed** and is the rational first move even though it's not a
  metaheuristic.
- If a non-metaheuristic crushes a problem, submit that FIRST for
  points. Optionally submit a best-effort metaheuristic under a
  separate submission name to contribute to the challenge's stated
  purpose AND provide a reference baseline for our own
  metaheuristic work.
- If multiple top teams use the same solver, ties cluster at the
  optimum and tie-breaking rules dominate. Optimise tie-breaking is
  undocumented — see `[[submission-pipeline]]` for the open
  question; worth asking on the SpOC4 Discussions forum before a
  race to the optimum forms.

## 6. Goal-domain tag vocabulary

These extend the generic vocabulary in `META.md §9`. Use sparingly
and log new tags here when introduced.

- challenge: `#ch1` `#ch2` `#ch3`
- difficulty: `#beginner` `#advanced` `#easy` `#medium` `#hard`
- domain (problem-side, primarily for concepts): `#astrodynamics`
  `#lambert` `#cr3bp` `#bcp` `#optimization` `#ilp` `#milp`
  `#metaheuristic` `#numerics`

## 7. Goal-specific frontmatter interpretation

The frontmatter schemas in `META.md §4` use abstract units (e.g.,
`expected_points`). For this campaign:

- `expected_points` — units = SpOC4 leaderboard points (1 point =
  1 leaderboard point at scoreboard rank-mass weighting).
- `realized_points_total` (in `vault/index.md`) — sum of
  leaderboard points actually scored.

For another campaign, the unit is whatever the root goal measures.

## 8. Resources / pointers

- Campaign root: `vault/index.md`
- Frontier: `vault/open-paths.md`
- User profile: `vault/user.md`
- Upstream starter kit (gitignored): `reference/SpOC4/`
  (re-clone with `git clone --depth 1 https://github.com/esa/SpOC4.git reference/SpOC4`)
- Submission entrypoint: <https://optimize.esa.int/submit>
- Forum: <https://github.com/esa/SpOC4/discussions>
