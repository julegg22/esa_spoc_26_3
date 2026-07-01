# META.md — research process

Extends `CLAUDE.md`. `CLAUDE.md` says *how to code*; this says *how to
learn and record*. The campaign-specific objective lives in
`GOALS.md` (*what to learn for*); this file is goal-agnostic
methodology. All `CLAUDE.md` rules remain in force (think before
coding, simplicity first, surgical changes, goal-driven execution).
This file adds the scientific discipline on top.

## 1. Frame: research as tree search

One goal at the root of everything — defined in `GOALS.md`. The
campaign explores a tree whose nodes carry scientific meaning,
descending from that root. Mapping the seven steps of the scientific
method to the tree:

| scientific step                          | in the tree                                    | file type        |
| ---------------------------------------- | ---------------------------------------------- | ---------------- |
| 1. observation / grounding               | reusable grounding, shared across branches     | `observations/`  |
| 2. questioning (isolation, precision)    | branch origin or re-origin                     | `questions/`     |
| 3. hypothesis generation                 | inner node = branching point                   | `hypotheses/`    |
| 4. testing (controlled experiment)       | leaf under a hypothesis                        | `experiments/`   |
| 5a. analysis — per experiment            | verdict + short write-up at the leaf           | in E             |
| 5b. analysis — per hypothesis (distilled)| citable takeaway(s) produced at H close        | `takeaways/`     |
| 6. modification                          | rationale on the **child** H, citing the parent's takeaway | `modification_rationale` field |
| 7. documentation                         | continuous — YAML frontmatter + body           | every file       |

**Growth** adds children. **Branching** under one question is multiple
competing hypotheses. **Backtracking** marks a branch pruned and returns
to the next best open node on the frontier. Cross-links make the vault
a DAG in practice, but each node has exactly one `parent` pointer — that
defines the canonical tree.

## 2. Invariants

