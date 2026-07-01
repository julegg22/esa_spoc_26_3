---
id: S-2026-07-02
type: session
date: 2026-07-02
tags: [methodology, ch2, reproducibility, process]
---
# S-2026-07-02 — Methodology overhaul + Ch2-small method validated

Post-challenge (final 7th). Open-ended goal: rank-1 parity on all instances. This
session was primarily a **methodology build-out**, validated by one live result.

## Scope / key decisions
- **Abstraction ladder** (L1 objective → L8 params): a wall is the *highest
  mismatched rung*, not "the problem is hard". Why our audits missed
  *encoding* (L4): flat assumption lists, lever/implementation conflation,
  per-instance silos, cost-asymmetry bias. Node: `M-general-abstraction-ladder-audit`.
- **Assumption Register** (`vault/assumptions.md`) + `assumes:`/`reruns:`/`wall_level:`
  provenance: validity is an invalidatable DAG *over* the derivation tree; a flip
  runs the META §15 **T6** cascade. Node: `M-general-assumption-provenance-and-invalidation`.
- **Cadence & triggers** (`doc_methodology §7`): event/time/gate taxonomy;
  `/loop`(explore) vs `/goal`(exploit); the old plateau branch was an R5 violation.
- **Consultation levels** (§9): L0 autopilot / L1 signpost (default) / L2 consult —
  advisory, never blocking.
- **Reproducibility** wired in: run-time `_prov.stamp` → `[PROV] commit` → `E.commit`;
  clean-tree-before-bank; META §2/§4/§6 + housekeeping check.
- **Coherence pass**: `doc_methodology` Operating Model (hot path vs reference;
  canonical source map; two-scale explore/exploit; n=1 caveat).
- **3-tier code separation**: `src/`=library, `scripts/`=experiments, `tools/`=process;
  `tools/README.md` = canonical scaffolding inventory.
- New docs: `doc_methodology.md`, `doc_lessons.md`. New command: `/housekeeping [push]`.

## Scientific result (the framework's live test)
- **Ch2-small VALIDATED**: exact-DP+LNS on the window-indexed rep found feasible
  **111.96 d**, beating bank **112.996** (re-verified). It's the RE-RUN of the
  GLKH-walled lever (ENC-grid L4 + SOLVER-gtsp-exc L6) — R2/R3/R4 in action. E-760.
- **Ch2-medium: L4 wall.** The same method **did not improve** the bank (182.11);
  the ladder sweep **ruled out L7** (3 configs converge) → wall = **L4 encoding**,
  same rung as small but starker. Honest evidence the easy small win does *not*
  generalize; rank-1 (172) needs an L4 rebuild. (E-761 pending in the loop.)

## Open threads
- Fork (L1-signposted): medium/small L4 rebuild vs **graduate to LARGE**
  (cluster-decompose+couple; biggest gap; HRI hint) — recommendation = large.
- The framework is itself an **n=1 hypothesis**; medium/large are the real test.
  "The methodology must earn its keep in results, not documents."
