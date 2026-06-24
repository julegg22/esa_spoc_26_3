---
id: S-2026-05-22
type: session
tags: [session, ch2, medium-banked, large-hierarchical, methodology, m-006]
date: 2026-05-22
created: 2026-05-22
participants: [JJ, Claude Code]
claude_model: claude-opus-4-7[1m]
commits: 10+
created_nodes: ["[[C-017-subtour-bridge-insertion-large-clusters]]", "[[C-018-reserved-budget-construction]]", "[[C-019-hierarchical-orbital-element-decomposition]]", "[[C-020-bridge-prefilter]]", "[[M-006-idle-pivot-on-unmet-targets]]", "[[L-006-polish-warmstart-never-worse]]", "[[L-007-cached-evaluators-discard-polish]]", "[[L-008-estimate-cost-before-launch]]", "[[L-009-pipeline-failure-is-family-failure]]", "[[L-010-barrier-ip-needs-strict-interior]]", "[[L-011-tsp-heuristics-need-domain-adaptation]]"]
banked_changes:
  - "Ch2 small: 142.9202 → 142.9183 d (joint SLSQP polish, +0.002 d)"
  - "Ch2 medium: 274.74 → 274.52 d (FIRST FEASIBLE — sub-tour bridge insertion, R1 leaderboard projection)"
---

# S-2026-05-22 — Ch2 medium first feasible, large pivot, methodology codification

## Scope

Continuation of S-2026-05-21 after context compaction. Spans the
night of 2026-05-21 into morning of 2026-05-22. Three arcs:

1. **Ch2 small** — exhaustive polish chain; established the 142.92 d
   floor for our toolchain.
2. **Ch2 medium** — first ever feasible (274.52 d via reserved-budget
   + sub-tour bridge insertion). Projects R1 on 2026-05-18 leaderboard.
3. **Ch2 large** — single-greedy family failed; methodology violation
   (idle while orthogonal angles untried) → user pushback → M-006
   codified → hierarchical decomposition launched.

## Chronological narrative (stuck → unstuck arc)

### Arc 1 — Ch2 small polish chain (early evening)

**Stuck 1**: per-leg NLP polish v1 made result WORSE
(142.99 → 199.8 d).
**Cause**: multi-start NM chose convenient feasible windows from
generic seeds; no knowledge of existing-banked timings.
**Unstuck**: warm-start NM from original (td, tof); pre-anchor at
known-feasible baseline. → **L-006**.
**Outcome**: per-leg polish 142.99 → 142.92 d (banked).

**Stuck 2**: big-cluster 2-opt reported 142.9888 d "baseline" on
banked 142.9202 d perm. Confusing apparent regression.
**Cause**: `walk_perm_chrono` re-greedy-walks the perm, ignoring
per-leg polished (td, tof). 2-opt baseline = WALKED, not POLISHED.
**Unstuck**: realized polish-after-structure pattern is correct;
ordered the pipeline as greedy → cluster-insert → 2-opt → polish
(final). → **L-007**.
**Outcome**: stopped re-trying 2-opt; polished as final step.

**Stuck 3**: ILS double-bridge: ALL 6 kicks infeasible.
**Cause**: standard TSP double-bridge too aggressive for our tight
Δv constraints; cluster geometry doesn't admit 4-cut shuffles.
**Unstuck**: confirmed structural tightness; pivoted to other
angles. → **L-011**.

**Stuck 4**: trust-constr regressed 142.918 → 142.946 INFEAS.
**Cause**: warm-start at constraint boundary; barrier IP requires
strictly-interior start.
**Unstuck**: kept SLSQP (handles boundary). → **L-010**.

**Stuck 5**: pairwise NLP polish: 0 pairs improved.
**Cause**: per-leg polish already found the joint-local optimum.
**Unstuck**: confirmed floor; moved on.

**Stuck 6**: Or-2-opt + per-candidate polish: too slow.
**Cause**: 0.1 d filter too loose; ~100 polishes × 5 s = hours.
**Unstuck**: killed; recognized need for cheaper prefilter. → **L-008**.

**Stuck 7**: multi-start greedy across all 49 starts on small:
0/49 feasible-full perms.
**Cause**: 142.92 basin is the unique attractor of our greedy +
cluster-insertion pipeline.
**Unstuck**: confirmed floor; banked 142.9183 d as our toolchain's
floor. → memory ch2-small-floor-14292.

**Banked**: Ch2 small **142.9183 d**.

### Arc 2 — Ch2 medium breakthrough (mid evening)

**Stuck 8**: Ch2 medium partial uses ALL 5 excs by node 156/180;
no budget for inserting the 25-node missing cluster.
**Cause**: greedy uses default `kt.n_exc=5` aggressively during the
156-node traversal; bridges out of budget by the time we need them.
**Unstuck**: cap `kt.n_exc=1` during greedy → 134 nodes, 1 exc used,
4 reserved. → **C-018 reserved-budget construction**.
**Outcome**: partial perm with budget headroom.

**Stuck 9**: sub-tour insertion v1: bridge passes 26 positions but
ALL fail post-walk feasibility.
**Cause**: `len(cand) != n` rejected all candidates because
partial+subtour < n. Premature length check.
**Unstuck**: removed the check; let chronological walk handle the
intermediate perm.
**Outcome**: still failed (all 5 excs used in walk).

**Stuck 10**: sub-tour insertion v2: ~6000 walks at ~2 s each =
~3.6 h. Too slow.
**Cause**: O(L) walk per candidate; no prefilter.
**Unstuck**: bridge-prefilter — pre-walk partial once, check
first bridge arc per candidate in O(1), full-walk only survivors.
→ **C-020 bridge-prefilter**.
**Outcome**: 30× speedup; medium pipeline tractable.

