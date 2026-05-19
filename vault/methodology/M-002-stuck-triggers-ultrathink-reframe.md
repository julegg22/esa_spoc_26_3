---
id: M-002
type: methodology
status: confirmed
tags: [methodology, process, decision-rationale, framing]
kind: process-pattern
scope: stuck-handling / step-back
severity: warning
confidence: high
generalizability: cross-campaign
created: 2026-05-19
source: "user directive 2026-05-19; H-002 E-006..E-011 → T-005 reframe"
supersedes:
superseded_by:
---

# M-002 — When stuck, ultrathink: change perspective, hunt the missing hurdle

## What

When a branch is stuck (M-018 triggers: ≥3 consecutive
refutations / a shared failure axis / effort ≫ estimate), the
step-back must include an explicit **ultrathink pass** *before*
choosing the next move:

1. **Change perspective** — restate the problem from scratch; try
   forward↔backward, primal↔dual, local↔global, search↔structure.
2. **Think out of the box** — ask "what would the problem designer
   make hard *on purpose*?"; consider that the obvious method is
   deliberately a trap.
3. **Hunt the missing key hurdle** — enumerate the load-bearing
   *assumptions* and **audit each against ground truth** (the
   official scorer/code, not prose). State which are verified vs
   merely believed.

This is *not* re-pricing the frontier; it is re-grounding the
problem model itself.

## Why it matters

Local refinement after a refutation tends to iterate within a wrong
frame. Publication-relevant: the discipline that converts a stuck
branch into a correct re-frame is a core Human+Claude-Code research
pattern (GOALS.md §3).

## Evidence

H-002: five shooting iterations (E-006…E-011) clustered on one
axis. The user's out-of-the-box prompt ("is a fundamental
assumption wrong — does the Moon keep moving?") triggered an
assumption audit: frame/Moon-motion **verified bit-exact** vs the
official UDP (ruled out), and the real wrong assumption surfaced —
transfer *family/method* (short Hohmann shooting vs the BCP+Sun+
200-day-designed low-energy regime). Captured in
[[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem|T-005]];
redirected effort productively (timebox + pivot).

## Implication

**Hard rule (codified, `META.md §15`):** the M-018 step-back
checklist gains a mandatory ultrathink/assumption-audit step —
list load-bearing assumptions, mark each verified-vs-believed
against ground truth, and explicitly consider a designed hurdle —
before proposing the next branch. Pointer in [[user]].
