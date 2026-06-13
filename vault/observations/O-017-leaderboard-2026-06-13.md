---
id: O-017
type: observation
tags: [observation, leaderboard, reprice, ch1, ch2]
date: 2026-06-13
source: GraphQL api.optimize.esa.int (scripts/fetch_leaderboards.py --depth 11)
related: [[O-016-leaderboard-2026-06-12]], [[E-047-ch1-raan-argp-feasibility-refuted]], [[E-039-ch1-matching-evaluator-audit]]
---

# O-017 — Live leaderboard + 6-instance reprice (2026-06-13 02:34)

Our banks scored with the official-faithful evaluators; live r1 (and key
cutoffs) from GraphQL. Objectives: Ch1 matching = Σw (higher better); Ch1
trajectory fitness = −mass (more negative = more mass = better); Ch2 = days
(lower better).

| instance | our bank | live r1 | nearer cutoffs | est rank | verdict |
|---|---|---|---|---|---|
| Ch1 matching-i  | 33,338.18 | 33,555.61 | r3≈33,492–33,535 | ~r7–9 | EXHAUSTED — deep local opt, 66,660 exact Gurobi region re-opts found 0 gain (E-047 tick / matching-i agent) |
| Ch1 matching-ii | 72,204.29 | 73,714.03 | r2≈73,569–73,697 | ~r7+ | 2.05% gap (bigger than i's 0.65%) ⇒ realizable headroom; connected-region Gurobi-LNS launched (agent a29e2af0) |
| Ch1 trajectory  | −236,420.5 (236,420 kg) | −473,332.7 | r5 worst shown −372,729 | ~r10+ | far back; only the coherent impulsive-perfection + WSB model closes it (multi-week, low pts/hr) |
| Ch2 small  | 116.38 | 101.65 | r5≈111.76–111.79 | ~r7 | EXHAUSTED — DP floor, 4.6d above r5 cutoff |
| Ch2 medium | 192.90 | 195.68 | — | **RANK 1** (beats live r1 by 2.8d) | ultrafine retime defending; SUBMIT |
| Ch2 large  | 1013.29 | 424.62 | r2=1143.56 | **RANK 2** (beats r2 by 130d) | secure; r1 needs global TD-TSP (TGMA-class), low marginal pts |

## Repriced queue (ROI = expected points / est-hours, 4 cores, 17 days left)

1. **USER SUBMISSION of the 6 banks** — dominant unrealized value. medium=RANK 1
   and large=RANK 2 currently score 0 points (unsubmitted). User-gated;
   standing escalation.
2. **Ch1 matching-ii** (autonomous, IN PROGRESS) — the only instance where our
   bank sits at a >2% gap AND the strongest method (connected-region Gurobi
   ILP-LNS) is untried. Bounded ~1.5–2h. ×1 weight; a strict improvement that
   climbs ranks = a few points.
3. Everything else autonomous is EXHAUSTED (matching-i, small) or multi-week
   low-pts/hr (trajectory WSB, large global TD-TSP). Under NEVER-STOP these
   stay as bank-grinding / re-analysis fallbacks, not idle triggers.

Caveat: ranks are estimates from the top-11 depth; exact rank for banks below
the shown cutoffs (matching-i/ii, small, trajectory) not pinned but clearly
outside the top tiers.
