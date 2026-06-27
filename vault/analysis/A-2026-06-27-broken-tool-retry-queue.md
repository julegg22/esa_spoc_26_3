---
date: 2026-06-27
type: analysis
tags: [ch2, large, rank-1, retry-queue, broken-tools, evaluator, methodology]
status: ACTIVE — tracks Ch2-large branches that FAILED due to now-FIXED broken tools (re-try candidates)
related: ["[[E-725-ch2-large-fast-faithful-evaluator]]", "[[E-726-ch2-large-ultrathink-audit-rank1-reachable]]", "[[M-general-root-objective-and-proxy-skew]]"]
---
# Ch2-large rank-1: re-try queue — branches that failed on BROKEN tools (now fixed)

Distinct from REFUTED (genuinely wrong) and from genuine walls (e.g. time-expanded GTSP intractability): these
branches reached **negative conclusions caused by a now-FIXED tool defect.** Their failure is **recoverable** —
re-run with the corrected tool before treating the conclusion as real. (This is the same lesson as the project's
recurring "the evaluator, not the search, was the problem.")

## The broken tools (and their fixes)

| Tool defect | Symptom it caused | Fixed by |
|---|---|---|
| **T1 — epoch-SPARSE 1d table** (~6 cheap epochs/edge recorded vs ~100s real) | construction corner-paints; few window options at the frontier | faithful epoch-dense window table (E-726d, `cache/ch2_giant_faithful_windows.npz`) |
| **T2 — long-TOF-BLIND retimer** (fine-scan med±0.8d; bank uses tof to 6.7d) | valid long-tof legs STRANDED; makespan INFLATED (bank order 12 strands / 1104d) | full-tof fine-scan (E-726, `ch2_giant_timebeam.py` MINTOF–8.0) → bank order 3 strands |
| **T3 — max_revs=2 retimer** (speed shortcut) | under-counted feasibility vs official max_revs=20 | numba evaluator max_revs=20 (E-725) |
| **T4 — table-OPTIMISTIC makespan** | "rank-1 pace" illusions that collapse faithfully | faithful numba evaluator (E-725) |
| **T5 — iterated-LKH BIG re-cost** (forbids edge on bad-retime epoch) | epoch-aware iterate DIVERGED (163→461 strands) | soft penalty static+3d (E-726g) → CONVERGES (163→153…) |
| **T6 — spurious non-converged Lambert roots** (numba) | search exploited fake-cheap transfers (50 official over-thr legs) | residual filter (E-725d) |

## Re-try queue (branch → broken tool → what to re-run)

1. **LNS / insertion-repair "cascade" verdict** ([[E-721-ch2-large-foundational-graph-undercount|E-721d/g]]):
   "inserting a stranded city cascades 34→220 strands; local repair structurally blocked." **Tools: T1+T2+T3.**
   A large fraction of those "strands" were the evaluator FAILING TO FIND windows that exist. **RE-TRY**
   destroy-repair/ALNS on the faithful evaluator + full-tof retimer + timing-DP re-schedule. (This is the
   planned rank-1 LNS/SA attack.)
2. **Sub-tour bridge "1-city insert → 300 strands"** ([[E-722-ch2-large-reach-beam-and-phaselock|E-722b]]):
   **Tools: T1+T2.** The 300 strands were largely retimer blindness. **RE-TRY** bridge insertion with the
   fixed retimer.
3. **Order-search (E-724) makespan/strand evaluations** (in [[E-723-ch2-large-bank-reproduction-audit]] /
   [[E-726-ch2-large-ultrathink-audit-rank1-reachable]]): orders were scored on **T2** (long-tof-blind retimer)
   → inflated. **RE-EVALUATE** any saved order with the fixed retimer before trusting its "strands".
4. **"Real algorithmic gap / 575 cap" ultradeep-audit verdict** ([[E-720-ch2-large-ultradeep-audit]]):
   **Tool: T1.** Partly an under-counted/sparse foundation (already REFRAMED by E-726). The completion cap is
   ALSO phasing (genuine), so this is a PARTIAL re-try — re-run construction on faithful windows but expect a
   residual phasing wall.
5. **Rollout / reachability / fail-first beams** ([[E-722-ch2-large-reach-beam-and-phaselock|E-722/c]]):
   **Tool: T1.** Searched the sparse table. PARTIAL re-try on faithful windows (cap is partly phasing too).

## NOT re-try (genuine, not tool artifacts)

- **Time-expanded GTSP** ([[E-718...]]): intractable by SIZE/resolution (~450 dep-epochs/city), not a tool bug.
- **Static LKH order TD-infeasibility** (163 strands re-scored 206 with the FIXED retimer too): genuine, not
  artifact.
- **The short-tof phasing cap (~190–329)**: genuine TD-TSP difficulty (confirmed on the faithful evaluator).

## How to use this

Before re-citing any "cascade / blocked / floored / capped" Ch2-large conclusion, check this table: if its tool
is now fixed, RE-RUN before believing it. The immediate actionable: the **LNS/SA rank-1 attack** (#1) on a
complete order from the (now-converging) iterated LKH.

## PROPAGATION RULE (annotations do NOT auto-flow through child branches)

The vault is per-node; `[[links]]` are navigational, not inheritance — a 🔧 marker on a parent does NOT
propagate to descendants automatically. But a tool-artifact at a parent invalidates the **reasoning chain** of
every child that built on it. **So marking a node TOOL-ARTIFACT REQUIRES manually walking its descendants** and
propagating the marker to any whose load-bearing conclusion *rests on* the artifact (same idea as premise-
propagation in [[M-general-root-objective-and-proxy-skew]]).

**Done for this set:** the broken-tool conclusion "LNS/insertion cascades → local repair blocked → toolkit
exhausted" originated at E-721d/g and was repeated down the chain → E-722 (phase-lock) → E-726 (comprehensive
exhaustion) → S-2026-06-27 (session note). 🔧 banners now sit on ALL of them (E-720/721/722 + the E-726
exhaustion section + the session note), each flagging the LNS/cascade/divergence sub-verdicts as recoverable.
When the LNS/SA re-run completes, update this queue and clear/confirm each propagated marker.