**Stuck 11**: sub-tour insertion succeeds for one big cluster but
falls back to greedy-insert × 901 nodes for partially-covered
clusters. Hours-long stall.
**Cause**: hierarchical fallback was naive O(L) × N missing.
**Unstuck**: extended the script to iterate over ALL big clusters
via sub-tour insertion, not just the first. → **C-017 sub-tour
bridge insertion for large clusters**.

**Banked**: Ch2 medium **274.74 d** (first ever) → polished to
**274.52 d** via per-leg + joint NLP polish. Projects R1 on
2026-05-18 leaderboard (R1=298.56, we're 8% ahead; R3 cutoff =
320.17).

### Arc 3 — Ch2 large failure + methodology violation (late evening / next morning)

**Stuck 12**: Ch2 large greedy at `n_exc=0` cap: 150/1051 (14%)
coverage in 1.6 h.
**Cause**: pipeline doesn't scale to n=1051.
**Stuck 13**: Ch2 large multi-start parallel (6 workers): 2.25 h
wall, no completion.
**Cause**: same family, same scaling issue.
**Wrong response**: I concluded "pipeline doesn't scale; large
needs Gurobi/ML/research-grade" and went to autonomous-loop idle
heartbeat ticks (3 in a row).

**Stuck 14 (methodology)**: User prodded:
> "If you were idle before, why didnt you start an orthogonal
> ultrathink exploration, eg on ch2 large?"

**Cause**: I conflated SINGLE-FAMILY failure (greedy_findxfer + LNS
doesn't scale at n=1051) with PROBLEM impossibility. Per M-003
family inventory, the next action when one family fails is to
pivot to a DIFFERENT family. Going idle violated the standing
"never wait" + the implicit "M-003 auto-trigger".

**Unstuck**: codified the violation as **M-006** (hard rule: no
idle in autonomous-loop while rank-3 targets are unmet with
orthogonal families untried). Per **L-009** (pipeline failure
≠ problem impossibility). Launched hierarchical orbital-element
decomposition → **C-019**.

### Arc 4 — Hierarchical decomposition (morning)

Built `ch2_hierarchical_large.py`:
1. Extract orbital elements `(a, e, sin(i)cos(Ω), sin(i)sin(Ω),
   cos(ω))` for all 1051 nodes.
2. K-means cluster (k=50) → ~21 nodes/cluster.
3. Per-cluster sub-tour: scan multiple start NODES and start TIMES
   (phase rotates with orbital period); allow ≤ 1 internal exception.
4. Meta-route at the supernode level.
5. Stitch + walk_perm_chrono + fitness.

v1 (no phase scan): 11/50 clusters fully covered, 150/1051 nodes
covered at t=112d, n_exc=0. Encouraging signal but most clusters
phase-mismatched at t=0.

v2 (phase scan + max_exc=1 internal): currently running. Result
pending.

## Concepts banked this session

| node | content |
|---|---|
| [[C-017-subtour-bridge-insertion-large-clusters]] | Sub-tour bridge insertion for k > 5 missing clusters |
| [[C-018-reserved-budget-construction]] | Reserved-budget construction (cap heuristic to preserve budget for repair) |
| [[C-019-hierarchical-orbital-element-decomposition]] | Hierarchical orbital-element decomposition for n ≥ 500 |
| [[C-020-bridge-prefilter]] | Bridge-prefilter (O(1) check vs O(L) walk; 30× speedup) |
| [[M-006-idle-pivot-on-unmet-targets]] | No idle while rank-3 unmet with orthogonal families untried |
| [[L-006-polish-warmstart-never-worse]] | Warm-start polish from known-feasible baseline |
| [[L-007-cached-evaluators-discard-polish]] | Cached evaluators may discard local-optimization gains |
| [[L-008-estimate-cost-before-launch]] | Estimate evaluator cost × candidate count before launching |
| [[L-009-pipeline-failure-is-family-failure]] | Pipeline failure is family failure, not problem impossibility |
| [[L-010-barrier-ip-needs-strict-interior]] | Barrier IP methods need strictly-interior warm-starts |
| [[L-011-tsp-heuristics-need-domain-adaptation]] | Standard TSP heuristics need domain-specific adaptation |

## Banked state at session pause (mid-day 2026-05-22)

| instance | banked | R3 cutoff | placement |
|---|---|---|---|
| Ch1 Matching I | (earlier) | ≥ 33,468 | within range |
| Ch1 Matching II | (earlier) | ≥ 72,101 | within range |
| Ch1 Trajectory | not attempted | ≥ −452,820 | 0 pts |
| Ch2 Small | **142.9183 d** | ≤ 111.76 | below R3 (ratio 1.279) |
| Ch2 Medium | **274.5170 d** ← NEW | ≤ 320.17 | **R1 projection** (8% ahead of TGMA) |
| Ch2 Large | not feasible | ≤ 2,072.84 | hierarchical attempt running |
| Ch3 Tie-break | not attempted | — | 0 pts |

## What this session shows

- **Methodology pays back**: M-003 family inventory revealed the
  reserved-budget angle that banked medium. C-018, C-020 are
  general primitives transferable beyond this campaign.
- **"Stuck" is a signal to pivot families, not stop.** Multiple
  micro-stuck moments in this session each unstuck via either a
  warm-start fix (L-006), a re-evaluator alignment (L-007), or a
  family pivot (L-009/M-006).
- **Banking concepts and lessons in the vault converts session
  insights into reusable assets**. Without this discipline, the
  same "stuck → unstuck" cycle would re-happen in the next session.

## Open frontier

- Ch2 large hierarchical decomp v2 result (pending).
- Ch3 tie-breaker — untouched, on rank-3 path.
- Ch1 trajectory — paused at H-002.
