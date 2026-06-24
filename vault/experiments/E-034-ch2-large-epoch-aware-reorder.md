---
id: E-034
type: experiment
status: banked (large 2225.17 → 1048.98 d, feasible; E-562b terminal included)
tags: [ch2, large, epoch-aware, tof-reorder, ortools, makespan, breakthrough]

hypothesis: "large makespan is the sum-of-tof of the chosen 0-big-jump Hamiltonian order; re-ordering against a time-correct tof cost reduces it"

created: 2026-06-11
ran_start: 2026-06-11
ran_end: 2026-06-11
duration_runtime: "~3 h wall across E-561 + E-562 (single core each)"

code: scripts/ch2_e561_large_tofaware.py, scripts/ch2_e562_large_epoch_aware.py
inputs: |
  solutions/upload/large.json (2225.1654 d first feasible, from E-559)
  /tmp/ch2_e533_large_adj.npz (cheap/exc adjacency, labels)
  /tmp/ch2_e559_assembly_plan.json (5-bridge comp0-last topology)
outputs: |
  solutions/upload/large.json (1536.3953 d, feasible)
  backups: large_2225.json, large.json.bak.e561, large.json.bak.e562
  runs/ch2_e561_large_tofaware.log, runs/ch2_e562_large_epoch_aware.log
  /tmp/ch2_e562_assembly_plan.json
env: micromamba spoc26 (OR-Tools 9.15)

verdict: confirms (epoch-aware tof cost is the lever; banked −688.77 d total, feasible re-validated)
---

# E-034 — Large epoch-aware tof re-ordering (2225 → 1536 d)

## Setup

First feasible large bank (E-559) was 2225.1654 d via the 5-bridge
"comp0-last" topology (see [[E-034-ch2-large-epoch-aware-reorder]]). Decomposition
(E-560) showed makespan = sum-of-1050-tofs EXACTLY, IDLE=0; the 5 bridges
contribute only ~14 d. So the lever is the Hamiltonian ORDER: OR-Tools had
minimized cheap-edge-COUNT (cost=1 per cheap edge), not tof.

Two-stage attack, both preserving the topology (3 smalls oa/ob/oc + comp0
split segA/segB/segC at 267/508, dead-tail 931 at terminus, 5 exc, big_jumps=0):
- **E-561**: cost[i][j] = tof-if-cheap-else-BIG, scored via find_earliest_transfer
  at 4 FIXED reference times; OR-Tools PCI+GLS per piece; segB seeded via
  ReadAssignmentFromRoutes from the valid cheap-Ham order to keep big_jumps=0.
- **E-562**: same, but EPOCH-AWARE cost — score each edge at the epoch the
  chronological walk actually reaches node i (epochs extracted by walking the
  previous iteration's order), iterated 3 rounds.

## Results

| Stage | makespan (d) | Δ | legs>3d | sum>3d (d) |
|---|---|---|---|---|
| E-559 (first bank) | 2225.1654 | — | 220 | ~1040 |
| E-561 (fixed-ref-time) | 2182.0087 | −43.16 | 223 | 1118.5 |
| E-562 iter0 | 1957.006 | −225 | 185 | 925.4 |
| E-562 iter1 | 1732.271 | −225 | 133 | 663.8 |
| E-562 iter2/3 (BANKED) | **1536.3953** | −195.6 | 102 | 495.2 |

All re-validated independently (kt.fitness): viols=[0,0,0,0], is_feasible=True,
1051/1051 unique nodes, dV=3151, exc=5, big_jumps=0. Total session: −688.77 d
(−31%).

## Why E-561 barely moved but E-562 worked (the key finding)

The fixed-ref-time cost is an optimistic, TIME-INDEPENDENT lower bound. But the
walk reaches t~1500-2200 d by leg 500+, where the real earliest cheap transfer
is far longer than the best-of-4-ref-times proxy (e.g. epoch-aware segB cost
257 d vs fixed-ref proxy 104 d). E-561's GLS thus minimized the WRONG objective.
Making the matrix epoch-aware aligned the OR-Tools objective with the realized
chronological tof and collapsed the heavy tail. This is the
[[M-general-foundation-then-search]] / audit-the-evaluator trigger paying off:
the evaluator metric must match the walk metric.

## Leaderboard / rank

Large podium: r1=424.62, r2=1143.56/1153.90, r3=1186.65/1206.75/1238.52.
1536.40 d is still above the worst podium (1238.52) → ~rank 7, but the gap
collapsed from 5.2× to 1.24× the leader's distance. **This is now the campaign's
most promising rank-3 path** (vs the high-risk Ch1 WSB).

## Next levers (→ E-562b, running)

Predecessor reported iterations still improving ~200 d/round at cutoff; projects
1300-1450 d with N_ITERS 6-8. Plus: (a) sequential per-piece re-solve (re-walk
after each piece so downstream pieces see fresh epochs — fixes the one-round
epoch lag), (b) revisit split points 267/508 (tuned for the old proxy). Target:
cross 1238.52 (top-6) then 1186.65 (rank-3).

## E-562b terminal result (2026-06-11 19:47) — BANKED 1048.9786 d

Sequential per-piece re-solve beat the 1300-1450 projection by ~300 d.
Iteration trace (each = oa→segA→ob→segB→oc→segC, OR-Tools PCI+GLS 240 s/piece,
re-walk after every piece):

| iter | mk (d)    | Δ      |
|------|-----------|--------|
| base | 1536.3953 | —      |
| 0    | 1394.6329 | −141.8 |
| 1    | 1246.3236 | −148.3 |
| 2    | 1158.5405 | −87.8  |
| 3    | 1109.2376 | −49.3  |
| 4    | 1054.7239 | −54.5  |
| 5    | 1048.9786 | −5.7 (stop: <10 d) |

Terminal REVAL (script-side): mk=1048.9786, feas=True, viols=[0,0,0,0],
covered=True, exc=5, big_jumps=0. Guarded bank executed: backup
`large.json.bak.e562b`, then `solutions/upload/large.json` (disk mtime 19:47,
both verified). Independent kt.fitness re-validation pending (tool outage at
terminal time) — run before any submission decision.

Day total: **2225.17 → 1048.98 d (−53%)** across E-560 decomposition →
E-561 tof-aware (−43) → E-562 epoch-aware rounds (−646) → E-562b sequential
per-piece (−487). Board context (snapshot 15:40): r2=1143.56, r3=1153.90 →
**1048.98 is rank-2 territory (16.0 pts at hard ×16/9)**; r1=424.62 likely
needs cluster-decomposition + exact per-component solvers (TGMA inference,
queued as E-563).

Residual structure at terminal: tail max 24.23 d, 38 legs >3 d summing 219 d —
real headroom remains, but the next ~100 d toward r1 is priced as a new
architecture, not more iterations (iter5's +5.7 d confirms diminishing returns
of the current operator set).
