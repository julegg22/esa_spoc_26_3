---
id: E-760
type: experiment
status: analyzed — method VALIDATED, small bank 112.996 -> 111.96 (feasible); residual to rank-1 is L4
date: 2026-07-02
level: L6                      # the RE-RUN swaps the solver (GLKH -> exact-DP+LNS) at the same lever
wall_level: L4                # residual gap to rank-1 (100.4) is the encoding, after L7 was ruled out
code: scripts/ch2_small_order_search.py
commit: 78b1a8d                # validated 111.96 run at this script state (backfilled per _prov discipline)
assumes: [ENC-grid, SOLVER-gtsp-exc, EVAL-lambert, MODEL-official-feas]
related: ["[[E-746-ch2-small-time-expanded-gtsp]]", "[[assumptions]]", "[[M-general-abstraction-ladder-audit]]", "[[M-general-assumption-provenance-and-invalidation]]"]
---
# E-760 — Ch2-small: exact-DP + LNS validates the joint window-indexed lever GLKH walled on

**Result.** `ch2_small_order_search.py` (exact continuous-time labeling DP that enforces ≤5 exceptions
*natively* + or-opt/2-opt LNS over the order, on the pre-warmed 975-edge window cache) finds an
OFFICIAL feasible tour **111.960 d**, beating the bank **112.996 d** by **1.036 d** (independently
re-verified: `kt.fitness` on `easy.kttsp` n=49, `is_feasible=True`, viols [0,0,0,0]). Banked.

**Why this matters — the RE-RUN.** E-746 filed the small joint sequence+epoch lever **CLOSED**
because GLKH cannot express the ≤5-exception constraint (`SOLVER-gtsp-exc`, L6). That was a *tool*
wall mis-read as lever death (`doc_lessons.md` F2). The abstraction-ladder audit reopened it:
- **R2** — a tool wall is an L6 fact → swap the solver, don't abandon the lever.
- **R3** — the sibling **medium** engine's exact-DP enforces ≤5 natively → it *is* the fix.
- **R4** — GLKH's relaxed run hit 75.2 d ≪ 100.4 d → the structure *contains* sub-rank-1 tours; the
  gap was constraint-handling, not search.
So `ENC-grid` (L4) + `SOLVER-gtsp-exc` (L6) were flipped to REFUTED in the register and queued
**RE-RUN**; this experiment *is* that RE-RUN, and it beats the bank — exactly what GLKH could not do.

**Ladder sweep on the plateau.** Best 111.96 was found at it244 and never improved over 3 M iters.
Three independent configs — DP-on-ultrafine (112.996), exact-DP+LNS/or-opt (111.96), exact-DP+LNS/2-opt
seed 99 (111.96) — converge at ~112. That **rules out L7 (operators/basin)** by multi-config
convergence. Per **R1**, the residual gap to rank-1 (100.4, −11.5 d) is named at **L4 (encoding)**:
the cheap-restricted / 8 d-tof / TQ=0.05 representation cannot represent the rank-1 tour. Parked as a
research-grade L4 rebuild (finer TOFMAX/TQ, wider edge set); lower EV than graduating the validated
method to medium/large.

**Tooling lessons (caught by instrument-before-trust, `doc_lessons.md` F7).** (a) the script's success
gate carried *medium* defaults (`best_off=189.10`, `TAG=m`, threshold 186.27) — fixed to the small
bank/thresholds; (b) with an empty cheap-restriction the unrestricted moves lazy-scanned dv>600 edges
(~7.5 s each) and the search stalled at it0 — fixed by restricting moves to the 975 precomputed usable
edges (dv≤600 from `edges_small.npz`). Both fixed before wasting the run.

**Bank impact.** `solutions/upload/small.json` 112.996 → 111.960 (feasible, re-verified; `.bak_112996`
kept). Not submitted (post-challenge research; user-gated).

**Next.** Graduate the method to Ch2-medium (reorder toward 172; engine + 506 MB cache ready) — E-761.
