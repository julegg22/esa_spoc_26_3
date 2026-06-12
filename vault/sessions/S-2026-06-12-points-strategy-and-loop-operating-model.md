---
id: S-2026-06-12
type: session
tags: [session, strategy, campaign, loop, scoring, submission]
date: 2026-06-12
participants: [JJ, Claude Code]
claude_model: claude-opus-4-8
commits: []
created_nodes: []
---

# S-2026-06-12 — Points-maximization strategy + autonomous-loop operating model

## Scope

Journal the strategic reframe that now governs the whole campaign —
from a "rank ≤3 on every instance" gate to **maximizing total SpOC4
points** — and the matching changes to how the autonomous `/loop`
operates (compute-resource discretion, submission as a first-class
decision, points-priced ROI). This consolidates guidance that until
now lived scattered across `loop-state.md` tick entries and memory.

## Key decisions

### 1. Objective: maximize overall score, not a rank-3 gate (user, 2026-06-11 17:50)
The root goal is no longer "top-3 on all instances." It is to
**maximize global points = Σ over the 6 mandatory instances of
(11 − rank) × weight**, with weights **easy ×1, medium ×4/3,
hard ×(4/3)²≈1.778**. *Every* top-10 rank scores — rank 7→4 on a hard
instance is +5.33 pts, just as real as a podium move. Per-problem
maxima: easy 10, medium 13.33, hard 17.78.
- **Why:** the official scoring (reference/SpOC4 README §Scoring) rewards
  all top-10 placements; a rank-3 gate left large amounts of points on
  the table (e.g. a hard instance sitting at rank 6 is worth 8.89 pts
  that the old framing treated as "not done"). Maximizing points is the
  true competition objective.
- Supersedes memory `submission-policy-rank3` and the old `index.md`
  goal line. Instance→weight map: Ch1 matching-i = easy, matching-ii =
  **medium** (Ch1 is two-easy-plus-one-hard? — see note below), trajectory
  = hard; Ch2 small = easy, medium = medium, large = hard.

### 2. Submission is now a first-class, time-sensitive decision
**Unsubmitted banks score ZERO.** All six banks currently sit
unsubmitted ≈ 46.55 pts of latent score that the leaderboard reads as 0.
- **Why:** points only exist once uploaded. With banks this strong, the
  single highest-value action on the board is *submitting what we
  already have*, not squeezing more compute.
- **Constraint unchanged:** submissions remain **user-gated** — the
  agent never writes to the internet; JJ uploads JSON via the Optimise
  web UI. The agent escalates the submit decision, never performs it.
