---
id: L-005
type: lesson
status: active
tags: [methodology, intel, bootstrap]
created: 2026-05-20
caused_by_experiment: "user-noticed `fcmaes` in submission helper name; fcmaes was installed but not surfaced for 2 days"
related: ["[[M-003-approach-family-inventory]]", "[[M-004-convergence-watchdog-across-families]]", "[[M-005-external-intel-survey]]"]
---

# L-005 — The toolchain IS the intel; audit it at task bootstrap

*Trigger*: Discovered ~30 h into Ch2 work that `fcmaes 2.0.2` was
already installed in the `spoc26` env from day 1 — but never
surfaced by our task-start grounding. The library name also
appears in the leaderboard `submission_helper.py` URL. Both
signals pointed to the canonical winning toolchain (Dietmar Wolz's
GTOC/SpOC library); we missed both because we treated "what
toolchain is the env using?" as out-of-scope.

## Rule

At every new-challenge bootstrap (and at every M-004 trigger), run
a **toolchain audit**:

1. `pip list` / `conda list` of the active env. Anything unusual
   = a hint. ESA/SpOC envs are typically not vanilla.
2. Read **every Python file in the starter kit**, not just the
   README. Look for:
   - Submission helpers (their imports reveal expected toolchain)
   - Utility functions named after libraries (e.g., `find_transfer`
     from `fcmaes` examples → C-012)
   - Comment references to papers / repos
3. List every helper script and ask: "what kind of optimizer
   would consume this?"
4. Record findings as an **O-X observation** node (e.g.,
   `O-009-ch2-toolchain-signals`).

## How this would have caught fcmaes

| signal | how to surface |
|---|---|
| `fcmaes 2.0.2` in env | `pip list \| grep -iE "cma\|evolutionary\|optim"` |
| `fcmaes` in submission helper URL | read `README.md` Submitting section, *click the link* |
| Wolz's tutorials on GTOC | search `"fcmaes" GTOC` or `"fcmaes" spoc` |
| Optimization libs ecosystem | `pip list \| grep -iE "cma\|optim\|pygmo\|nevergrad"` |

## Practical checklist (template)

```markdown
## Toolchain audit — <challenge name> @ <date>

- [ ] `pip list` of env: any libs whose name suggests an
      optimization paradigm? Record them.
- [ ] Starter-kit Python files read: <list>
- [ ] Submission helper inspected: <source path or URL>
- [ ] Imports in helper files: <list>
- [ ] Comments / references in helpers: <list>
- [ ] Search the web for `<library> <competition acronym>`:
      <findings>

→ Observation node: O-X-<challenge>-toolchain-signals
```

## Companion to other rules

- M-003 family inventory: toolchain hints inform family priors
- M-004 watchdog: re-audit toolchain at every trigger
- M-005 external intel: extends toolchain audit to web/community
