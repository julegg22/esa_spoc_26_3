---
id: S-2026-05-21
type: session
tags: [session, methodology, fcmaes, bannach, ddd, medium]
date: 2026-05-21
created: 2026-05-21
duration_hours: ~8
participants: [JJ, Claude Code]
claude_model: claude-opus-4-7[1m]
commits: 30+ (full series in git log)
created_nodes: ["[[C-014-cma-es-and-evolution-strategies]]", "[[C-015-fcmaes-coordinated-retry]]", "[[C-016-argsort-permutation-encoding]]", "[[M-003-approach-family-inventory]]", "[[M-004-convergence-watchdog-across-families]]", "[[M-005-external-intel-survey]]", "[[L-005-toolchain-audit-at-task-bootstrap]]", "[[O-009-external-intel-survey]]", "[[E-025-ch2-fcmaes-cma-es-warm-start]]", "[[E-026-ch2-bannach-milp-attempts]]", "[[E-027-ch2-medium-pipeline-stalls]]"]
---

# S-2026-05-21 — Methodology codification + fcmaes/Bannach/DDD/Medium

## Scope

User-driven session in which:
1. **fcmaes discovery (by accident)** revealed a methodology gap →
   M-003 / M-004 / M-005 / L-005 added; META.md §2 updated.
2. **M-005 external intel survey** identified the canonical Bannach
   paper (IAC 2024), HRI as SpOC3 winner (Honda colleagues, separate
   team), and the canonical time-expanded ILP encoding with DDD.
3. **Path 2 build** (per user "go for it, never wait"): canonical
   Bannach MILP via HiGHS + DDD-style refinement. Several rounds
   of fixes; converges encoding correctness but HiGHS too slow
   without Gurobi licence.
4. **Pivot to medium (Ch2)**: 181-start greedy completes 158/180 max
   from start=26; multi-cluster insertion stalls on the 20-node
   missing cluster.

## Key new methodology assets

| node | role |
|---|---|
| **M-003** | Approach-family inventory + breadth requirement (frontier always has ≥2 families) |
| **M-004** | Convergence watchdog: when N≥3 methods *in same family* converge at the same value, fire orthogonal-pivot review |
| **M-005** | External intel survey at bootstrap + watchdog re-fires |
| **L-005** | Toolchain audit (pip list / starter-kit files / submission helpers as intel) |
| **C-014** | CMA-ES & evolution strategies primer |
| **C-015** | fcmaes coordinated retry (Wolz library) |
| **C-016** | Argsort permutation encoding for continuous optimizers |

META.md §2 invariants now include "Family-breadth before depth" and
"Toolchain audit at bootstrap" as non-negotiable rules. Both would
have surfaced fcmaes (env-installed from day 1) and the Bannach
paper at task bootstrap.

## Key experiments (E-025 → E-027)

| # | summary | verdict |
|---|---|---|
| E-025 | fcmaes / CMA-ES from 142.99 warm-start — basin tight; 14 retries returned 142.989 | confirmed-no-improvement |
| E-026 | Bannach time-expanded MILP via HiGHS — encoding correct on 5-node synthetic; n=49 TimeLimits | refuted (HiGHS too slow) |
| E-027 | Medium (n=181) greedy 4.84h → 158/180; multi-cluster blocked by 20-node missing | refuted (pipeline doesn't scale) |

## Banked state — unchanged

- Ch1: 11 pts (small + medium matching banked earlier)
- **Ch2 small: 142.99 d** (rank-3 = 111.76; ratio 1.279; ~3–5 pts)
- Ch2 medium: NOT banked (best partial = 158/180)
- Ch2 large: not attempted
- Ch3: not attempted (tie-breaker)

## What would unlock progress

For **Ch2 medium**:
1. **Gurobi licence** → solve canonical Bannach MILP per Table 1
   (Gurobi 8.5× faster than HiGHS; medium ≈ scale of |A|=20 in paper)
2. **Cluster-FIRST greedy** specifically for medium's 20-node cluster
3. **Decompose into sub-tour problems** + bridge with exceptions

For **Ch2 small polish** (142.99 → < 130 d):
1. **Multiple diverse warm-starts** for fcmaes (not just one)
2. **Full PWL MILP with continuous (td, tof)** (we built discrete-window MILP only)

For **Ch1 trajectory** (paused at H-002 + T-005):
- Global Sun-perturbed low-energy trajopt; revival considered if
  Ch2 medium remains stalled

## Key insight from this session

The user's ad-hoc question about fcmaes triggered the methodology
audit. The codified rules (M-003/4/5/L-005) ensure future sessions
auto-discover this kind of intel at bootstrap, not by accident.
That preserves the >25 h that the gap cost in S-2026-05-19/20.

## Workflow constants confirmed

- "Never wait for user choice — always continue" (user 2026-05-20):
  applied throughout this session; multiple intermediate commits
  reflect ongoing autonomous execution while user offline.

## Where we are on the rank-3 trajectory

Current ratio: 1.279 (Ch2 small). For rank-3 on all instances, need
ratio ~1.0. With current toolchain (HiGHS, fcmaes, find-transfer +
LNS), unlikely without Gurobi or a multi-day MILP-DDD build.
