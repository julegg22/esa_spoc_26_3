---
id: OPEN-PATHS
type: frontier
updated: 2026-05-20
tags: [frontier]
---

# Frontier — the single list of "what we could do next"

> [!important] Single frontier (META.md §2)
> This is the **only** list of candidate next moves. Ideas living in
> chat do not exist. Selection policy: pick the open H maximizing
> `ROI = expected_points / max(estimated_effort_h, 0.25)`; tie-break
> on time-to-first-signal, then diversity, then unblocking (META.md §5).
> Reprice after every experiment and log the re-pricing below.

## Live view

![[frontier.base]]

## Selection (2026-05-18)

Bootstrapped under [[questions/Q-001-rank3-each-regular-instance|Q-001]].
ROI = expected_points / max(estimated_effort_h, 0.25).

### Open (status: open) — at most one active per compute stream (§2)

| H | instance | expected | est. h | ROI | note |
|---|---|---|---|---|---|
| H-003 polish | Ch2 small | +2–4 | 4 | 0.75 | reduce 145.8d → 112d via 2-opt + multi-seed insertion; topk running |
| H-007 (Ch2 medium) | Ch2 medium | 8 | 12 | 0.67 | reuse find_transfer + cluster-insertion pipeline; same structure (Q6 confirmed pending) |

(Ch1 matching banked ≈11 pts. **Ch2 small banked 145.80 d = ~3–5 pts** via E-022 find_transfer + cluster-insertion. H-002 paused.)

### Closed

| H | verdict | result |
|---|---|---|
| [[hypotheses/H-001-ch1-matching-mip\|H-001]] | **refuted** | cheap MIP/greedy/LNS ~11–13 % short ([[takeaways/T-001-ch1-matching-needs-strong-search\|T-001]]) |
| [[hypotheses/H-004-ch1-matching-mip-lns\|H-004]] | **refuted (near-miss)** | parallel MIP-LNS → 33134 = 99.0 % R3 (≈rank-7) ([[takeaways/T-002-mip-lns-family-validated-but-plateaus\|T-002]]) |
| [[hypotheses/H-005-ch1-matching-coop-mip-lns\|H-005]] | **refuted (near-miss)** | coop+adaptive → 33320 = 99.56 % R3 (≈rank-6) ([[takeaways/T-003-diminishing-returns-need-exact-polish\|T-003]]) |
| [[hypotheses/H-006-ch1-matching-exact-polish\|H-006]] | **refuted (ceiling)** | polish → 33338 = 99.6 % R3; HiGHS family exhausted, no Gurobi → pivot ([[takeaways/T-004-ch1-matching-ceiling-pivot\|T-004]]) |
| [[hypotheses/H-002-ch1-trajectory-greedy\|H-002]] | **analyzed — paused** | pipeline proven (E-008) but no positive-mass transfer; global-trajopt problem; timeboxed per user ([[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem\|T-005]]) |

### Drafts (priced siblings, §16)

| H | instance | expected | est. h | ROI | note |
|---|---|---|---|---|---|
| C-B | Ch1 matching | 5 | 6 | 0.8 | parallel SA/Tabu (only if Ch2 secured) |
| H-002 revival | Ch1 trajectory | 14 | 20+ | 0.7 | global Sun-assisted trajopt (T-005); only if Ch2 secured |

*Children C-A/C-B/C-C are candidates (not yet H-files) — committed
after the user picks (META.md §6). Expectations cut per [[user]]
*Conservative expectations*.*

## Narrative log — the frontier has history (§5)

- **2026-05-20 (H-003 banked at 143.79 d after 2-opt polish; pipeline validated)** — After
  E-018 → E-021 chained refutations of discrete CP-SAT (single-window,
  joint (td, tof), 3-mode per-arc — all proven INFEASIBLE), the
  breakthrough came from re-reading the official `find_transfer`
  helper: it returns the EARLIEST tof at fixed t_start where Δv ≤ thr,
  inverting the precompute target. Parallel `greedy_findxfer` over 49
  starts (mp.Pool, 4 workers) → best partial = 45 legs from start=34,
  missing the 3-node small cluster {17, 11, 4}. Cluster-insertion LNS
  (46 positions × 6 orderings) inserts the small cluster mid-tour via
  two 540–576 m/s exception bridges → **first banked Ch2 small at
  makespan 145.80 d, 4 of 5 exceptions used**. Subsequent 2-opt polish
  (two 25-min rounds, one swap per round, converged) →
  **143.79 d**. Ratio to rank-3 (111.76): 1.286
  ⇒ likely rank 6–10 (~3–5 pts). E-022, polish; commits up to 741fdca.
- **2026-05-19 (H-002 timeboxed→paused; pivot to Ch2 H-003)** — Five
  shooting iterations (E-006..E-011) + one timeboxed pygmo global
  attempt: validation pipeline fully proven (E-008, banked asset)
  but no positive-mass transfer — the binding difficulty is global
  low-ΔV Sun-assisted trajopt
  ([[takeaways/T-005-ch1-advanced-is-a-global-trajopt-problem|T-005]];
  frame/Moon-motion verified bit-exact, *not* the bug). Per user ROI
  decision, **H-002 paused**, **H-003 (Ch2 small) promoted active**.
  Ch2 grounded ([[observations/O-005-ch2-kttsp-official-udp|O-005]],
  [[concepts/C-006-lambert-problem-and-orbital-tsp|C-006]]):
  time-dependent orbital ATSP, rank-3 small ≤ 111.76 d.