> [!important] Invariants — non-negotiable
> Violate these and the log stops being useful.
>
> - **Falsifiability before testing.** A hypothesis states a concrete
>   prediction (metric + threshold) before its first experiment runs.
> - **Reproducibility by construction.** Every experiment captures code
>   path, commit SHA, inputs, seed, env — **captured at RUN time**, not
>   reconstructed: each script calls `_prov.stamp(__file__, seed=…)`, which
>   writes `[PROV] commit=<sha>[+DIRTY]` into the run log; that SHA fills
>   `E.commit`. A `+DIRTY` stamp means the result maps to no commit and is
>   not replayable — so **any run whose output is banked runs on a clean
>   tree** (§4, §6). Replayable a year from now.
> - **Written analysis at close.** Hypotheses never move to
>   `corroborated`/`refuted` without an analysis block citing the E nodes.
> - **Modification rationale on every continuation.** A child hypothesis
>   opened after its parent closes must carry `modification_rationale`
>   stating what changed and why. No orphan restarts.
> - **Logged resources, not remembered.** Timestamps stamped by the tool,
>   not reconstructed; wall-clock and peak memory recorded per experiment.
> - **Takeaway on close.** Every hypothesis reaching `corroborated`,
>   `refuted`, or `analyzed` produces ≥ 1 `T-NNN` takeaway. Modification
>   rationales on descendants cite takeaways by link, not H-body prose.
> - **Lesson on surprise.** When a tool, environment, or code behaviour
>   surprises us in a way future-us would want to know, write an
>   `L-NNN` lesson before moving on. Cost ≈ 2 minutes; skipping it
>   guarantees re-discovery.
> - **Solver-assumption audit before "hard" verdict.** Before declaring
>   a benchmark requires research-grade techniques or fundamentally
>   harder methods, perform a 3-step audit: (a) compute the theoretical
>   bound for the metric and compare to current achievement — if the
>   ratio is >100×, suspect solver bug, not problem difficulty; (b) for
>   each implicit assumption in your solver (e.g. circular target,
>   linear approximation, fixed parameter), verify against the actual
>   data distribution; (c) test the solver on ≥10 inputs spanning the
>   data's diversity, not just the easiest cases. Skipping this audit
>   cost 5 days on Ch1 trajectory in May 2026 — see `LESSONS-LEARNED.md`.
> - **Commit on learn.** Observations and lessons are written *when
>   their content becomes known*, not batched at session end. The
>   vault's value depends on timestamps matching the moment a fact
>   surfaced.
> - **Plot on quantitative result.** Every experiment producing
>   quantitative metrics embeds ≥ 1 plot in its Results section. Every
>   takeaway includes ≥ 1 headline plot in its Summary. Prose describes;
>   plots convince.
> - **Single frontier.** `vault/open-paths.md` is the only list of "what
>   could we do next." Ideas living in chat do not exist.
> - **One active branch per compute stream.** A compute stream is a
>   sequential execution context (human attention, a cluster node, a
>   parallel job slot). Multiple streams can hold sibling H open
>   simultaneously; within one stream, only one. Cross-link siblings
>   with `concurrent_with`.
> - **Establish baseline early on every measurable instance.** When
>   work begins on a scored sub-instance, a trivial-but-valid baseline
>   result is produced and recorded promptly. The first result is
>   never optimal — but its presence is insurance and a calibration
>   anchor. Goal-specific timing and submission rules live in
>   `GOALS.md`.
> - **5× wall-time watchdog on every long-running compute task.**
>   Declare an `expected_wall_s` budget when launching a sim / sweep
>   / optimisation. Arm a watchdog that fires at 5× expected and
>   triggers a mid-run analysis (process alive? observable progress?
>   cost-model refuted? partial output salvageable?). Decide
>   *continue / kill-and-fix / kill-and-abandon* — never silent
>   waiting, never silent killing. Calibrated for compute wall-time;
>   the 2× human-effort threshold in §6 still applies separately to
>   `effort_person_hours`. Procedure in
>   [[methodology/M-019-compute-time-budget-watchdog|M-019]].
> - **Idle cores are bugs.** Before ending an agent turn during a
>   compute-bound campaign, the agent verifies at least one
>   productive compute stream is running, or explicitly justifies
>   why none is. Transient infra obstacles (classifier unavailable,
>   package install in flight) get retried or routed around — they
>   never silently end the turn while cores remain idle. Procedure
>   in [[methodology/M-020-idle-cores-are-bugs|M-020]].
> - **Family-breadth before depth.** The frontier always has
>   priced hypotheses from **≥ 2 approach families**
>   ([[methodology/M-003-approach-family-inventory|M-003]]). When
>   3+ methods *in the same family* converge at the same value,
>   fire the orthogonal-pivot watchdog
>   ([[methodology/M-004-convergence-watchdog-across-families|M-004]]):
>   list 2 untried families, run cheap smoke probes, then decide
>   whether to commit. Local-search refinement past convergence
>   without an orthogonal-family probe attempt is an explicit
>   violation.
> - **Ladder-breadth before depth.** The frontier always carries
>   ≥ 1 live hypothesis at a **Tier-A/B rung** of the abstraction
>   ladder (L1 objective / L2 model / L3 structure / L4 encoding /
>   L5 evaluator) — not only Tier-C (L6 solver / L7 operators / L8
>   params). The §5 ROI formula systematically under-prices
>   high-rung hypotheses (high effort, uncertain payoff) — the R5
>   cost-asymmetry bias encoded *in selection itself*; this
>   invariant counters it. Grinding only Tier-C past a plateau or
>   convergence is an explicit violation → fire the ladder sweep
>   (`doc_methodology.md §1–2`) before the next selection.
> - **Toolchain audit at bootstrap.** Before any code, inventory
>   the env (`pip list`), read every helper file in the starter
>   kit, and inspect any submission / reference URLs. Unusual
>   libraries are intel about the intended approach. Procedure in
>   [[lessons/L-005-toolchain-audit-at-task-bootstrap|L-005]].
>   External intel (winners' toolchains, problem-class libraries)
>   completes the picture per
>   [[methodology/M-005-external-intel-survey|M-005]].

## 3. Vault layout

```
vault/
├── index.md                # root: goal, current best, pointers
├── open-paths.md           # frontier, prioritized
├── assumptions.md          # load-bearing assumption register — the assumption-DAG for multi-level invalidation (§15 T6); M-general-assumption-provenance-and-invalidation (§14 tier-1)
├── abbreviations.md        # glossary of acronyms with primary-node links — update whenever a new acronym is introduced (§14 tier-1)
├── user.md                 # user profile + soft preferences — portable replacement for local Claude memory (§14)
├── _templates/             # YAML + body templates (copy → fill)
│   ├── hypothesis.md
│   ├── experiment.md
│   ├── observation.md
│   ├── question.md
│   ├── takeaway.md
│   ├── lesson.md
│   ├── concept.md
│   ├── methodology.md
│   ├── session.md
│   └── review.md
├── observations/           # O-NNN-slug.md
├── questions/              # Q-NNN-slug.md
├── hypotheses/             # H-NNN-slug.md
├── experiments/            # E-NNN-slug.md  (+ optional E-NNN/ folder for logs/plots)
├── takeaways/              # T-NNN-slug.md — distilled problem-side learnings, ≥1 per closed H (+ optional T-NNN/plots/)
├── lessons/                # L-NNN-slug.md — atomic engineering lessons (gotchas, ADRs, tips, workarounds)
├── concepts/               # C-NNN-slug.md — prior-knowledge primers (domain + tool)
├── methodology/            # M-NNN-slug.md — methodology insights (research-process learnings, publication-bound)
├── sessions/               # S-YYYY-MM-DD-slug.md — episodic session narrative; consolidated into weekly reviews (§14)
├── package/                # living docs about our software (env, pipelines, modules) — not ID'd
└── reviews/                # weekly + milestone retrospectives (consolidate sessions)
```

IDs: zero-padded 3-digit integer, monotonically increasing per type
(`H-042`, `E-017`). Filenames: `<ID>-<short-slug>.md` so Obsidian
autocomplete ranks them well. The vault is tracked in git — **the git
history is the research log**. Large run artefacts live in ignored
`E-NNN/` subfolders; the folder path is recorded in the experiment's
frontmatter so nothing is lost conceptually.

## 4. Frontmatter schemas (canonical forms in `_templates/`)

**hypothesis** — minimum required fields:

- identity: `id`, `type: hypothesis`, `status`, `tags`
- links: `parent` (H or Q), `question`, `children_experiments`,
  `children_hypotheses`
- chronology: `created`, `tested_start`, `tested_end`,
  `duration_testing`
- accounting: `effort_person_hours`, `expected_points`,
  `estimated_effort_h`, `priority`, `mode` ∈ {`full`, `lite`}
- content: `claim`, `falsifiable_prediction`, `modification_rationale`
  (nullable only when rooted directly on a question)
- ladder: `level` — the abstraction-ladder rung this H concerns (L1–L8;
  `doc_methodology.md §1`). Makes the frontier organizable by level and the §2
  *Ladder-breadth* invariant checkable. `assumes` — Assumption-Register IDs
  (`vault/assumptions.md`) this H rests on; effective validity = `assumes` ∪ the
  branch's inherited set (up `parent`).
- `falsifiable_prediction` may be **level-appropriate**: a metric+threshold
  (Tier-C), OR a representability / expressiveness / structure-existence /
  evaluator-fidelity claim (Tier-A/B) — e.g. *"the window-indexed encoding can
  represent a tour ≤ Q that the uniform-grid encoding cannot."* A high-rung H is
  not exempt from falsifiability; its prediction is just not always a score.
- supersession (nullable): `invalidated_by` (`[[L-NNN]]`),
  `superseded_by` (`[[H-NNN]]`), `invalidated_at`

`status` ∈ {`draft`, `open`, `testing`, `analyzed`, `corroborated`,
`refuted`, `abandoned`, `invalidated`}.

The `invalidated` state is **terminal-overlay**: it is set
retroactively by the cascade procedure in §15 when a code-side bug
or upstream invalidation removes the H's premise. The original
status (e.g., `corroborated`) is preserved in git history; only the
current YAML moves to `invalidated`. Mandatory pairing with
`invalidated_by` (the `L-NNN` lesson documenting the bug) and,
when applicable, `superseded_by` (the new H that re-frames on the
corrected substrate).

**experiment** — minimum required fields:

- identity: `id`, `type: experiment`, `status`, `tags`
- link: `hypothesis`
- chronology: `created`, `ran_start`, `ran_end`, `duration_runtime`
- reproducibility: `code`, `commit`, `inputs`, `outputs`, `plots`,
  `seed`, `env`. **Capture provenance at RUN time, not later:** every
  experiment script calls `_prov.stamp(__file__, seed=...)` at the top of
  `main()`, which prints a `[PROV] commit=<sha>[+DIRTY] script=… sha1=…`
  line into the run log. Copy that `commit` SHA into the `commit:` field
  when writing the E node — this is how a result is bound to a code version
  (git history of the *note's* commit is not the code the run *used*, since
  we routinely edit→run→commit). **Clean-tree-before-bank:** any run whose
  output gets banked/committed as a result must run on a *clean* tree — a
  `+DIRTY` stamp means the result maps to no SHA and is not reproducible;
  commit the code first. (Historical E nodes backfill `commit` only on touch.)
- provenance: `code_dependencies` — list of repo-relative source
  paths (or commit-pinned artefacts) the run depended on. Each
  entry may be a bare path string, or a mapping
  `{path: ..., verified_by: [[L-NNN]] | [[E-NNN-smoke]]}` when a
  grounding lesson / smoke test exists. Required for new E from
  §15 adoption forward; backfilled only when an existing E is
  touched.
- assumption provenance: `assumes` — list of Assumption-Register IDs
  (`vault/assumptions.md`) this conclusion is load-bearing on, at ANY
  ladder level (not just code/L2). Effective validity = `assumes` ∪ the
  branch's inherited set (walk up `parent`/`hypothesis`). Required on
  **load-bearing** conclusions (banks, floors, "walled/exhausted"
  verdicts); optional on exploratory probes. Enables the §15 T6 cascade.
- wall provenance: `wall_level` — for any "walled/exhausted/closed"
  verdict, the ladder rung it is exhausted at (L1–L8). A verdict without
  `wall_level` is inadmissible (ladder-audit R1).
- resources: `compute: {cpu_seconds, peak_memory_mb, cores}`,
  `effort_person_hours`
- result: `metrics` (free-form dict), `verdict` ∈ {`supports`,
  `refutes`, `inconclusive`}
- supersession (nullable): `invalidation` block with fields
  `invalidated_by` (`[[L-NNN]]` or Assumption-Register ID),
  `superseded_by` (`[[E-NNN-redo]]`), `invalidated_at`, `level`
  (ladder rung Lx of the failed assumption), `notes`. **The original
  `verdict` is not rewritten** — it was correct given its assumptions;
  the overlay tells future readers the conclusion is now conditional /
  no longer holds, and at which level.

**observation** — `source` is mandatory (file, URL, or `E-NNN`).
Observations are append-only; corrections arrive as new observations
that link back.

**question** — names the ambiguity it isolates. Must be answerable or at
least decidable.

**takeaway** — minimum required fields:

- identity: `id`, `type: takeaway`,
  `status` (`draft` | `final` | `superseded` | `invalidated`), `tags`
- link: `hypothesis` (parent H, required)
- chronology: `created`
- content: `supports_verdict` ∈ {`corroborated`, `refuted`, `inconclusive`},
  `confidence` ∈ {`low`, `medium`, `high`},
  `generalizability` ∈ {`single-H`, `subgoal-wide`, `cross-subgoal`}
    (legacy `ch-wide`/`cross-challenge` are equivalent — the SpOC4
    sub-goal is the *challenge*; see `GOALS.md`),
  `goal_contribution` (1-line summary; surfaces in dashboards)
- supersession (nullable): `superseded_by` (`[[T-NNN]]`),
  `invalidated_by` (`[[L-NNN]]`), `invalidated_at`
- accounting: `effort_person_hours`

The `superseded` state is set when a corrected E re-run yields a
T-NNN that replaces this one (the conclusion changed). The
`invalidated` state is set when the parent H itself was invalidated
and no replacement T has been written yet. Both are set by the
cascade procedure (§15), not by hand-edit.

The body always includes: a **Summary with ≥ 1 headline plot**,
evidence links, implications, a **Position vs goal** block
(contribution, where we stand, next move), and caveats. A takeaway
is the **citable artefact** — descendants link `[[T-NNN]]`, not
H-body prose.

**Register bridge.** When a takeaway *establishes or refutes a load-bearing
assumption* (a premise other conclusions rest on), create or flip its row in
`vault/assumptions.md` and — on a flip — run the §15 **T6** cascade. Tag the T
with the ladder `level` it concerns. This is how problem-side learning enters
the assumption-dependency DAG instead of staying siloed in one branch.

**lesson** — minimum required fields:

- identity: `id`, `type: lesson`, `status` (`draft` | `confirmed` | `superseded`),
  `tags`
- classification: `kind` ∈ {`gotcha`, `decision`, `tip`, `workaround`},
  `scope` (module/tool/workflow), `severity` ∈ {`blocker`, `warning`, `tip`},
  `confidence` ∈ {`low`, `medium`, `high`}
- chronology: `created`
- lineage: `source` (E/H/commit/URL), `supersedes`, `superseded_by`
- accounting: `effort_person_hours`

Lessons capture **engineering** insight (about our means — tools, code,
environment) as opposed to **scientific** insight (about the problem,
which lives in takeaways). See §11 for when to write which.

**concept** — minimum required fields:

- identity: `id`, `type: concept`, `status` (`draft` | `confirmed` |
  `superseded`), `tags`
- classification: `scope` (domain or tool, e.g., `astrodynamics/two-body`,
  `optimization/milp`), `confidence` ∈ {`low`, `medium`, `high`}
  (how well-established in literature / our understanding)
- chronology: `created`
- lineage: `sources` (URLs, paper / book citations), `supersedes`,
  `superseded_by`
- cross-links: `related` (list of `[[H-NNN]]` / `[[E-NNN]]` /
  `[[T-NNN]]` / `[[L-NNN]]` / `[[C-NNN]]`)

Body has five sections: **Definition**, **Why it matters here**
(ties the concept to the campaign), **Mechanics** (equations /
algorithms / properties), **In practice** (code invocation, common
gotchas), **References**. Concept notes capture **prior knowledge**
we depend on but didn't discover — see §11.

**methodology** — minimum required fields:

- identity: `id`, `type: methodology`, `status` (`draft` |
  `confirmed` | `superseded`), `tags`
- classification: `kind` ∈ {`dialogue-pattern`, `vault-pattern`,
  `process-pattern`, `decision-pattern`, `loop-instance`,
  `reflection`}, `scope` (which part of the research process —
  e.g., `H-bootstrapping`, `compute-streams`, `session-resume`),
  `severity` ∈ {`blocker`, `warning`, `tip`},
  `confidence` ∈ {`low`, `medium`, `high`},
  `generalizability` ∈ {`single-instance`, `campaign-wide`,
  `cross-campaign`, `universal`}
- chronology: `created`
- lineage: `source` (session/dialogue/commit/H reference where the
  pattern emerged), `supersedes`, `superseded_by`
- accounting: `effort_person_hours`

Body has four sections: **What** (the insight), **Why it matters**
(publication-bound rationale), **Evidence** (sessions / commits /
nodes), **Implication** (rule it sets, change to future practice).
Methodology nodes capture **research-process learning** — what we
learn about *how we work together*, distinct from problem-side
(T) / tooling-side (L) / prior-knowledge (C). They are the
primary raw material for the campaign's methodology-validation
publication. See §11.

**session** — minimum required fields:

- identity: `id` (`S-YYYY-MM-DD`), `type: session`, `tags`
- chronology: `date`, `created`, `duration_hours`
- participants: `participants`, `claude_model` (if AI-assisted)
- links: `commits` (git SHAs), `created_nodes` (list of `[[...]]`)

Body has five sections: Scope, Key decisions, Soft knowledge,
Artefacts touched, Open threads. Sessions are the episodic memory
layer (tier 2 in §14); they're consolidated into the weekly review
(tier 3).

**user-profile** (`vault/user.md`, single file). Living doc — no ID,
no append-only rule; edit in place. Captures user role, background,
working constraints, soft preferences. Hard rules graduate from here
into `CLAUDE.md` or `META.md`. See §14.

## 5. Selection policy (which open node next)

From `vault/open-paths.md`, pick the hypothesis maximizing

```
ROI = expected_points / max(estimated_effort_h, 0.25)
```

Tie-breakers in order:

1. **Time-to-first-signal.** Prefer experiments producing any
   goal-relevant data point quickly over deep-but-slow bets.
2. **Diversity.** Don't stack all effort on one sub-goal when similar
   ROI exists elsewhere.
3. **Unblocking.** Prefer hypotheses whose outcome prunes many siblings.

**Ladder gate (runs BEFORE ROI ranking).** ROI alone under-prices high-rung
hypotheses (see the §2 *Ladder-breadth* invariant), so guard selection with two
rules: (a) if a **plateau or convergence** trigger is active
(`doc_methodology.md §7.1 #3/#8`), run the **abstraction-ladder sweep first** and
reprioritize — the sweep is a mandatory diagnostic gate, not an ROI competitor;
(b) never let the frontier collapse to Tier-C-only — if it has, promote or open a
Tier-A/B hypothesis before picking. The wall is fixed at the *highest* mismatched
rung, which ROI would never surface on its own.

Reprice the frontier after every experiment. Record dated re-pricings
in `open-paths.md` — the frontier has history.

*Future refinement (not v1):* UCT-style scoring once we have enough
closed H to form priors on `realized/expected` ratios.

## 6. Inner loop (automatic, recursive)

```
while deadline not reached and frontier not empty:
    H  ← argmax_ROI(open-paths)
    H.status ← "testing"; stamp H.tested_start
    for each designed experiment E of H:
        commit code (CLEAN tree before a banking run)   → note the SHA
        run  → _prov.stamp(__file__) emits [PROV] commit=<sha>[+DIRTY] to the log;
               copy that SHA to E.commit; capture metrics, resources, outputs
        write verdict + 2–5 lines of analysis in E body
        embed ≥ 1 plot of quantitative results in E body
    aggregate into H's Analysis section (terse; links to all E)
    write ≥ 1 T-NNN takeaway distilling what was learned,
      with headline plot(s) and a position-vs-goal block
    H.status ← corroborated | refuted | analyzed
    stamp H.tested_end, H.duration_testing
    propose child hypotheses; each carries modification_rationale
      that cites the relevant T-NNN by link
    append children to open-paths with ROI scores
    if branch dead → mark pruned; backtrack to nearest open ancestor
```

**Escalate to the human** when: (a) realized effort >2× estimate on one
H, (b) a decision needs judgement not in the vault, (c) about to take
an externally-visible action with goal-impact (e.g., submission, public
release — see `GOALS.md` for goal-specific examples), (d) choosing
between approaches of comparable ROI but very different risk profiles.

### Bootstrapping the frontier

When the frontier is empty — at campaign start, after a retrospective,
or after a large branch is pruned — candidate hypotheses are
**discussed with the human first**, then committed as `H-NNN` files
once agreed. Observations and lessons underlying the discussion are
committed immediately (per §2 *Commit on learn*) so the conversation
leaves durable grounding regardless of which hypotheses are approved.

### Parallelism as experiment structure — probe then campaign

When compute parallelism is available, the loop adapts rather than
breaks:

- **Probe → campaign.** Run a small set of parallel experiments under
  one H to map the landscape (algorithm choice, hyperparameter
  ranges, seed variance). Based on probe results, commit to a focused
  large-scale parallel campaign with chosen settings. The
  organizational overhead of the large run is paid *once*, after the
  probe has de-risked it.
- **Sweeps as E clusters.** A parameter sweep (e.g., DE with 100
  seeds) is a single experiment cluster: one E file describing the
  sweep, one output folder holding per-seed metrics, one set of
  aggregated plots. Individual seeds are sub-runs, not separate E.
- **Island models.** pygmo `archipelago` over 4–8 algorithms on the
  same problem is one E with the topology recorded in
  `metrics.island_topology`.

Don't scale a campaign-level parallel run without a probe first. The
probe E is what justifies the campaign E's compute budget, and its
results appear in the campaign E's body as the rationale for the
parameter choices.

### Lite mode

A hypothesis may set `mode: lite` at creation if **all three** hold:

- `expected_points ≤ 2`
- `generalizability == single-H` (the learning won't travel)
- approach is off-the-shelf (no novel algorithm; validated tooling)

Lite closure skips: the `T-NNN` file, the headline plot, the
position-vs-goal block. The H body's Analysis section absorbs the
learning. `status` still moves to `corroborated`/`refuted`/`analyzed`
normally.

Default is `mode: full`. If a lite H surprises us on outcome, promote
to full retroactively (write the T and plots) — the flexibility is
the whole point.

## 7. Modification discipline

When a hypothesis closes, any continuation must include
`modification_rationale` with:

- 1 line: what the prior experiment showed
- 1 line: why the prior hypothesis was insufficient
- 2–3 lines: what this hypothesis changes, and why that change narrows
  the gap to the root goal — **cite the parent's `[[T-NNN]]` by link,
  not H-body prose**
- 1 line: the **ladder level of the refutation**, and whether it hit the
  **lever** (abstraction — so the child moves to a *different* level / new
  approach) or the **implementation** (tool — so the child is a *minimal
  same-level swap* per R2, and the lever's H stays open). Filing an
  implementation wall (e.g. L6 solver) as lever death is the recurring
  error (`doc_lessons.md` F2).

Until this field is filled, the child stays `status: draft` and does
not enter the frontier.

## 8. Resource logging — gain/cost tradeoff

Three granularities, each answerable without re-running anything:

- **E-level:** `compute` block + `effort_person_hours` in frontmatter.
- **H-level:** rolled-up totals; `expected_points` vs. realized points
  on close.
- **Weekly review** (`reviews/YYYY-Www.md`): aggregated time per
  sub-goal, points gained, ROI per closed H, top wins and regrets.

The test: can we answer *"is this branch paying off?"* from the vault
alone? If no, resource logging is failing.

## 9. Tags and links

Controlled vocabulary (extend sparingly; log new tags in a glossary if
they matter). Generic vocabulary lives here; goal-domain extensions
(goal-domain tags, problem-domain tags) live in `GOALS.md §6`.

- kind: `#infra` `#baseline` `#improvement` `#sota-attempt`
- state: `#blocked` `#dead-end` `#submitted`
- engineering: `#gotcha` `#decision` `#tip` `#workaround` `#env` `#pipeline`
- methodology: `#methodology` `#dialogue` `#vault-pattern`
  `#process` `#decision-rationale` `#H-bootstrapping`
  `#compute-streams` `#framing`

Link rules:

- Every H links up to its `parent` and `question`.
- Every E links to its `hypothesis`.
- Every observation is referenced by ≥ 1 H; orphans flagged at review.
- Cross-branch reuse via `[[...]]` wiki-links, not by copying.

## 10. Reviews

- **Per session:** short narrative log in `sessions/S-YYYY-MM-DD-*.md`
  — decisions, soft knowledge, commits, open threads. The
  dialogue-level memory that would otherwise vanish with the chat.
- **Weekly:** re-score frontier, cleanup orphans, realized-vs-expected
  per closed H, commitments for next week, **plus session
  consolidation** (summarize the week's sessions in one "Sessions
  consolidated" block so they can be archived). File:
  `reviews/YYYY-Www.md`.
- **Per externally-visible result:** compare the realized goal-metric
  delta to `expected_points`. Update estimation priors (gut-feel
  calibration). See `GOALS.md` for the goal-specific instance of this
  trigger (e.g., per leaderboard submission, per benchmark run).
- **Milestone retrospective** after each sub-goal's first
  externally-visible result — seeds observations for the next sub-goal.

## 11. Support tracks — non-frontier knowledge bases

The scientific tree (O/Q/H/E/T) captures what we **learn about the
problem** during the campaign. Four parallel lighter-weight
tracks capture what we **rely on**, what we **learn about our
means**, and what we **learn about how we work together** —
none of which enter the frontier.

- **Engineering practice** — lesson nodes (`L-NNN`) for atomic
  tooling / env / workflow learnings.
- **Domain knowledge** — concept nodes (`C-NNN`) for prior-art
  primers we depend on but didn't discover.
- **Methodology** — methodology nodes (`M-NNN`) for insights about
  the research process itself (publication-bound when the campaign
  has a methodology-validation goal — see `GOALS.md §3` and
  [[user]] *Strategic preferences*).
- **Software reference** — `vault/package/` living docs for our
  software stack.

**Lesson (`L-NNN`).** Atomic, citable engineering insight about our
**means** — our code, environment, and tooling. Written when a
build, run, or experiment reveals something that would generalize
beyond the current hypothesis:

- `kind: gotcha` — a bug or footgun (e.g., *"library function X
  silently returns garbage for edge-case input Y"*)
- `kind: decision` — a lightweight ADR: *"we chose X over Y because Z"*
- `kind: tip` — a useful pattern or performance trick
- `kind: workaround` — a kludge with known scope, to be revisited

Lessons are written immediately when the surprise is fresh (see §2
invariant), and revised with `status: superseded` + a link to the
replacement rather than overwritten when later learning reverses
them.

**Concept (`C-NNN`).** Primer on **prior knowledge** — a domain
concept (a foundational model, theorem, or algorithm class) or a
tool (a solver, library, framework) that we didn't discover but
depend on. Written when:

- An H / E / T / L body references something a future reader (or a
  fresh-context Claude) wouldn't know without background.
- The user asks for an explanation in-session and opts to preserve
  it.
- **A new concept materially appears** in any node body or dialogue
  — write its **non-expert** primer in the *same working unit /
  commit*, proactively, not deferred until asked. This is a
  continuous obligation (the concept-side analogue of *commit-on-
  learn*). Rationale + publication framing:
  [[methodology/M-001-proactive-concept-capture]].

Concept notes are stable substrate — not append-only, but revise by
supersession (`status: superseded` + link) rather than rewrite when
understanding deepens. Proactive capture is the default (per M-001);
no need to ask first.

**Methodology (`M-NNN`).** Atomic, citable insight about our
**research process** — the Human + Claude Code dialogue, the
scientific-loop instances, the vault patterns that work or don't,
decisions about how to spend attention, dialogue patterns that
shape outcomes. Written when:

- A reusable pattern emerges (e.g., *"discuss-before-commit on H
  frontmatter pays off"*, *"single-stream discipline avoids
  cognitive fork"*).
- A meta-level decision is made about how to work (campaign goal
  reframing, decision rules between candidate approaches).
- A reflexive observation surfaces in dialogue that future-us would
  want to know and that is publication-relevant.

Methodology notes are stable substrate — append-only with
supersession-by-link if later experience modifies them. When the
campaign has a methodology-validation goal (see `GOALS.md §3`),
they are the primary raw material for synthesizing the resulting
publication. `vault/methodology/README.md` is the index + proto-paper
themes.

**Package docs (`vault/package/`).** Living, named reference docs
about our software stack — environment setup, submission pipeline,
per-module notes. Not ID'd, not append-only. Grow on demand.
`vault/package/README.md` is the index and status board.

**T vs L vs C vs M — quick rule.**

- **Takeaway** (`T`) — about the **problem**, **learned** through
  our experiments. Cites E nodes. Would change if we swapped
  challenges.
- **Lesson** (`L`) — about our **means**, **learned** through
  builds / runs / commits. Stays true across challenges with the
  same stack.
- **Concept** (`C`) — **prior knowledge** we depend on. Stable
  substrate. Either domain (math, physics) or tool (solver
  internals).
- **Methodology** (`M`) — about **how we work together**, learned
  through the dialogue and process itself. Publication-bound.

Cite freely with `[[L-NNN]]`, `[[T-NNN]]`, `[[C-NNN]]`,
`[[M-NNN]]` in each other's bodies when an insight crosses
dimensions.

## 12. Tooling stance

- Plain markdown + YAML. Readable without any tool; Obsidian optional.
- Obsidian is recommended for graph view and template insertion — open
  `vault/` as a vault (File → Open folder as vault).
- If a dedicated Obsidian skill becomes available in the agent runtime,
  wire it in here (template insertion, graph queries). Not a blocker.
- `src/` carries code; `vault/` carries knowledge. They reference each
  other by path — never duplicate content across them.

## 13. Spirit vs letter of goal rules

When the goal domain has rules (a competition's submission format, a
benchmark's evaluation script, a paper venue's expectations), use
whatever method achieves the best objective the rules actually score
— don't self-restrict to methods the rules' *spirit* prefers if the
*letter* allows others. Goal-specific rule guidance is in
`GOALS.md §5`.

## 14. Portable memory and tiered access

Claude Code's local memory at `~/.claude/projects/<path>/memory/` is
per-path and per-machine; its contents don't travel with a repo.
Two surfaces in the vault replace it for portable context:

- **`vault/user.md`** — single living doc: user role, background,
  persistent soft preferences. Hard rules migrate from here to
  `CLAUDE.md` / `META.md` once codified.
- **`vault/sessions/S-YYYY-MM-DD-*.md`** — one per working session,
  template in `_templates/session.md`. Captures decisions, soft
  knowledge, commits, and open threads — the dialogue-level
  context that vanishes when chat history is lost.
- **`vault/abbreviations.md`** — glossary of every acronym /
  abbreviation that appears in vault nodes, scripts, and commit
  messages, with a one-line meaning and a link to the primary
  explaining node. Maintained alongside the work that introduces
  new terms: when a new acronym appears in a commit, this file is
  updated in the same commit (PR-style discipline).

Together these preserve not just *what* we're working on (vault
nodes) but also *who we are and how we work* (`user.md`), *what
we recently discussed* (latest session), and *the shorthand we
use* (`abbreviations.md`).

### Tiered access

Sessions accumulate; reading all of them on every resume is
wasteful. Memory is tiered so that weekly reviews act as
compactification:

| tier | surface                                                                 | read when                               |
|------|-------------------------------------------------------------------------|-----------------------------------------|
| 1. active    | `CLAUDE.md`, `GOALS.md`, `META.md`, `vault/user.md`, `vault/index.md`, `vault/open-paths.md`, `vault/assumptions.md`, `vault/abbreviations.md` | every resume                            |
| 2. recent    | newest `vault/sessions/S-*.md`                                          | every resume                            |
| 3. rolled-up | newest `vault/reviews/YYYY-Www.md`                                      | only if tier-2 session is > 7 days old  |
| 4. archived  | older sessions                                                          | on demand (`git log`, `git grep`, path) |

Weekly reviews have a **"Sessions consolidated"** block (see the
review template) that summarizes the week's sessions and lists the
cross-session decisions that became locked in. Once a session is
covered by a weekly review, it moves conceptually to tier 4 — still
in the repo, linkable, but no longer on the active read path.

### When to write to each surface

- A **fact** about the user's role or constraints → `user.md`.
- A **soft preference** that should persist across sessions →
  `user.md`.
- A **hard rule** the agent must always follow → `CLAUDE.md` or
  `META.md` (copy over and note the migration in `user.md`).
- A **decision** made in dialogue, with its *why*, that isn't
  captured in an O / Q / H / T / L → the current session file's
  "Key decisions" block.
- A **soft observation** that emerged mid-session but doesn't
  warrant its own O-NNN → session's "Soft knowledge" block.

## 15. Invalidation handling (retroactive bug discovery)

Hypotheses, experiments, and takeaways are **append-only with
overlay supersession**. A bug found late in a code path that
earlier experiments depended on does not delete or rewrite earlier
nodes; it triggers the cascade below. The discipline rests on two
schema additions (§4): `code_dependencies` on E (provenance) and
the `invalidated` / `superseded` states on H / E / T.

See [[methodology/M-010-invalidation-cascade-and-provenance]] for
the rationale.

### When to run the cascade

Trigger on any of (codified in
[[methodology/M-017-cascade-triggers]] as T1-T5):

- **T1**: a new M-NNN with `severity: critical` is committed —
  cascade is mandatory before session close (the M's claim must
  apply retroactively to results that depended on the now-falsified
  pattern).
- **T2**: a new L-NNN with `severity: blocker` AND foundational
  scope (any module multiple downstream E's depend on — the core
  solver, integrator, simulation truth oracle, etc.) — grep
  `code_dependencies` for the affected module and tag every E.
- **T3**: a retrospective addendum to a CLOSED H that surfaces a
  wrong premise in any ancestor — walk back, tag each affected
  ancestor.
- **T4**: status reversal on a foundational H (corroborated →
  refuted, or any revocation of a corroboration that other H's
  cite in `modification_rationale`).
- **T5**: a pattern-finding session whose explicit purpose is to
  identify wrong-tracks. Findings count as critical per T1.
- **T6**: an **Assumption-Register** row (`vault/assumptions.md`) flips
  to `suspect`/`refuted` at ANY ladder level (objective / model /
  structure / encoding / evaluator / solver / operators / params).
  Cascade over the dependents — `git grep "assumes:.*<ID>"` plus branch
  inheritance; overlay `invalidation:{level: Lx}`; triage each into
  **RE-RUN / REFRAME / STILL-HOLDS**. Generalizes the code-dependency
  cascade (T2) to all abstraction levels. Procedure:
  [[methodology/M-general-assumption-provenance-and-invalidation]].
- A bug fix lands in code that an E previously depended on (T2).
- A redo run of a foundational E diverges from the original
  beyond numerical noise.
- An external observation (paper, colleague, post-hoc reasoning)
  contradicts a previously-corroborated H, and the suspect cause
  is on our side of the experimental boundary.

### Session-end checklist (control point)

Before declaring a session closed (whether via session-summary
message, "campaign close", or `/clear`-equivalent), the assistant
**must verify** all triggers from this session were honoured:

**Cascade triggers (per [[methodology/M-017-cascade-triggers]]):**

- [ ] Any new M-NNN with severity: critical? → cascade applied?
- [ ] Any new L-NNN with severity: blocker on foundational code? → grep run, affected E flagged?
- [ ] Any retrospective addendum to a CLOSED H this session? → ancestors reviewed?
- [ ] Any closed H whose status reversed earlier corroboration? → children reviewed?
- [ ] Any pattern-finding outcomes that exposed wrong-tracks? → affected results flagged?

**Step-back triggers (per [[methodology/M-018-stuck-progress-step-back-review]]):**

- [ ] Any branch with 3+ consecutive refutations / loose-only corroborations? → M-018 step-back review run?
- [ ] Any branch with effort > 2× initial estimate without progress? → M-018 review run?
- [ ] Refutations across the branch clustering on a shared axis? → M-018?
- [ ] Active branch open at session-end without decisive verdict? → brief M-018 ideation pass?

> [!important] Stuck ⇒ ultrathink before the next move
> (Hard rule, [[methodology/M-002-stuck-triggers-ultrathink-reframe|M-002]].)
> Any M-018 step-back **must** include an explicit ultrathink pass
> *before* proposing the next branch: (1) change perspective
> (forward↔backward, local↔global, search↔structure); (2) think
> out-of-the-box — *what would the problem designer make hard on
> purpose?*; (3) **audit every load-bearing assumption against
> ground truth** (the official scorer/code, not prose) and state
> each as verified-vs-believed. Re-grounding the problem *model*,
> not just re-pricing the frontier.

**If any answer is yes-but-procedure-not-run, the session does
not close until the procedure is done.** This is the control
point that distinguishes:
- Defensive cascade (M-010, "we have the procedure written down")
  from active cascade (M-017, "the procedure runs when triggered").
- Local refinement (chasing the next H's rationale) from
  global re-grounding (M-018, "are we still on track at all?").

### Cascade procedure

```
1. document
   - write L-NNN (kind: gotcha) describing the bug:
     expected vs actual behaviour, root cause, fix commit SHA,
     and a first-pass impact-scope note.

2. identify affected E set
   - if E.code_dependencies is populated:
       affected = {E : module_X ∈ E.code_dependencies}
   - else (pre-retrofit E):
       affected = {E : commit SHA-search or grep finds X usage}
       backfill code_dependencies on these E while there.

3. re-run
   - for the highest-leverage affected E (the one whose verdict
     anchors the most descendants), write E-NNN-redo: same setup,
     fixed code, same metrics. Capture divergence vs the original.
   - if E-NNN-redo agrees with the original within tolerance:
       the bug did not affect this E's verdict in practice;
       record this as a finding in the L-NNN impact-scope block;
       skip step 4 for this E.

4. tag E (overlay, do not rewrite verdict)
   - on every affected E, add the `invalidation:` block:
       invalidated_by: [[L-NNN]]
       superseded_by:  [[E-NNN-redo]]   # if one was written
       invalidated_at: <ISO-8601>
       notes: <one line on what changed>
   - the original `verdict` field stays untouched.

5. tag H (status overlay)
   - for each H whose closing E set is now invalidated:
     a) if E-NNN-redo gives the SAME H-level outcome →
        H stays in its prior status; add an analysis-section
        line "revalidated by [[E-NNN-redo]] post-[[L-NNN]]".
     b) if E-NNN-redo gives a DIFFERENT outcome →
        H.status ← invalidated
        H.invalidated_by ← [[L-NNN]]
        H.superseded_by  ← [[H-NNN-corrected]]   # if opened
        write a new child H whose modification_rationale cites
        the L-NNN as the trigger and the corrected E as evidence.

6. tag T (status overlay)
   - for each T-NNN whose parent H was invalidated:
     - if a replacement T was written → T.status ← superseded,
       T.superseded_by ← [[T-NNN-corrected]].
     - else → T.status ← invalidated, T.invalidated_by ← [[L-NNN]].

7. walk descendants
   - for each H whose modification_rationale cites an
     invalidated/superseded T, decide:
     a) the cited claim still holds (the corrected T agrees on
        the load-bearing point) → no change; optional note.
     b) the cited claim no longer holds, but the H's own
        evidence still stands → add an analysis note;
        consider downgrading confidence; H status unchanged.
     c) the cited claim was load-bearing and no longer holds →
        H.status ← invalidated; open a child H if the question
        is still alive, abandon the line otherwise.
   - recurse on the descendants of any newly-invalidated node.

8. terminate
   - walk halts when no descendants reference invalidated nodes.
   - the L-NNN impact-scope block is updated with the final list
     of invalidated/superseded nodes.

9. open-paths reprice
   - any newly-opened child H joins vault/open-paths.md with a
     freshly-estimated ROI; previously-banked points from
     invalidated H are removed from realized-points totals.
```

### Things this procedure does not do

- It does not re-run *every* affected E. Step 3 re-runs the
  load-bearing one and uses divergence to scope the rest. Re-running
  all of them is a separate decision based on compute budget.
- It does not actively *find* bugs. Detection is upstream of the
  cascade. A complementary regression-validation pass at weekly
  reviews (§10) is a possible future add-on, deferred until the
  procedure is exercised by a real event.
- It does not rewrite git history. The cascade is append-only:
  prior commits show what we believed at the time; current YAML
  shows the corrected status with pointers to the lesson and redo
  experiment.

## 16. Sibling commitment at closure (multi-child branching)

§1 frames the campaign as a tree where *"branching under one
question is multiple competing hypotheses"* and §6 specifies
*"propose child hypotheses; … append children to open-paths with
ROI scores."* That is **multi-child commitment**: at every closure
the chosen path opens for testing, and the alternatives discussed
at the same fork are committed as priced draft siblings on the
frontier.

[[methodology/M-011-sibling-commitment-at-closure|M-011]] documents
the practice gap that motivated this section: through 2026-04-29
the campaign defaulted to single-child commitment, which made the
tree a chain and the §5 ROI selection a no-op.

### The 0.5 h threshold

At every H closure, before opening the next H:

- **Alternatives ≥ 0.5 h of plausible work** become committed
  siblings — full frontmatter (`claim`, `falsifiable_prediction`,
  `expected_points`, `estimated_effort_h`, `parent`,
  `modification_rationale`) at `status: draft`. The chosen one
  promotes to `status: open`; the rest sit on `open-paths.md`
  *Drafts* until promoted, pruned, or expired.
- **Alternatives < 0.5 h** stay as bullets in the parent H's
  *Next steps* section — explicitly *noted*, not *opened*.
  Cheap variants (parameter sweeps, minor knob changes) belong in
  the body of the chosen sibling, not in separate H files.

The 0.5 h threshold is calibrated to *"deserves a falsifiable
prediction."* Below that bar, an alternative cannot carry a
meaningful threshold-based prediction, so a draft H is overhead
without value.

### Closure procedure

When closing an H:

```
1. Write the closing H's Analysis section (§6) and the T-NNN
   takeaway (full mode) or absorb into Analysis (lite mode).
2. Enumerate every alternative considered at this fork. Sources:
     - chat / dialogue at the fork (current session)
     - the closing H body's "Conditional next" / "Next steps"
     - the parent question's Candidate hypotheses
   For each alternative, estimate effort_h.
3. For each alternative with estimated_effort_h >= 0.5:
     - create vault/hypotheses/H-NNN-slug.md at status: draft
     - frontmatter at minimum: claim (1 sentence),
       falsifiable_prediction (sketch — refine on promotion),
       expected_points, estimated_effort_h, priority,
       parent (= the just-closed H or its Q),
       modification_rationale (cite [[T-NNN]] of the closing H)
     - body: at minimum a "Why this alternative was considered"
       paragraph + the falsifiable_prediction sketch
4. Promote exactly one to status: open per §5 ROI selection.
5. List all alternatives < 0.5 h as bullets in the closing H's
   Next steps section.
6. Append a dated entry to open-paths.md narrative log naming the
   chosen child and listing the new draft siblings with one-line
   summaries.
```

### Backfill

When this section is adopted (or any time the practice was not
followed), backfill prior closures:

- Walk closed H in chronological order.
- For each, identify the alternatives discussed at the fork from
  available sources (in order of preference): closing H body,
  modification_rationale of the chosen child, Q-NNN candidate
  list, session notes, chat history.
- Apply step 3 above to create draft H files; mark them with a
  `backfilled_from:` frontmatter field naming the source
  ("session S-YYYY-MM-DD" or "dialogue 2026-04-29 reconstruction").
- Backfilled drafts may be lower-confidence than fresh ones (the
  alternative may not have had a precise prediction at the time);
  the threshold is "would future-us recognise this as a path we
  considered?" If yes, commit it; if not, leave it as a bullet.
- One bulk-backfill commit per campaign-period; record hash in
  the new M-011 node and `open-paths.md` narrative log.

### Sibling cross-links

When two or more siblings are committed under the same parent at
the same closure, add a `concurrent_with: [...]` field on each
listing the others by `[[H-NNN]]` link. This is the same field
§2 *One active branch per compute stream* uses for sibling H held
open simultaneously across compute streams. Here it doubles as a
"these were considered together" pointer.

### Pruning (deferred)

Open question explicitly deferred per dialogue 2026-04-29: do
unchosen draft siblings expire, get reviewed quarterly, or stay
forever until manually pruned? Not codified in v1 of §16. Revisit
once the procedure has been exercised on a real backtracking
scenario.
