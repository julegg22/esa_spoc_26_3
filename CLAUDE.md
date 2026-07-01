# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Goal-driven scientific process

Read `GOALS.md` for *what* this project is trying to achieve (root
goal, sub-goals, goal-domain rules) and `META.md` for *how* we work
toward those goals (research methodology, vault structure,
invariants). Adhere to the spirit of both.

The **central synthesis** of our optimization methodology — the
abstraction ladder (why we get stuck and at which level: objective →
model → structure → encoding → evaluator → solver → operators →
params), the vault structures that mirror it (the Assumption Register
`vault/assumptions.md` + `assumes:` provenance), and the processes on
them (top-down sweep, the §15 T6 invalidation cascade, housekeeping) —
is **`doc_methodology.md`** at repo root, with **`doc_lessons.md`** its
companion case library (how we failed at the process level + the
directives that broke walls, each now codified). **Keep both in sync**:
when the ladder, the rules R1–R5, the register schema, or the cascade
change, update `doc_methodology.md` in the *same commit*; when a wall is
broken or a process root-cause is found, add a case to `doc_lessons.md`.

## 5a. Investigation discipline (anti-oscillation + bug-surfacing)

This project uses an explicit **anti-oscillation** discipline. When
investigation has cycled ≥3 times between competing explanations for an
observed gap, or when you find yourself proposing a "new structural
insight" / "real lever" / "what we missed", **STOP** and consult
`vault/methodology/M-applying-methodology-triggers.md`. The trigger
table there is **not optional** — it's the project's expected workflow.

Key triggers (full list in the doc):
- "Saturated / plateau / ceiling" claim → per-instance check on 3-5
  cases before concluding (aggregate metrics can match wrong hypotheses)
- Solver rejects >30% of candidates → instrument silent reject paths
- New lever proposal → must fit a row of the quantitative gap
  decomposition OR explain the unexplained residual
- Default values added → hostile-default audit (what if maximally
  adversarial?)
- "Stuck / walled / exhausted", or the urge to add compute / try another
  solver variant → run the **abstraction-ladder sweep** top-down
  (objective → model → structure → encoding → evaluator → solver →
  operators → params). The wall is the *highest* mismatched rung, not the
  cheap bottom one you reach for first; a tool wall is a solver-level fact,
  not lever death; no "exhausted" verdict without naming its level.
  (`vault/methodology/M-general-abstraction-ladder-audit.md`)
- An assumption a past verdict relied on is refuted at ANY level (not just
  a code bug) → flip its row in `vault/assumptions.md` and run the META §15
  **T6** cascade (grep `assumes:`, overlay `invalidation:{level}`, triage
  RE-RUN / REFRAME / STILL-HOLDS). A conclusion is only valid under its
  branch's assumptions; record load-bearing ones with `assumes:`.
  (`vault/methodology/M-general-assumption-provenance-and-invalidation.md`)
- Plateau (K attempts / T hours at one rung, no target-progress) OR 3+
  same-family methods converge → run the **ladder sweep** and act at the
  highest mismatched rung. Do NOT reflexively reach for finer resolution /
  more operators / more restarts — that low-rung grind is the R5 tell.
  Cadence & the `/loop`(explore)–`/goal`(exploit) split: `doc_methodology.md` §7.

The general methodology (project-agnostic, blog-post-ready):
- `vault/methodology/M-general-anti-oscillation-discipline.md`
- `vault/methodology/M-general-bug-surfacing-for-scientific-code.md`
- `vault/methodology/M-general-abstraction-ladder-audit.md`

The Ch1 trigger case that originated these:
- `vault/methodology/M-2026-05-29-systematic-bug-surfacing.md`

## 5b. Exhaustion is a transition, not a stop (never give up the top lever)

When you judge a method *family* exhausted / plateaued / walled on the
highest-value open goal, you are **forbidden** to stop, hand back to the
user, or redirect the freed effort to a *lower-value* lever. "Keeping
cores busy" on lesser work while the top lever still has an unbuilt next
step **is** the failure mode — *busy is not the same as exploring the best
lever.* (The older "no idle cores" rule does not cover this; you can be
fully busy and still have given up.)

