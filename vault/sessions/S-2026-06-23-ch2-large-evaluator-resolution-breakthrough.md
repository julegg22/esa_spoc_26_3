---
id: S-2026-06-23
type: session
tags: [session, ch2-large, evaluator-resolution, time-dependent-tsp, beam-search, audit, methodology, anti-oscillation]
date: 2026-06-23
participants: [JJ, Claude Code]
claude_model: claude-opus-4-8
commits: [9fd7bf0, 0c64a3e, 5ca2c01, 1fa6b6c, 135966d, 4fd075b, 880f717, 37efa67, 20c71e2, a56c717, 9f42199, aedd637, b606546, 2b74730, cd27ab9]
created_nodes: [[[E-709-ch2-large-audit]], [[E-710-ch2-large-time-aware-decomp]], [[C-033-fast-faithful-oracle]], [[C-034-time-aware-beam-narrow-window-tdtsp]], [[L-013-evaluator-resolution-phantom-wall]], [[M-general-commit-criteria-reproduce-reconstruct-trace]]]
---

# S-2026-06-23 — Ch2-large: the "wall" was the evaluator's resolution, not the problem

## Scope

A day that started by *closing* Ch2-large as a moonshot and ended by
*re-opening* it as a tractable rank-2→1 lever — because the second audit
probed the one axis the first one didn't: the **resolution of the
evaluator** the verdicts rested on. Trajectory tier-2 extended-tof sweep
ran in the background throughout (3 cores); all Ch2-large work used the 4th.
The day's lessons were then captured as concept/lesson/methodology notes and
the repo was brought to a clean reproduce/reconstruct/trace state.

## Chronological narrative

### Ch2-large deep audit (E-709) — concluded "genuine wall, moonshot"
User asked for a 4-phase deep audit of the large rank-1 gap (424 vs our 932
bank), on the premise that "there was ALWAYS a straightforward reason."
Five hypotheses, each **refuted with measurements**:
- adjacency under-sampled → 0/300 false negatives (graph correct);
- bank-order needs re-timing → 931 d, no collapse;
- urgency proxy (deadline vs degree) → deadline ordering *worse* (160/207
  vs min-arrival 367);
- a global static-cost TSP would beat greedy → **strands at 10/601**
  (OR-Tools GLS order, faithfully walked) — static solvers provably fail;
- LB → assignment relaxation 14.8 d (loose; makespan is 100 % time-coupling).
Verdict: no easy flaw; genuine time-dependent TSP; rank-1 all-or-nothing
(+1.78 pts); **recommend hold rank-2.** Rigorous — and, it turned out, wrong
about the root cause.

### User redirect: "develop the time-aware decomposition"
Rather than accept the moonshot, the user directed building the competitor's
time-aware paradigm, in parallel with the trajectory cores.

### E-710 foundation audit — the discovery
Per [[M-general-foundation-then-search]], validated the evaluator before
the search. Three positive-controlled probes:
- **M0b (table precision):** the cached 1d table is **100 % faithful**
  (200/200 cells verify), but a full faithful scan at **0.01 d** tof steps
  finds the cheap tof only **11 %** of the time — because the cheap-tof
  feasible bands are **~0.002 d wide** (median |true−stored| = 0.002 d).
- **M0c (epoch continuity):** cheap windows are **continuous & wide (~12 d**
  vs 1 d grid) → a cheap tof exists at essentially any departure.

**The discovery:** every prior faithful construction (greedy, shorttof_walk,
SA) scanned tofs at 0.01–0.05 d and was **blind to ~89 % of cheap edges**.
The "367 wall" and the dense-beam "overfit→1099 d" were largely **coarse-tof
artifacts**, not structural facts. (Anti-oscillation check applied: this is a
"real lever" claim → verified per-instance with M2 before concluding.)

### E-710 M2/M3 — the beam breaks the wall
Built the **fast-faithful oracle** ([[C-033-fast-faithful-oracle]]): table
proposes the (epoch, tof), one fine (≤0.0005 d) exact verify confirms it —
~100× cheaper than a full scan, no overfit. Wrapped it in a **time-aware
beam** ([[C-034-time-aware-beam-narrow-window-tdtsp]]) carrying an exact clock
per state with width-W global lookahead. Results:
- W=60: threaded **558/601 @ 283 d** (0.29–0.51 d/leg, at/under rank-1's
  0.404) vs greedy's 367 — **the wall gave way**, then stranded 43 short.
- W=120 first try crawled (exceptions fired every early step) → fixed to fire
  only on a near-stuck frontier; relaunched W=100 (running at session end,
  ~0.30 d/leg, tighter than W=60).
A complete tour on this trajectory extrapolates to ~300–380 d < rank-1 424 →
**rank-2→1 lever now open** (was priced a moonshot).

### Documentation + commit hygiene
- New concepts C-033, C-034; extended [[C-031-grid-quantization-mismatch]]
  with the "phantom wall" (online-evaluator) manifestation; lesson
  [[L-013-evaluator-resolution-phantom-wall]].
- Memory ([[ch2-large-time-ordering-wall]]) annotated: symptoms valid,
  root-cause verdict superseded ([[M-general-retraction-annotation]]).
- User codified the **commit criterion** (reproduce + reconstruct + trace);
  captured as [[M-general-commit-criteria-reproduce-reconstruct-trace]].
  Committed 19 previously-untracked source scripts, the E-673 orphan journal,
  the matching-ii bank; gitignored `cache/`; excluded run logs / `.bak`.
  Pushed; vault left clean.

## Decisions & state

- **Ch2-large reframed:** not a moonshot. The fine-tof time-aware beam is the
  active high-EV lever; if it closes the last ~43 cities under 424 d → stitch
  the 3×150 satellites, faithful UDP verify, guard-bank, **escalate for
  submission** (never auto-submit).
- **Trajectory** bank steady at 356,550 (rank 6; +16,179 to rank-5); tier-2
  extended-tof sweep still running, low-yield.
- Banks unchanged and unsubmitted (medium rank-1, large rank-2 still 0 pts
  until upload — user-gated).

## Methodological takeaways

1. **Audit the evaluator's RESOLUTION before accepting a "wall," not just its
   correctness.** Five experiments agreed because they shared one coarse-tof
   instrument — agreement was shared blindness, not truth (L-013).
2. **The cheapest high-information probe is often the one the audit skips —
   auditing its own measuring stick.** The gap here was ~10 lines of
   resolution, not a new algorithm.
3. **Table for recall, exact eval for precision** (C-033) breaks the
   accurate-vs-fast dilemma that had blocked every prior global attempt.
4. **Width buys tail access** in a time-aware beam (C-034): W>1 was the
   difference between stranding at 367 and threading 558+.

## Open threads → next session

- W=100 beam endgame (complete 601 < 424 d?); if it walls short, close the
  last cities via wider W / window-epoch clustering / tail-repair.
- On completion: satellite-stitch + official UDP verification + guard-bank
  large; escalate submission decision.
- Trajectory tier-2 assemble + idd re-opt on sweep completion.
