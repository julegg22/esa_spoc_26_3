# M-general — Instrument every experiment before launching it

**Kind:** process-discipline · **Scope:** experiment engineering ·
**Generalizability:** cross-campaign · **Status:** active (user-stated 2026-06-16)

## Rule

**Never launch a long-running experiment that produces no output until it
finishes.** Every background/compute experiment MUST emit progress as it runs:
per-item or periodic log lines (count done / total, current best, elapsed,
last result), flushed immediately. A program that prints only at the end is
indistinguishable, while running, from one that is hung, mis-pathed, stuck on a
single slow item, or computing the wrong thing — and you only discover the flaw
after burning the full wall-clock waiting.

## Why (the incident that originated this)

E-646 (Ch1-trajectory high-incl fill test, 2026-06-16) collected all 144 results
via `imap_unordered` and printed **only at the end**. It ran **>85 minutes** with
a 2-line log (just the header), so every health-check was blind — I could not tell
whether it was progressing, hung, or solving the wrong pairs. It also had a
silent path bug on first launch (`LtlTrajectory(ROOT)` vs the data dir) that a
startup self-check would have caught in seconds. The fix — kill it, add coarse
per-pair logging + a faster sweep (E-646b) — produced a readable, trustworthy
answer (high-incl idE fill at 84–516 kg) in a fraction of the time. The wasted
85 minutes were pure instrumentation debt.

Same session, related near-misses caught only by ad-hoc checks: a stale
evaluator table that mis-scored the bank by +5.5 d (would have optimized the
wrong metric), a per-pair evaluator that was 80× too slow (pure-Python DP), and
two underpowered "basin" tests whose weak polish gave false negatives. All are
the same failure family: **launching before verifying the harness emits
trustworthy signal.**

## Checklist (apply to every experiment script before `nohup … &`)

1. **Progress logging:** print every item (or every N items / every ~30 s) with
   `flush=True`: `[done/total] key=… best=… elapsed=…`. Never end-only output.
2. **Positive control / startup self-check:** before the long loop, reproduce one
   KNOWN value (e.g. score the current bank, eval a known pair) and assert it
   matches. Fail fast on path/import/units bugs.
3. **Smoke test the cheap parts first:** run the constructor/evaluator on a few
   inputs (skip the expensive solve) to catch shape/feasibility/`inf`/`nan` bugs
   before committing cores for an hour.
4. **Evaluator-matches-baseline gate:** confirm the experiment's metric reproduces
   the established baseline before trusting any delta (see
   [[M-general-foundation-then-search]]).
5. **Bounded + observable:** print a wall-clock ETA at start; size the run so a
   first signal arrives within minutes, then scale up once it's trustworthy.
6. **Pick power before precision:** ensure per-item effort is strong enough to be
   conclusive (a fast-but-too-weak probe gives false negatives — the
   underpowered-test trap).

## How to apply

Treat "can I see it working and trust the signal within 2 minutes of launch?" as
a launch gate. If no, add instrumentation/controls first. The cost of a logging
line is seconds; the cost of its absence is the entire run's wall-clock plus a
relaunch. Relates to [[M-general-bug-surfacing-for-scientific-code]] (audit the
harness before blaming the search) and the never-stop loop's health-check
discipline (a run that can't be health-checked can't be in the loop).
