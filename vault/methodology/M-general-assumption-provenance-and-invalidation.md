---
title: "Assumption provenance & multi-level invalidation — the vault as an assumption-TMS"
tags: [methodology, general, vault-pattern, invalidation, assumptions, abstraction-ladder]
created: 2026-07-01
type: methodology
status: ACTIVE — extends META §15 (code-dependency cascade) to all abstraction levels
---

# Assumption provenance & multi-level invalidation

Companion to [[M-general-abstraction-ladder-audit]]. That node says *how to
find* the level a wall sits at. This node says *how the vault represents* the
fact that **every conclusion is only valid given the assumptions of its
branch**, so that invalidating an assumption at ANY level (objective, model,
structure, encoding, …) propagates to the conclusions that rest on it.

## The problem (why the encoding weakness never propagated)

The vault records **conclusions** (E verdicts, H closures, "walled/floored"
notes). Each conclusion rests on assumptions at every ladder rung, **inherited
from its whole originating branch**. But:

- Assumptions are **implicit**. A conclusion rarely states "this holds *given*
  the uniform-grid encoding is faithful."
- The only **explicit** provenance we had is `code_dependencies` (META §4/§15)
  — which captures **L2 (model/code)** dependencies and nothing else. So the
  §15 cascade fires for code bugs but is **blind** to L1/L3/L4 assumption flips.
- Derivation (`parent`) ≠ validity dependency. Two experiments in *different*
  branches can share the encoding assumption; the `parent` tree does not
  connect them, so a tree walk can't find all dependents.

Net: when we learned the **encoding** (L4) is weak, nothing in the
representation could tell us *which* past conclusions are now conditional.

## The model — overlay an assumption-DAG on the derivation tree

Keep the derivation tree (single `parent`, the narrative — META §1). **Overlay**
an explicit **assumption-dependency DAG**:

- **Assumptions are first-class and ladder-tagged.** They live in the single
  **Assumption Register** `vault/assumptions.md` (the assumption analogue of the
  single-frontier `open-paths.md`). Each row: `ID · ladder level (L1–L8) ·
  falsifiable statement · status {holds|suspect|refuted} · evidence · underpins
  (levers/verdicts) · on-flip action`.
- **Conclusions declare their NEW load-bearing assumptions** via an `assumes:
  [ID, …]` frontmatter field (list of register IDs). The *effective* validity
  condition of a conclusion = its own `assumes` ∪ the transitive closure up its
  `parent` chain. That is the vault encoding of "all previous assumptions from
  the originating branch play a role."
- Only **load-bearing** conclusions must populate `assumes:` — walls, floors,
  banked results, "closed/exhausted" verdicts. Exploratory probes may skip it.

This is a **lightweight assumption-based truth-maintenance system (ATMS)**:
conclusions are *justified by* assumptions; retract one → dependents lose
justification → re-triage. Our §15 code cascade is the special case for L2; the
register generalizes it to all rungs.

## Invalidation propagation (generalizes META §15; new trigger T6)

When a register row flips to `suspect`/`refuted`:

1. **Find dependents.** `git grep -l "assumes:.*<ID>" vault/` (plus any node
   whose branch inherits it). The register row's `underpins` names the class up
   front.
2. **Overlay, don't delete.** On each dependent add the META §4 `invalidation:`
   block with a new **`level:`** field = the ladder rung that failed. The
   original `verdict` stays — it was **true under its stated assumptions**.
3. **Triage each dependent into one bucket:**
   - **RE-RUN** — the conclusion was a *tool/encoding artifact*; redo under the
     corrected assumption (this is exactly the [[broken-tool-retry-queue]] /
     TOOL-ARTIFACT 🔧 bucket).
   - **REFRAME** — the conclusion's *meaning* changes but no re-run needed
     (e.g. a proxy-skew re-statement in the root objective).
   - **STILL-HOLDS** — the flipped assumption was not actually load-bearing for
     this conclusion; annotate and move on.
4. **Backlog + cadence.** Retro-tagging the full dependent set is incremental —
   highest-value first (the "walled/closed" verdicts we might overturn). The
   weekly review consumes the queue; housekeeping surfaces it (below).

## What happens to old experiments now that ENCODING (L4) is suspect

Concretely, the current case:

- Add register row **`ENC-grid` (L4)**: *"a Ch2 makespan-optimal tour is
  reachable by retiming a fixed visit order on a uniform time-grid encoding"* →
  **REFUTED** (E-759: idle 100% order-forced; the epoch-shift trap). `underpins`
  = the Ch2 retiming-based "floor/walled" verdicts.
- Those experiments are **not wrong and not deleted.** They recorded a real
  result *under the uniform-grid encoding*. They get `invalidation: {level: L4,
  notes: "conditional on uniform-grid encoding, now non-faithful; revalidate
  under window-indexed / exact-clock joint search"}` and land in the RE-RUN
  bucket. Their original verdict remains citable as "true under its assumptions."

## Mirroring R1–R5 in the representation

- **R1 (name the level)** — every "exhausted/walled" node carries
  `wall_level: Lx` in frontmatter; housekeeping rejects un-leveled wall verdicts.
- **R2 (tool wall ≠ lever death)** — split **lever** from **implementation**:
  the walling goes on the *implementation* node (`wall_level: L6`), the *lever*
  (its H / open-paths entry) stays **open**. A lever is removed from
  `open-paths.md` only when its **level** is R1-exhausted, not when one tool fails.
- **R3 (sibling-transfer)** — a `family:` tag + a family-map note list shared
  structure/machinery across sibling instances; register rows whose `underpins`
  spans siblings (e.g. `ENC-grid` underpins small+medium+large) make shared
  assumptions visible, so a fix on one instance is scanned against the others.
- **R4 (relaxation-beats-target ⇒ constraint-handling gap)** — recorded as a
  positive **bound observation** (O-node / register note) linked to the
  constraint-handling lever, never a "capped" verdict.
- **R5 (cost-asymmetry counter-bias)** — `open-paths.md` gains a **ladder-level
  column** and stays ordered so high-rung (A/B) levers remain visible; a frontier
  that is all-L8 is itself a flag.

## Is a tree the right representation? — verdict

**No — a single tree is insufficient; keep it, but overlay two more relations.**
The derivation tree is right for *history* and the episodic loop. Validity is a
*different* relation that does not coincide with derivation, so it needs its own
edges: the **assumption-dependency DAG** (register + `assumes:`) for propagation,
and **ladder-level tags** for systematic coverage and for seeing which rung we're
stuck on / grinding. The vault already proved it can carry overlay-invalidation
(§15); this generalizes the trigger from code to all rungs.

## Evidence — our breakthroughs are a walk DOWN the ladder

Tagging past corrections by level shows the pattern that justifies making the
ladder first-class: L2 model bugs (eccentric-departure, idD=0) → L5 evaluator
(8-probe undercount) → L1 proxy (completeness-skew) → L6 solver (GTSP can't
express ≤5) → now **L4 encoding / L3 structure**. Each breakthrough was an
assumption flip one rung further down. The remaining rungs are where rank-1
sits — so the representation must make an assumption at *any* rung a first-class,
invalidatable object.

## When NOT to over-apply

Don't premise-decompose trivial probes. The register is for **load-bearing**
assumptions (those underpinning a banked result or a wall verdict). Keep it
small and honest — a register bloated with non-load-bearing rows is as useless
as none.
