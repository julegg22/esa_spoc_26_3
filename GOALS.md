# GOALS.md — campaign-specific objectives

`META.md` specifies *how* we learn and record (the scientific
methodology). This file specifies *what* we are trying to achieve in
this particular campaign and the goal-domain conventions that follow.
Together with `CLAUDE.md` (how to code) and `META.md` (how to learn),
this is the third leg: **what to learn for**.

If you re-use the methodology in `META.md` for another campaign,
fork this file. `META.md` should remain unchanged.

## 1. Root goal

**Match rank-1 performance on every SpOC4 instance. Open-ended — no
deadline.**

User directive 2026-07-01 (post-challenge): the SpOC4 submission
deadline has passed; our final standing was **7th overall**. The
challenge is now a **research investigation** with no time limit. The
new root goal is to reach **rank-1-equivalent objective values on all
six instances** — close the gap to the best-known (rank-1) solution on
each, one instance at a time. Points/rank weighting (kept in §2) is now
only a *prioritization* heuristic for which gap to attack first, not a
deadline-bound score to bank.

**Why we were walled, and the method that beats it (intelligence from
the rank-1 team, HRI, 2026-07-01):** rank-1 did **not** use risky
beyond-state-of-the-art physics or novelty research; and although they
had 10–20× our compute, **compute was not the cause** of their edge.
Their edge was **structure discovery + structure-specialized
metaheuristics**:
- Ch2 **medium**: they found *super-narrow time-window basins* and
  specially optimized against them.
- Ch2 **large**: they found *cluster substructures*, optimized each
  individually, then **coupled** them within a larger system.

**Methodological goal (the meta-target):** understand *how to proceed to
the top rank* as a repeatable method. Working thesis: **search the
structure, not the encoding** — first discover the problem's native
structure (narrow phasing windows; node clusters) and its scale, match
the representation and evaluator resolution to that scale, decompose
along the structure, optimize each part with a specialized local method,
and add an explicit coupling layer; only then run the metaheuristic — on
the structured representation. Every past "wall" is re-read as *generic
search exhausted on a mismatched encoding*, not the problem's optimum.
Explore-and-exploit **better metaheuristics** is the operative lever.
This refines [[architecture-change-on-large-gaps]],
[[foundation-then-search-methodology]], and
[[basin-overarching-search]] with rank-1 ground truth.

Submissions remain user-only (§4).

The current rank-3 cutoff per instance (live leaderboard, read-only
GraphQL `https://api.optimize.esa.int/graphql/`; snapshot
[[observations/O-002-leaderboard-2026-05-18|O-002]]) is the binding
falsifiability anchor for every active hypothesis.
`tools/fetch_leaderboards.py` is a stub — fetching is currently done
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
