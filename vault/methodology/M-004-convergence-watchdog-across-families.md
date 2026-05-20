---
id: M-004
type: methodology
status: active
tags: [methodology, frontier, watchdog, stuck-trigger]
created: 2026-05-20
related: ["[[M-002-stuck-triggers-ultrathink-reframe]]", "[[M-003-approach-family-inventory]]", "[[L-005-toolchain-audit-at-task-bootstrap]]"]
---

# M-004 — Convergence watchdog across families

*Complement to M-002*. M-002 fires *inside a branch* when a single
method gets stuck (→ ultrathink/reframe). M-004 fires
*across branches* when multiple methods in the **same family**
converge at the same value (→ family pivot).

## Trigger

When **N ≥ 3 distinct methods, all in the same approach-family,
converge at the same local optimum** within tolerance ε,
auto-trigger an **orthogonal-pivot review**.

Operationally: for the open hypothesis, list the converged value
and the methods. If the family-coverage table (M-003) shows the
shared family has 3+ entries at the same value, fire.

## The orthogonal-pivot review

1. **Enumerate at least 2 untried families** from the M-003
   taxonomy that are plausible for the problem class.
2. **For each untried family, name a specific tool / library**
   (not just the family). Use the L-005 toolchain audit + an
   ecosystem survey (see M-005).
3. **Cost the pivot**: build effort (h) + smoke-test compute (h).
4. **Run a smoke probe** (≤ 30 min compute) for each pivot before
   deciding to commit fully. The probe answers: "is the tool
   plausibly applicable here?" *not* "does it beat current
   result?".
5. If 1 or more pivots survive the smoke probe, **promote one as a
   sibling on the frontier** with explicit ROI estimate.

## Hard rule

Until ≥1 orthogonal-family smoke probe is *attempted*, do not
invest >1 h further in refining methods of the converged family.
This forces breadth before depth.

## Worked example (Ch2 KTTSP, 2026-05-20)

Should-have-fired-here triggers:
- 142.99 d converged across 7 methods, ALL in local-search family
- Population-evolutionary, ML, problem-specific-analytical families
  were "not_considered"
- Smoke probes would have been:
  - fcmaes/CMA-ES: 30 min — would have shown the warm-start path
  - pygmo SADE: 30 min — pygmo was also installed
  - Wolz GTOC tutorial review: 15 min reading

If M-004 had fired after E-023 (5 methods at 142.99), we would
have probed fcmaes ~1 day earlier without the accidental tip-off.

## Diagnostic prompt template

When the watchdog fires, write to the session log:

> 🔔 **M-004 fired**: methods {A, B, C, ...} all converge at
> {value}. All in family {F}. Untried families: {F', F''}.
> Quick check: {family→library suggestion}. Smoke probe? [Y/N]

## Wiring into the loop

- At every `experiment.close` event, compute the family-coverage
  table; check for the trigger.
- Every session-end checklist (META.md §15) includes "ran the
  watchdog?".
- The frontier reprice considers watchdog state explicitly.

## Not a replacement for ultrathink

M-002 still applies *within* a chosen family. M-004 ensures that
*choosing the family itself* is revisited periodically.
