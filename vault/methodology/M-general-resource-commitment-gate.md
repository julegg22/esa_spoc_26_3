---
title: "Resource-commitment gate for long computations"
tags: [methodology, general, compute, resource-management]
created: 2026-07-01
type: methodology
---

# Resource-commitment gate for long computations

**Principle.** Compute is a multiplier on insight, not a substitute for it
([[ch2-compute-parallelization-roi]]). Long jobs (>10 h) are legitimate and
sometimes necessary — but only behind an explicit **resource-commitment
gate**. "Keeping cores busy" on an unvalidated long sweep is not progress;
it is waste that also delays the real lever.

Originating case (2026-07-01, Ch2 medium deadline session): a ~16 h
precompute chain (e531 10.8 h coarse table + e542 5.0 h fine pair-set)
consumed almost the entire window and left the actual DP-ALNS search ~1.5 h
— too little to move the metric. The precompute was correct; committing to
it *without budgeting the search* was the error.

## The gate — commit to a long (>10 h) job ONLY if all three hold

1. **Confidence.** The approach is expected to move the target metric,
   grounded in a measurement or prior evidence (fits a row of the
   quantitative gap decomposition, or attacks the isolated bottleneck) —
   not a speculative punt. If it's exploratory, run a *short* probe first.

2. **Validity pre-tested.** Before committing hours:
   - positive control passes within the first ~minutes (see
     [[M-general-bug-surfacing-for-scientific-code]] and the
     instrument-before-launch rule);
   - the **evaluator is faithful** — this campaign's recurring failure is
     optimistic / coarse-resolution evaluators that make a long run measure
     the wrong thing (Ch2-large GLKH resolution mismatch; the 8-probe cheap
     graph undercount; [[foundation-then-search-methodology]]);
   - a small-scale dry run reproduces the expected behavior, so the full
     run's result will be real, not an artifact.

3. **Live monitoring + resumability.** Frequent checkpointing to a
   reboot-surviving dir with resume ([[feedback-persist-partials-survive-reboot]]),
   a visibly advancing metric, and a kill criterion (stalled ETA / flat
   objective for N ticks). Never launch a no-output-until-end job.

## Budget backward from any hard bound

If there is a deadline or a fixed compute envelope, **precompute + search
must both fit**. Estimate each and reserve enough for the stage that
actually produces the result. A precompute that leaves the optimizer
starved has negative ROI even if it completes.

## Order of escalation

Cheapest information-gaining probe first (does the lever exist? is the
evaluator faithful? how wide is the structure?), then a medium validating
run, then the long sweep — and only once the gate is satisfied. This is the
same escalation the deep-audit and exhaustion-is-a-transition rules assume
([[M-general-exhaustion-is-a-transition]]).

Related: [[feedback-resource-management-long-compute]],
[[feedback-instrument-experiments]], [[ch2-compute-parallelization-roi]].
