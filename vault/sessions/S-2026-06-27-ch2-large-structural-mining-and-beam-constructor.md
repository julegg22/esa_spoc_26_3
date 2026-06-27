---
date: 2026-06-27
type: session
tags: [ch2, large, rank-1, cls, fragility, beam-constructor, leaderboard, timing-fragility, deepaudit]
related: ["[[E-727-ch2-large-faithful-insertion-repair]]", "[[E-728-ch2-large-robust-cls-and-solution-patterns]]", "[[E-729-ch2-large-low-degree-bottleneck-and-cheap-slot]]", "[[E-730-ch2-large-node-fragility-analysis-and-fragstart]]", "[[A-2026-06-27-broken-tool-retry-queue]]"]
---
# Session 2026-06-27 (cont.) — Ch2-large rank-1: robust CLS, structural mining, the beam constructor, and the decisive wall

Continues S-2026-06-27-ch2-large-rank1-exhaustion-and-evaluator-fixes (morning: evaluator fixes + 3 audits).
This afternoon was user-driven structural mining of Ch2-large rank-1, ending in a **decisive, well-evidenced
wall** plus durable tooling. All banks HELD/unsubmitted per user.

## Arc (each step a user prompt or its consequence)

1. **E-727 — faithful insertion-repair (re-try-queue #1, executed on FIXED tools).** Built a fast validated
   W-beam retimer (combined faithful short-tof ∪ dense1d long-tof windows) + mid-tour regret-2 insertion.
   Result: insertion fills the seed's idle slack for free to ~368/601 (makespan drops), then walls — greedy
   438/601 @908 d, regret caps 385 @461 d. **Closes re-try #1: insertion still walls on correct tools = genuine
   phasing, not the broken evaluator.**
2. **User: "find ONE robust-against-strands method, then several alternative solutions + analyse patterns."**
   - **E-728 — CLS (complete-order penalty local search):** keep all 601 cities, minimise (strands, makespan)
     by strand-targeted or-opt + SA — never drops a city. Robust by design; descends. Pattern analysis →
     **two structural basins:** bank-basin (edge-Jaccard 0.96–0.99, near-feasible) vs LKH-basin (0.0–0.017 =
     genuinely different topology, but deeply TD-infeasible 153–573 strands). Resolves the "why only one
     topology?" mystery: the bank topology is the only basin near TD-feasibility.
3. **User: "more city-graph analyses (connectivity, fragility), prioritise cities, precompute feasible windows;
   proximity vs fragility?"**
   - **E-729 — low-degree bottleneck + cheap-slot move.** The strand cities are LOW cheap-degree (7–14 preds vs
     median 152); 6 recurrent ones. NOT structural (1000+ windows, all epochs) — a sequencing constraint (the
     immediate predecessor must be 1 of ~10 cheap preds). **cheap-slot move** (place a stranded low-degree city
     between a cheap pred & succ) broke the 6-strand stall (6→2). Conflict-graph check: 118-city low-degree
     subgraph, contended, but **no Hall obstruction (118/118 matchable)** → not structurally blocked.
   - **E-730 — per-node fragility analysis.** Fragility index = `max_gap` (longest unreachable stretch). Bimodal
     graph: 482 robust + 119 fragile cities. **Proximity (orbital isolation) ⊥ fragility (r=0.12)** — fragility
     is a PHASE-synchronisation property, not geometric. CAVEAT: NO static node feature strongly predicts actual
     strands (all ~0.1; difficulty is GLOBAL timing coherence) — static priors are an endgame tie-breaker only.
4. **E-730b — the actionable win: the W>1 time-aware BEAM constructor.** Fragile START + earliest-arrival greedy
   = 87-strand seed (2× better than static 150–165); branching over windows (beam) → **44 → 30 → 16 strands**
   (wider beams keep improving). Best seeds on record. `scripts/ch2_beamfrag_constructor.py`.
5. **E-730c — DECISIVE: makespan converges to RANK-2 across ALL basins.** As every chain (bank topology + beam
   topology, ~0 shared edges) approaches feasibility it lands at ~900–985 d (d/leg ~1.5 = rank-2). Tighter
   maxwait gives MORE strands, not lower makespan. **Rank-1 (now 391–424 d) is a basin-REACHABILITY wall, not a
   search-effort gap** — the tight-phased basin is unreachable by feasibility-seeking methods. Also tried + reverted
   an ILS kick: extreme TIMING FRAGILITY (3-city relocation cascades 2→107 strands) — the solution is a knife-edge,
   rank-1 must be *constructed* with globally-coherent timing, not perturbed into.

## Leaderboard repricing (read-only fetch)

- **Ch2-medium: we LOST the rank-1 window while holding.** Our 189.10 bank was rank-1-grade when banked (live r1
  195.68); field moved to **186.27** → 189.10 now ranks ~2.
- **Ch2-large r1 dropped to 391.17** (TGMA; was 424.62) — rank-1 even further off.
- **Team HRI** (Honda colleagues, separate team): Ch2 small **r1 101.65**, medium **r3 192.11**, large **r4
  1028.59**. Our held banks beat HRI on medium and large; HRI owns small r1 (our floor 112.996).

## Tooling shipped

- `scripts/ch2_giant_completion_repair.py` (CLS modes: single/lns/cls; prefix-cached incremental retimer; cheap-slot).
- `scripts/ch2_analyze_solutions.py`, `scripts/ch2_node_analysis.py`, `scripts/ch2_beamfrag_constructor.py`.
- Search priors: `cache/ch2_node_features.json`, best seed `cache/ch2_seed_beam16.json`.
- **`/deepaudit <challenge>` slash command** (`.claude/commands/deepaudit.md`) — fires the deep single-prompt
  audit on a named challenge: scopes to that challenge's vault subtree, questions recorded results, runs the 4
  phases, proposes further exploration paths, records an E-node.

## State at session pause

Fleet: 4 CLS chains on Ch2-large rank-1 (2 bank-basin 1–2 strands, 2 beam-basin 7–8 strands) — all converging to
rank-2 reproductions (small upside: a sub-932 giant could marginally improve the rank-2 bank). Banks ALL HELD:
Ch2-large 932.53 (~r2), Ch2-med 189.10 (~r2 now), Ch2-small 112.996 (~r6), Ch1-traj 361014 kg. **Two open user
decisions: (1) submissions — medium degraded r1→r2 while held, field improving; (2) allocation — rank-1-large
decisively walled, untouched Ch1 levers (E-701 fleet #36, matching-II #35) likely higher total-points EV for the
final 3 days.** User directive standing: keep all 4 on rank-1, HOLD submissions.