- Old info-leak caution (don't reveal methods early) now yields to the
  hard fact that a final pre-deadline submission is mandatory for *any*
  points. Recommend a planned submission window before 2026-06-30 AoE.

### 3. ROI is now priced in expected POINTS per invested hour
Queue repricing uses expected Δpoints / est-hours (analytics + dev +
compute) given remaining days and 4 cores — not raw days/kg improvement.
- **Why:** a 12-day medium build worth +1.33 pts must be weighed against
  a 1-hour matching push worth the same, and both against the ~46.55 pts
  sitting in unsubmitted banks. Points/hour makes those comparable.
- Consequence: rank-gap *structure* dominates. Improving a bank that is
  already rank 2 yields **zero** points unless it crosses into rank 1
  (e.g. Ch2 large 1048.98d → must more-than-halve to <424.62d for +1.78).

### 4. Full compute-resource discretion (user, 2026-06-12)
The agent may **kill, reallocate, and relaunch any process freely** to
advance the rankings, with no per-kill escalation.
- **Why:** the earlier "no kills — let processes finish" instruction
  (2026-06-11 17:00) was *contextual*, not a general rule. Treating it as
  standing wasted ~7.5h on a deadlocked E-554 left running past its
  budget at 0% CPU. Captured in memory `feedback-compute-resource-discretion`.
- **Still gated:** submissions and non-compute destructive/irreversible
  actions. Guarded-banking discipline is untouched.

### 5. Banking safety hardened: agents never write the bank
New heavy compute (e.g. the E-563 medium build) writes candidate
solutions to `/tmp` only; the main loop guard-banks itself after an
independent official re-score.
- **Why:** discovered a latent landmine — `ch2_e537_large_cluster_lkh.py`
  still bank-guards on a hardcoded `fit[0] < 1200` (from when the bank was
  1536d); with the bank now 1048.98d it would *clobber* with anything
  <1200d. Guard must always be "strictly better than the *current* bank,"
  so the safe pattern is: agent proposes → loop verifies & banks.

## Loop operating model (current shape)

The autonomous `/loop` self-paces (dynamic mode), waking on a fallback
heartbeat or a background-task notification. Two tiers:

- **Cheap tick (every wake):** health-check running runs (process alive,
  log <30min fresh, sane iteration rate, SA/ALNS accepted>0 in 1h,
  DP/walk feasibility sane); on any tripwire, diagnose root cause *now*,
  fix, relaunch. Note bank deltas. If cores idle, launch top of the
  points-priced queue.
- **Deep review (on trigger only — run finished/banked, stalled 2+ ticks,
  tripwire fired, or >12h since last):** refetch the live leaderboard
  (read-only GraphQL `api.optimize.esa.int`), recompute gaps on all 6
  instances, reprice the queue by points-ROI, apply the methodology
  triggers (instrument >30% rejects; audit the evaluator before blaming
  search; evaluator metric must equal the official scorer), update the
  vault and a concise user status.
- **Escalate to the user only for:** submissions, non-compute destructive
  actions, or an empty positive-EV queue.

State lives in `vault/loop-state.md` (reverse-chronological tick log,
updated every iteration).

## Current standing (banks vs live board; all UNSUBMITTED = 0 pts now)

| Instance | Bank | Would rank | Pts | Next rank up |
|---|---|---|---|---|
| Ch2 large (H) | 1048.98 d | 2 | 16.00 | r1=424.62 (needs >2× cut) |
| Ch2 medium (M) | 228.97 d | 4 | 9.33 | r3=216.95 (−12d; new code) |
| Ch1 trajectory (H) | 236,420.5 kg | 6 | 8.89 | r5=372,729 (+136k; unreachable near-term) |
| Ch1 matching-ii (M) | 72,200.7 | 7 | 5.33 | r6=72,327 (+127; tapered) |
| Ch2 small (E) | 116.37 d | 6 | 5.00 | r5=111.79 (−4.6d; DP-fine exhausted) |
| Ch1 matching-i (E) | 33,338.2 | 9 | 2.00 | ceilinged |
| **TOTAL** | | | **≈46.55** | (currently 0 — nothing submitted) |

## Soft knowledge

- The cheap-improver queue is **empty** across all 6 instances:
  matching-i ceilinged, matching-ii tapered short of rank-6, trajectory
  WSB exhausted for *points* (gains 0 ranks below r5), Ch2 medium/small
  permutation search structurally exhausted. Remaining levers are
  multi-hour *new-code builds*, now authorized under the compute-discretion
  directive.
- A "ceiling" can be a **contention/cold-start artifact**, not a true
  optimum: matching-ii's apparent 6-method plateau broke (+163 kg) under a
  warm-started cooperative LNS on *uncontended* cores.
- The proxy⊥reality trap recurs: a fixed-reference-time tof proxy is
  orthogonal to the chronological-walk cost. Epoch-aware re-costing is the
  lever that broke Ch2 large (2225→1049d) and is being transferred to
  medium (E-563, in flight this session).

## Artefacts touched

- `vault/loop-state.md` — standing-directive header rewritten (compute
  discretion); tick log 06:09→09:00.
- `vault/index.md` — goal + status refreshed to the points objective.
- Memory: `feedback-compute-resource-discretion`,
  `submission-policy-rank3` (marked superseded → points objective).
- `scripts/ch2_e563_medium_epoch_aware.py` — new medium build (agent
  a4cf2add), candidate-to-/tmp only.

## Open threads

- **Pending submission** of the 6 banks (~46.55 pts) — user-gated; the
  dominant action.
- **E-563 medium build** in flight: best perm 199.57d on the (pessimistic)
  v2 proxy; official fine-timed verdict pending → guard-bank if feasibly
  <228.9748d.
- Next points-priced targets after medium: Ch2 small epoch-aware attempt
  (r6→r5, +1 pt); Ch2 large only matters if it can more-than-halve.
- **Note to verify at next leaderboard fetch:** the Ch1 weight map —
  loop-state at one point flagged matching-ii as easy ×1 (Ch1 = two easy +
  one hard) rather than medium ×4/3. Confirm the A-category field via the
  API before trusting matching-ii's 5.33-pt figure.