- **2026-05-18 (H-006 closed refuted; Ch1-matching line closed; pivot to H-002)**
  — Exact-polish added only +18 (33320→**33338**, 99.6 % R3) =
  terminal HiGHS-family ceiling, below rank-5. User: no Gurobi →
  **Ch1-matching rank-3 infeasible for us**. Decision (user-approved):
  bank `matching-i` ≈ rank-6 (~5 pts), run `matching-ii` (campaign
  running), **pivot frontier to H-002 (Ch1 trajectory greedy)** —
  higher ROI, rank-3 greedy-reachable (Team HRI), user's BCP
  strength. Stop-rule learned ([[takeaways/T-004-ch1-matching-ceiling-pivot|T-004]]):
  clean halving asymptote ≥2 gens short ⇒ pivot, don't tune.
- **2026-05-18 (H-005 closed refuted; H-006 opened; Gurobi escalated)**
  — Coop+adaptive MIP-LNS → `matching-i` **33320 = 99.56 % rank-3**
  (≈rank-6, ~5 pts; beat H-004's 33134 but missed rank-3 and the
  rank-5 fallback). Diminishing-returns ladder confirmed
  ([[takeaways/T-003-diminishing-returns-need-exact-polish|T-003]],
  [[experiments/E-003-ch1-matching-i-coop-mip-lns|E-003]]). Promoted
  **H-006 exact-polish** (warm-start 33320, big sub-MIPs, 1500 s,
  running). **Escalated to user: Gurobi licence?** — commercial
  exact solver is the realistic top-field method for the last
  0.44 %; pivot-to-H-002 is the no-Gurobi fallback.
- **2026-05-18 (H-004 closed refuted; H-005 opened)** — Campaign:
  parallel MIP-LNS → `matching-i` **33134 = 99.0 % rank-3** (≈rank-7,
  *scores ~4 pts* — first banked progress). Refuted the 600 s
  prediction (plateau ~1 % short, tight isolated basins,
  [[takeaways/T-002-mip-lns-family-validated-but-plateaus|T-002]],
  [[experiments/E-002-ch1-matching-i-mip-lns-campaign|E-002]]). First
  campaign died silently (broken redirect — L-001); relaunched
  harness-managed + heartbeats. Promoted child **H-005
  (cooperative+adaptive MIP-LNS)**, campaign running 1200 s. One
  silent-fail lesson reinforced; focus held on Ch1 matching.
- **2026-05-18 (H-004 opened: C-A validated)** — Decision made on
  own judgement ([[user]] *ask-but-never-stall*): committed **C-A
  parallel MIP-based LNS as H-004 (open)**. Probe (70 s, 1 thread)
  escaped the greedy optimum: 29792 → **32958 = 98.5 % of
  `matching-i` rank-3**. C-C (long tuned exact) killed as dominated;
  4 cores reallocated to the H-004 campaign (4 workers, 600 s),
  running. Breadth call: **focus** (finish the near-win) over
  diversify. C-B / H-002 / H-003 deferred drafts.
- **2026-05-18 (H-001 closed: refuted)** — E-001: default HiGHS
  (79 % R3, 122 % gap), greedy (89 %/88 %), naive+ejection LNS
  (0 improvement — greedy is a provable hard local optimum,
  [[lessons/L-001-greedy-localopt-and-suppressed-solver-log|L-001]]).
  Cheap methods do not clear Ch1 rank-3. User directive: parallelise,
  expect hard, be conservative (→ [[user]], [[takeaways/T-001-ch1-matching-needs-strong-search|T-001]]).
  Valid greedy baselines banked (`solutions/upload/`). Frontier
  repriced down. **Strategic fork to user**: child C-A/C-B/C-C
  (parallel MIP-LNS / parallel metaheuristic / long tuned exact) —
  none committed pending user choice (discuss-before-commit).
- **2026-05-18 (kickoff)** — Grounding committed
  ([[observations/O-001-spoc4-problem-grounding|O-001]],
  [[observations/O-002-leaderboard-2026-05-18|O-002]]). GOALS.md §1
  reframed to per-instance rank-3 (user directive). Frontier
  bootstrapped under [[questions/Q-001-rank3-each-regular-instance|Q-001]]:
  **H-001 (Ch1 matching MIP) promoted to open** — ROI 8.0, exact,
  fastest signal, "establish baseline early" (META.md §2).
  H-002 (Ch1 trajectory greedy) + H-003 (Ch2 small) committed as
  priced draft siblings (§16). Next: run E-001 (HiGHS MIP).
- **2026-05-18** — Repo instance `esa_spoc_26_3`. Methodology
  scaffold (`CLAUDE.md`/`GOALS.md`/`META.md`) and tier-1 docs were
  inherited from a prior mature campaign whose vault nodes
  (H/E/T/C/M/L/O, templates, scripts, frontier) were absent. User
  directed a **fresh-start scaffold rebuild**: created `_templates/`
  (10 node templates), node directories, `open-paths.md`,
  `frontier.base`, `scripts/`, `solutions/upload/`, draft
  `environment.yml`. Frontier is empty; next step is the
  bootstrap discussion (no `H-NNN` committed without it).