**Mandatory sequence the moment you think a family is exhausted:**
1. **Name** the next most plausible exploration step — a different method
   family, a relaxed assumption, a faster/different primitive, a
   sub-problem, or the bottleneck you just isolated.
2. **Take it.** Build and run it. A step being "heavy / research-grade /
   multi-day / the competitor's method" is a **specification of what to
   build, not a reason to defer it.** Scope it and start; report progress,
   not a request for permission.
3. **If genuinely no next step exists,** run the deep audit
   (`M-general-deep-single-prompt-audit`) that questions the *results and
   assumptions* to **derive** one. The audit is itself the next step — it
   has repeatedly turned a false "exhausted" into a live lever (Ch1
   asymmetry bug, Ch2-small resolution, Ch2-large 8-probe graph).

**Self-check — these phrases, when you write them as a reason to
stop/defer/pivot, ARE the trigger to run the sequence above instead:**
"exhausted", "plateau / ceiling / wall", "genuine/real <X> problem",
"research-heavy", "multi-day / not a quick build", "beyond a quick fix",
"the competitor's sophisticated method", "fundamental limit", "I'll build
it if you want". The instant you catch one, name + take the next step.

**The only legitimate stops:** (a) the submission gate (user-gated, never
auto-submit) and destructive/outward actions; (b) a deep audit that
*explicitly, with evidence,* concludes the admissible optimum is reached.
"It's hard / it's a real research problem" is never one of them — that is
a build spec.

Case that named this rule (2026-06-25, Ch2-large rank-1): I correctly
named the forward path (continuous-time TD-TSP metaheuristic + a fast
drift-free evaluator), then used its difficulty to stop and pivot to a
matching grind — until the user pushed. The difficulty WAS the spec.
See `vault/methodology/M-general-exhaustion-is-a-transition.md`.

## 6. Commit conventions

- **No AI-attribution trailer.** Do not append `Co-Authored-By:` or
  similar AI-attribution lines to commit messages. Keep messages
  focused on the change.
- Stage files explicitly by name or directory; avoid `git add -A`.
- Messages: 1–2 sentences, focus on *why* rather than *what*.

## 7. Session resume / continuity

On a fresh session in this repo (new machine, `--resume` not used, or
context cleared), orient by reading the **tiered memory** defined in
`META.md §14`:

1. **Active (always):** `GOALS.md`, `META.md`, `vault/user.md`,
   `vault/index.md`, `vault/open-paths.md`.
2. **Recent (always):** the newest file in `vault/sessions/` — the
   episodic "what we just discussed and decided" narrative.
3. **Rolled-up (only if the newest session is > 7 days old):** the
   newest file in `vault/reviews/` — that's the weekly
   consolidation.
4. **Archived (on demand):** older sessions accessible via
   `git log`, `git grep`, or direct path. **Don't** read every
   session on resume — weekly reviews consolidate them.

After reading, confirm the active frontier entry with `git log
--oneline -20` and open the named H file.

**Housekeeping triggers** (keep vault + git from drifting; see
`vault/methodology/M-general-housekeeping-cadence.md`):
- **At resume AND wind-down:** run
  `python scripts/housekeeping_check.py` (mechanical drift: uncommitted
  vault, untracked scripts, unpushed commits, dangling links, MEMORY.md
  pointer rot, cache-without-generator). Fix what it flags **before
  proceeding** — never batch it. Then do the *judgment* review
  (`M-001`): did this session produce a reusable insight not yet in a
  C-/L-/M- node? Is the session note written? `git status vault/` must
  end empty.
- **Every `/loop` tick:** the loop prompt runs the same check as a cheap
  gate and fixes flagged mechanics that tick.
- **Weekly:** a cloud cron runs the full audit + writes the
  `vault/reviews/` consolidation (triages the dangling-link backlog).

Re-clone the gitignored upstream starter kit:

```
git clone --depth 1 https://github.com/esa/SpOC4.git reference/SpOC4
```

Install pre-commit hooks (one-time per clone):

```
pip install pre-commit && pre-commit install
```

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


