---
id: E-726
type: experiment
tags: [ch2, large, rank-1, audit, ultrathink, structure, short-tof, reframe]
date: 2026-06-26
status: ACTIVE — audit reframes rank-1 from "moonshot" to "complete the fast beam"; build launched
reframes: [E-721, E-722, E-723, E-724, E-725]
related: ["[[E-725-ch2-large-fast-faithful-evaluator]]", "[[E-723-ch2-large-bank-reproduction-audit]]", "[[ch2-large-time-ordering-wall]]", "[[M-general-root-objective-and-proxy-skew]]"]
---

> ↩ **This node REFRAMES a cluster** (E-721d/f/g, E-722, E-723, E-724, E-725) via ONE shared corrected premise
> — not five independent retractions. **Shared skewed premise P:** *"completeness (cities the beam threads)
> measures progress toward rank-1, so 575/601 is a wall and rank-1 means compressing the 932 d bank ~2×."*
> **Corrected P′:** *the time-aware beam already threads 558 @ 283 d = 0.51 d/leg = rank-1 PACE; the deficit is
> completeness only, and the short-TOF subgraph is strongly connected (601/601) — so rank-1 = COMPLETE the fast
> beam, a reachable completion problem.* Those nodes' DATA is valid; only the direction P implied was wrong.
> Convention + lesson: [[M-general-root-objective-and-proxy-skew]], [[M-general-retraction-annotation]].

# E-726 — Ch2-large ultrathink audit: rank-1 is REACHABLE, not a moonshot (user-triggered)

> ⚠️ **SELF-CORRECTION 2026-06-26 (E-726c/d, same day).** The structural findings below STAND (932 d = one
> static topology; short-TOF subgraph strongly-connected 601/601; rank-1 not structurally impossible). BUT the
> headline claim *"the time-aware beam is already at rank-1 PACE (558 @ 283 d = 0.51 d/leg)"* was itself an
> **evaluator-optimism artifact** — that 283 d came from the **sparse/optimistic TABLE**. A full **faithful**
> (numba, official-max_revs) W=200 retime of the best beam order (583 cities) gives d/leg climbing 0.29→**1.8**
> and the **tail strands 52** — i.e. ~bank pace, NOT rank-1 pace, and incomplete. So "we already found the fast
> structure, only completeness is missing" is WRONG: we have **not** found a faithfully-fast order; the table
> under-reported makespan everywhere. Net corrected verdict: rank-1 is **structurally reachable but NOT yet
> achieved** — it needs a genuine **faithful-evaluator search** (precompute the faithful epoch-dense windows →
> fast faithful beam / order-search), not "complete the existing beam." **Methodology:** this is the MIRROR of
> the proxy-skew lesson — I re-stated the *pessimistic* metric (completeness) in the root objective but trusted
> an *optimistic* evaluator (the table) without re-verifying the favorable number faithfully. The discipline
> must cut both ways: **re-verify FAVORABLE numbers under the faithful/official evaluator too, not only
> unfavorable ones.** See [[M-general-root-objective-and-proxy-skew]] (extended).

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

## E-726b/d result (faithful beam on the precomputed window table) — honest

