---
id: E-726
type: experiment
tags: [ch2, large, rank-1, audit, ultrathink, structure, short-tof, reframe]
date: 2026-06-26
status: ACTIVE — audit reframes rank-1 from "moonshot" to "complete the fast beam"; build launched
related: ["[[E-725-ch2-large-fast-faithful-evaluator]]", "[[E-723-ch2-large-bank-reproduction-audit]]", "[[ch2-large-time-ordering-wall]]"]
---

# E-726 — Ch2-large ultrathink audit: rank-1 is REACHABLE, not a moonshot (user-triggered)

User (2026-06-26): "How did we find 932d? Why couldn't we find a single OTHER similar solution? Moonshot? A
lonely basin? Lucky seed? It is simply not likely that despite all our attempts we have not advanced."

## Provenance of the 932d bank (subagent trace of git+vault)

ALL ~20 complete valid large solutions (2225d -> 932.53d) are **ONE topology**: built once, deterministically,
by **OR-Tools open-path ATSP on the STATIC cheap graph** (E-559, cost = static distance/DV, time-IGNORING),
then refined ONLY by timing (epoch-aware re-solve -> windowed-LNS [randomized, the one stochastic stage] ->
retime-DP). 932.53 = the timing FLOOR of that single basin (E-589). So "only one solution" = **we never built
a second topology**; not a lucky lonely hit.

## What the audit refuted (assumptions checked empirically with the faithful numba evaluator)

- **Component structure is real:** 0/120 satellite->giant "non-cheap" pairs are cheap under faithful numba.
  The 4 components [601,150,150,150] + 5-bridge structure HOLD. (Not an under-count artifact.)
- **Bank's TOFs aren't shortenable in place:** 16/60 long legs have a marginally-shorter cheap tof, total
  saving ~0d. The table's per-edge min-tof is correct (numba agrees, 0/50 disagreements).

## The decisive findings — rank-1 is structurally reachable

- **78% of giant edges have min-TOF ≤ 0.3 d** (the bank's 1.02 d/leg median was its CHOSEN legs, not the edge
  population). The **short-TOF subgraph (≤0.5 d) is STRONGLY CONNECTED: 1 component, 601/601 cities, full
  in/out degree.** A ~300 d giant traversal is structurally available → rank-1 (424 d whole-tour) is reachable.
- **We already FOUND the fast structure and mismeasured it as failure:** the time-aware beam (E-710) threads
  **558 cities @ 283 d = 0.51 d/leg** — rank-1 PACE. The cap is COMPLETENESS (558-575/601), NOT makespan.
- So **rank-1 = "complete the fast beam's last ~43 cities at pace," not "halve the 932 d bank."** A completion
  problem, far more tractable than a global 2× compression.
- **Caveat (real):** short-TOF windows are epoch-RARE (~6% of epochs open for a ≤0.6 d transfer). So a
  short-TOF order needs tight PHASING (arrive when the window is open) — the genuine TD-TSP difficulty. But the
  beam's 558@283d proves a well-phased short-TOF chain is findable for most of the giant.

## Why we stalled, precisely

(1) ONE topology, built static/DV (long-TOF), never a second. (2) Our search used the **epoch-sparse table**
(~6 windows/edge) → few options → corner-paint at 558-575. (3) We measured progress by completeness and read
the makespan-good-but-incomplete beam as "no progress."

## The lever / build

Re-run the completion search on the **faithful epoch-dense evaluator** (E-725 numba: same edges cheap at ~100×
more epochs → far more window options at the stranding frontier). Hypothesis: the extra windows break the
corner-paint cap and complete 601 at ~0.5 d/leg ≈ 300-400 d giant → rank-1. If it completes, greedy-retime +
OFFICIAL per-leg verify (max_revs=20) + stitch satellites + udp.fitness<=0 + guard-bank + ESCALATE (gated).

This is the pattern the user predicted: not a wall, but a **mismeasured result + wrong-foundation search**.
Corrects the "moonshot/lonely-basin" reads in [[ch2-large-first-bank-topology]] and this session's E-724/725
verdicts. Banks secure; nothing submitted.
