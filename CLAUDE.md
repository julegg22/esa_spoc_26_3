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

The general methodology (project-agnostic, blog-post-ready):
- `vault/methodology/M-general-anti-oscillation-discipline.md`
- `vault/methodology/M-general-bug-surfacing-for-scientific-code.md`

The Ch1 trigger case that originated these:
- `vault/methodology/M-2026-05-29-systematic-bug-surfacing.md`

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


