---
date: 2026-06-10
tags: [methodology, autonomous-agents, monitoring, loop-design, general]
scope: GENERAL — applies to any long-running agent loop, NOT specific to ESA SpOC
status: distilled from empirical experience (E-550 dead-run incident, 2026-06-10)
---
# Designing autonomous-loop directives: two-tier cadence + persistent state

How to formulate the standing directive for an autonomous agent loop
(e.g. Claude Code `/loop`) that babysits long-running compute
experiments. Distilled from a concrete failure and three directive
iterations in one day.

## The incident that forced the redesign

E-550 (Ch2 medium walk+SLSQP ALNS, 4 chains × 24 h) ran for **7 hours
on all 4 cores with `accepted=0`** — its SA acceptance was
*mathematically impossible*: the baseline was the bank's DP-evaluated
makespan (228.97 d) while candidates were scored by a walk+SLSQP
evaluator whose floor for the very same permutation is ~274.7 d. Every
delta was +40–70 d; exp(−Δ/T) ≈ 0. The process was alive, the log was
fresh, the per-iteration pipeline metrics looked healthy (walk_ok 35 %,
polish_feas 17 %) — and the run was structurally dead from minute one.

Nobody noticed until the user asked for status. The loop directive at
the time said "analyse experiments for opportunities or bugs" — which
in practice meant a full strategic re-analysis on every wake and *no
specific obligation to check whether running jobs could even succeed*.

## Directive evolution (three versions in one session)

**v1 — aspirational monolith.** "Analyse experiments for missed
opportunities or bugs, compare with rankings, plan best experiments,
stop at rank 1 everywhere." Problems:
- Every wake pays for a full deep analysis even when nothing changed.
- No health-check obligation → the E-550 class of failure is invisible.
- Stop condition ("rank 1 in all") likely unreachable → loop never has
  a defined exit, and there's no escalation rule either.
- All state lives in conversation context → re-derived from scratch
  after every context compaction (expensive, drift-prone).

**v2 — tripwires bolted on.** Same monolith + "ALSO health-check every
iteration: liveness, log freshness, accepted>0 within 1 h, …". Catches
the incident class, but still re-analyses everything every wake.

**v3 — two-tier with persistent state (adopted).**
- **Cheap tick (every wake):** health-check running jobs against
  quantitative tripwires; note bank/output deltas; launch the top of
  the priority queue if cores are idle. Seconds of work, stays inside
  the prompt-cache window.
- **Deep review (event-triggered only):** experiment
  finished/banked/stalled ≥2 ticks, a tripwire fired, or >12 h since
  the last review → refetch external truth (leaderboard), recompute
  gaps, reprice the queue by ROI, update vault, report to user.
- **State file** (`vault/loop-state.md`): priority queue, running jobs,
  tripwires, bank snapshot, last-review timestamp, tick log. The
  directive's first instruction is "read the state file"; every
  iteration updates it. Survives context compaction and session
  restarts.
- **Explicit escalation set:** submissions, destructive actions, empty
  positive-EV queue. Everything else proceeds autonomously.

## Design principles (general form)

1. **Separate monitoring from strategy.** Monitoring is cheap and must
   be frequent; strategy is expensive and should be event-driven.
   A directive that asks for both on every wake gets you sluggish
   monitoring *and* redundant strategy.
2. **Health-check semantics, not just liveness.** A process can be
   alive, logging, and burning CPU while being incapable of ever
   producing a result. Tripwires must test *progress invariants*
   (acceptance rate > 0 within a horizon, feasibility rates sane,
   monotone counters advancing), not just "is the PID up".
3. **Make tripwires quantitative.** "Check experiments are OK" is not
   actionable. "SA/ALNS chain with accepted=0 after 1 h must be
   diagnosed immediately" is. Each past incident should be converted
   into a named tripwire (here: *evaluator metric must equal the
   acceptance-baseline metric* — the bug class that produced both the
   E-549 misread and the E-550 dead run).
4. **Persist loop state outside the conversation.** Priority queue,
   running-job table, last external snapshot. The directive should be
   a *pointer* to state, not a *container* of state — context windows
   compact, files don't.
5. **Reachable exits + explicit escalation.** Pair the aspirational
   stop condition (rank 1) with a hard deadline (competition end) and
   name the situations that must interrupt the human. Otherwise the
   loop either never ends or stalls silently on a judgment call.
6. **Adaptive cadence, cache-aware.** Tighten the wake interval only
   while something urgent is unresolved (here: a dead run burning 4
   cores during a tooling outage → ~4 min retries); relax to the long
   tick (~20–30 min) once the urgency clears. Match polling to the
   timescale of what's being watched.
7. **Degrade gracefully during tooling outages.** When the execution
   channel fails (here: shell-approval classifier outage blocked all
   mutating commands for ~1 h), keep doing read-only diagnosis,
   pre-stage the fix as a one-shot script, and let the loop retry the
   single mutating call — so recovery needs one success, not a
   sequence.

## Cross-references

- Incident + fix: `scripts/ch2_e550_medium_walk_slsqp_alns.py` (patched
  2026-06-10), `vault/loop-state.md` (live state).
- Related discipline: [[M-general-bug-surfacing-for-scientific-code]]
  (instrument silent reject paths — the same incident also fired the
  ">30 % rejects" trigger via E-549's DP_ok=4 %).
- Related: [[M-general-anti-oscillation-discipline]] (quantitative
  decomposition before narrative flip-flop).
