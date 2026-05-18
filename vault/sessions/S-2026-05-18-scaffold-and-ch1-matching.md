---
id: S-2026-05-18
type: session
tags: [session]
date: 2026-05-18
created: 2026-05-18
duration_hours: ~4
participants: [JJ, Claude Code]
claude_model: claude-opus-4-7[1m]
commits: [cc73aa8, 42820c5, 1091fc6, 9c56837, efa7a68, 5ecabbf, 3a4e2ca, 87e5bb5, 86ebe22, 1bdd9dc]
created_nodes: ["[[Q-001-rank3-each-regular-instance]]", "[[H-001-ch1-matching-mip]]", "[[H-002-ch1-trajectory-greedy]]", "[[H-003-ch2-small-lambert-metaheuristic]]", "[[H-004-ch1-matching-mip-lns]]", "[[H-005-ch1-matching-coop-mip-lns]]", "[[H-006-ch1-matching-exact-polish]]", "[[E-001-ch1-matching-first-attempts]]", "[[E-002-ch1-matching-i-mip-lns-campaign]]", "[[E-003-ch1-matching-i-coop-mip-lns]]", "[[E-004-ch1-matching-i-exact-polish]]", "[[E-005-ch1-matching-ii-coop-mip-lns]]", "[[T-001-ch1-matching-needs-strong-search]]", "[[T-002-mip-lns-family-validated-but-plateaus]]", "[[T-003-diminishing-returns-need-exact-polish]]", "[[T-004-ch1-matching-ceiling-pivot]]", "[[L-001-greedy-localopt-and-suppressed-solver-log]]", "[[O-001-spoc4-problem-grounding]]", "[[O-002-leaderboard-2026-05-18]]", "[[O-003-ch1-trajectory-data-structure]]"]
---

# S-2026-05-18 — Scaffold rebuild + Ch1 matching campaign

## Scope

Fresh-start scaffold rebuild (inherited docs referenced a missing
prior campaign), full grounding, frontier bootstrap, and the
complete Ch1-matching (beginner) campaign through to a banked
result and a pivot decision.

## Key decisions

- **Fresh-start scaffold** (user): built `_templates/`, node dirs,
  `open-paths.md`/`frontier.base`, scripts/solutions stubs, draft
  `environment.yml`; corrected inherited dangling-ref docs.
- **Root goal reframed** to rank-3 on each *regular* instance
  (Ch3 deferred) — user directive; GOALS.md §1.
- **Conservative + parallelise** + **ask-but-never-stall** captured
  as persistent prefs in [[user]] (user directives).
- **Ch1-matching exact line closed**: greedy→MIP-LNS→coop→polish
  ladder asymptotes ~33 338 (99.6 % rank-3); no Gurobi (user) ⇒
  rank-3 infeasible for us. Banked matching-i ≈rank-6, matching-ii
  ≈rank-5 (≈11 pts). **Pivot to H-002** (Ch1 trajectory) — user
  approved. Stop-rule: clean halving asymptote ≥2 gens short ⇒
  pivot, don't tune ([[T-004-ch1-matching-ceiling-pivot]]).
- **Decisions taken autonomously** when user delayed (per
  ask-but-never-stall): method=MIP-LNS, kill dominated probes,
  focus-not-diversify, child promotions.

## Soft knowledge

- HiGHS (open-source) cannot crack 25k/92k weighted 3-D matching to
  rank-3; competitors (fcmaes/Team HRI/DIAG) almost certainly use a
  commercial solver. Small field (4–8 teams/instance) — top-3 is
  realistic where method exists.
- MIP-LNS (destroy → exact sub-solve) is the key operator that
  escapes the provable greedy local optimum; cooperation + adaptive
  destroy + warm-start each add diminishing increments.
- Git: this repo's account key is `~/.ssh/id_ed25519` (pinned via
  `core.sshCommand`); `id_rsa` is a deploy key for `esa_spoc_26_2`.
- Tooling gotcha (L-001): never suppress a long solver's log /
  always harness-capture — silent runs killed observability twice.

## Artefacts touched

10 commits (cc73aa8…1bdd9dc, all pushed). `src/esa_spoc_26/
ch1_matching.py` (greedy / ejection / mip_lns / coop / polish /
parallel runners). `solutions/upload/matching-i.json` (33 338),
`matching-ii.json` (72 018) — valid feasible, ≈11 pts banked.
Q-001; H-001..H-006; E-001..E-005; T-001..T-004; L-001;
O-001..O-003.

## Open threads

- **H-002 (Ch1 trajectory) is the active branch** — needs the BCP
  transfer-cost build (heyoka): per-(e,l) Earth→Moon ΔV → m_l, ΔT;
  reuse the `ch1_matching` MIP-LNS on the discounted-mass matrix.
  Design fork (user's BCP strength): transfer-model fidelity
  (cheap analytic/Lambert vs full BCP) — proposed cheap-first.
- Ch2 (H-003 small) + Ch3 untouched.
- Revisit Ch1 matching only if a Gurobi/academic licence appears
  (would supersede T-004).
- Session-end cascade check (M-017/M-018): no critical M / blocker
  L on foundational code introduced; L-001 is a design constraint,
  not an invalidating bug → no cascade. Branch pivoted cleanly
  (T-004 stop-rule) — M-018 step-back satisfied.
