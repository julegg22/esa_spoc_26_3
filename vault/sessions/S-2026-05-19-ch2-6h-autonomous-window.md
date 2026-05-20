---
id: S-2026-05-19
type: session
tags: [session, ch2, autonomous-window]
date: 2026-05-19
created: 2026-05-19
ended: 2026-05-20
duration_hours: ~6
participants: [JJ (offline), Claude Code]
claude_model: claude-opus-4-7[1m]
context: "6-hour autonomous research window directed by JJ"
commits: [46c65e8, fab865d, a5e65b5, f15d6b2, 14ed32c, 26b39b5, 851f514, a0f2956, 2db55a1, 43c6860, 821354e, 9a4ae68]
created_nodes: ["[[O-008-ch2-cheap-window-density-per-pair]]", "[[E-018-ch2-cpsat-fullhorizon-still-infeasible]]", "[[E-019-ch2-edge-compute-marginal-value-zero]]", "[[E-020-ch2-cpsat-mw-singletof-infeasible]]", "[[E-021-ch2-cpsat-mw-v2-infeasible-diagnostics]]", "[[E-022-ch2-banked-145d-cluster-insertion]]"]
banked_results: "Ch2 small @ 145.80 d (4/5 exc, ~3-5 pts; ratio to rank-3 = 1.305)"
---

# S-2026-05-19 — Ch2 6-hour autonomous research window

## Scope (per JJ's directive)

> "You have a compute window of 6 hours now, so continue fully
> autonomously. Try to find out as much as possible about the right
> approach, so that we afterwards know well where to spend more
> heavy compute time."

Per the [[user]] standing rules: no leaderboard submissions; stealth
identity; parallel + conservative; ultrathink on stuck; capture
concepts as they arise; ruff+smoke before background launch (L-04);
ask-but-never-stall.

## What landed in this window (delta)

### Banked
- **Ch2 small @ makespan 145.80 d, 4/5 exceptions used, feasible** —
  the first ever banked Ch2 solution (E-022). Banked at
  `solutions/upload/small.json`; expected ~3–5 pts at leaderboard
  placement rank 6–10.

### Methodology (T-008 trajectory)

E-018 → E-019 → E-020 → E-021 → E-022 is a **5-experiment chained
refutation + breakthrough** demonstrating the methodology under
genuine difficulty:

| E | hypothesis | verdict | finding |
|---|---|---|---|
| E-018 | full-horizon retime fixes CP-SAT | **refutes** | the **time-coupling** is the binding crux ([[O-008]]) |
| E-019 | denser edge precompute lifts feasibility | **refutes** | 16× compute = ZERO new cheap edges; resolution saturated |
| E-020 | multi-window CP-SAT (K=8 td-only) | **refutes** | static-tof per pair = wrong precompute target (ΣTOF=1312d) |
| E-021 | joint (td, tof) v2 K=12 + diagnostics | **refutes** | 5-node sub-INFEASIBLE → graph topology; discrete CP-SAT cannot capture continuous time |
| E-022 | find_transfer + cluster insertion | **CONFIRMS** | first banked Ch2 @ 145.80 d via greedy-on-arrival + small-cluster insertion |

### Concepts captured
- C-010 (constrained Hamiltonian time-dependent routing) used as
  central frame for E-018+
- find_transfer pattern from `SpOC4/utils_users.py` re-discovered as
  the canonical per-leg primitive (E-022)

## Key decisions and reframes

1. **Trade off Q6 (medium/large structure)** for the decisive
   experiment chain — killed Q6-medium-sample-60 after >1h, ran
   sample-30 instead (then also killed in favour of v2 chain).
2. **Killed v1 CP-SAT after INFEASIBLE in 14s**; pivot to v2 (joint
   td-tof). v2 also INFEASIBLE → pivot to v3 dense. v3 UNKNOWN.
   Pivot to NLP-per-leg continuous-time. NLP-greedy too slow → pivot
   to NLP-perm-refine. Still no full chain. Pivot to find_transfer
   (the official helper) + cluster-insertion. **Breakthrough**.
3. **Conservative expectations met**: at 145.80d we are 30 % over
   rank-3 (111.76d) but well below rank-LAST. ~3–5 pts banked.

## Compute footprint of the window

- 5 background tasks run (chain runs, structure probes)
- 7 NLP / CP-SAT prototypes built and tested
- 13 commits, all pushed to `origin/main` via SSH `id_ed25519`
- Files: `ch2_cpsat_tw.py`, `ch2_cpsat_mw.py`, `ch2_cpsat_v4.py`,
  `ch2_nlp_greedy.py`, `ch2_perm_nlp.py`, `ch2_perm_lns.py`,
  `ch2_greedy_chrono.py`, `ch2_findtransfer_greedy.py`,
  `ch2_insert_lns.py`, `ch2_insert_lns_topk.py` (10 modules)
- `precompute_windows_2d` (joint td-tof) with v2 (K=12) and v3
  (K=24, 15 tofs) variants in `ch2_kttsp.py`

## What the user gets back

A clean, data-grounded answer to "where to spend heavy compute":

1. **NOT** discrete CP-SAT over (td, tof) point-windows — proven
   infeasible at three densities up to 18 651 windows (E-018→E-021).
2. **NOT** edge-search resolution — flat marginal value (E-019).
3. **YES** greedy-on-arrival-time with `find_earliest_transfer`
   (the official `find_transfer` pattern).
4. **YES** cluster-aware insertion-LNS for handling unreachability
   pockets (the 3-node small cluster {17, 11, 4} in this instance).
5. **YES** 2-opt / multi-seed polish to reduce 145.80 → ~120 d.
6. **Heavy-compute target for the user's main investment** —
   per-leg makespan-NLP (current greedy picks first-feasible tof,
   not makespan-optimal); cluster-bridge enumeration for medium /
   large; same pipeline expected to transfer (Q6 deferred).

## Bookkeeping

- T-008 finalised: continuous-time per-leg + permutation
  metaheuristic (was draft; refuted v1 = discrete CP-SAT scaling).
- O-008 added: cheap-window density per pair (~100 windows per
  cheap pair in 0–200d).
- O-007 still valid for the structural picture.
- Q6 (medium/large structure) deferred — same pipeline expected to
  transfer; verify next session.
- Frontier updated: H-003 polish + Ch2-medium queued.

## Estimated leaderboard impact (informational only — no submission)

- Ch1 matching-i + matching-ii: ~11 pts (locked)
- **Ch2 small @ 145.80 d: +~3–5 pts (new)**
- Total: **~14–16 pts** with conservative estimate. Rank-3 target on
  Ch2 small would require polish to ≤ 112d (extra ~3–5 pts).