Built the faithful epoch-dense short-tof window table (E-726d, 58555 edges) and ran the pure-lookup faithful
coverage beam on it. **Result: threads ~140 cities at d/leg 0.40-0.43 (RANK-1 PACE, FAITHFULLY confirmed),
then strands at ~191** — and expanding the precompute top-50→top-120 did NOT help (193→191). So the cap is
**time-PHASING**, not edge coverage: the rare (~6%-open) short-tof windows can't be globally phased by a
greedy/coverage beam (corner-paint). Net: short-tof rank-1 PACE is real (the key positive), but the greedy
beam can't COMPLETE 601 at that pace; neither can the table beam (reaches 575 only by spending long-tof edges,
at table-optimistic makespan). **The remaining hard problem is the genuine TD-TSP: a global PHASED ordering of
all 601 on short-tof edges.** Enablers built (faithful evaluator + window table); next lever = LKH/Concorde on
the faithful short-tof cost (the competitor's inferred method, GLKH available from E-718), or a metaheuristic
that optimizes phasing globally rather than greedily. Not solved by greedy construction.

## Audit #3 (user: "why never a complete solution?") — retimer was long-tof-blind; LKH order genuinely TD-infeasible

User pressed on the central worry: we have a complete 932d bank but NO method this session threads even 400.
Findings: (1) **Our faithful precompute was short-tof-only (TOF_HI=1.3d) but the bank uses tof up to 6.71d (17%
of legs >1.3d)** — so every faithful short-tof method was STRUCTURALLY unable to complete. (2) **Our RETIMER
was long-tof-blind** (fine-scan med±0.8) — it stranded the bank's OWN order 12x; fixed to full-tof -> bank
order now threads **598/601 (3 strands = satellite gaps), makespan 1104d** (near-reproduces the bank; my
earliest-arrival retime vs the bank's timing-DP gives 1104 vs 932). So we CAN reproduce the bank. (3) BUT the
static short-tof **LKH order is genuinely TD-INFEASIBLE: 206 strands even with the fixed retimer** (not an
artifact) — the static min-tof order doesn't phase. This is the real static->TD gap; the epoch-aware iterated
LKH (E-726g) is the fix-attempt but E-562's analogous table-iterate FLOORED at 932. **Net: the bank recipe
(full-tof OR-Tools + epoch-aware iterate + timing-DP) reproduces ~932d=rank-2; rank-1 (424d) = the global
PHASED short-tof TD-TSP remains the genuine unsolved hard problem.** The repeated optimism->refutation was, in
EVERY case, a partial/optimistic evaluator (table makespan, short-tof windows, long-tof-blind retimer).

## Comprehensive method exhaustion (2026-06-27) — rank-1 walls at rank-2 across ALL standard TD-TSP approaches

> 🔧 **PARTIAL TOOL-ARTIFACT — propagated from [[A-2026-06-27-broken-tool-retry-queue]] (2026-06-27).** Two rows
> below are NOW-FIXED tool artifacts, NOT genuine walls: (a) **"iterated LKH DIVERGES"** = the T5 BIG-penalty
> bug — FIXED (soft penalty), now CONVERGES (163→153…); (b) **"LNS/insertion cascade"** = largely the broken
> evaluator (T1 sparse table + T2 long-tof-blind retimer) failing to find windows — to be RE-RUN on the faithful
> evaluator (the planned LNS/SA rank-1 attack). So "ALL standard approaches wall" is OVERSTATED: the LNS family
> is **untried with correct tools.** GENUINE walls that stand: static-LKH TD-infeasibility, time-expanded GTSP
> intractability, the short-tof phasing cap.

After the retimer fix, ran the remaining levers on an honest evaluator:
- **Static LKH (full-tof, bank's static-graph step):** 438/601, 163 strands — TD-infeasible ALONE.
- **Epoch-aware iterated LKH (my impl):** DIVERGES (it0 163 -> it1 461 strands) — buggy re-cost (INF on
  edges lacking a window at a bad-retime epoch). E-562's careful version converged but floored ~932=rank-2.
- **GRASP (faithful short-tof):** caps ~239 (phasing).
- **Faithful short-tof beam:** ~191. **Time-beam / order-search:** rank-2 floor or incomplete.
- **Time-expanded GTSP (E-718):** intractable (near-OOM, no result).
- **The bank recipe (full-tof OR-Tools + E-562 iterate + timing-DP):** the ONLY thing that produced complete
  valid orders -> ~932d = rank-2 (already banked).

**Verdict:** rank-1-large (424d, needs the giant in ~half the bank's time = a globally PHASED short-tof tour)
is genuinely research-grade — every standard method either caps incomplete (~200-240), is TD-infeasible
(static LKH), floors at rank-2 (E-562 iterate), or is intractable (time-expanded GTSP). The session's durable
wins: reframed the problem (structurally reachable, not a moonshot), built the faithful evaluator + window
table + fixed the long-tof-blind retimer (bank reproduces at 3 strands), and named the recurring root cause
(optimistic/partial evaluators) in methodology. Rank-2 (932.53) is secure and reproducible; rank-1 is the
competitor's hard-won TD-TSP, not crackable by our standard toolkit in this window.
