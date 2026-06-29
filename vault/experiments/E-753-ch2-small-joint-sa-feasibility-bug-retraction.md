---
id: E-753
type: experiment
tags: [ch2, small, joint-sa, feasibility-bug, false-positive, retraction]
date: 2026-06-29
status: RETRACTED — the "small 112.996->95.8 rank-1 breakthrough" was a FEASIBILITY-CHECK BUG in the SA, not a real result. Corrected SA confirms 112.996 floor. The audit (E-740/ch2-small-floor-14292) was right.
related: ["[[E-740-ch2-small-deepaudit-order-search-untried]]", "[[ch2-small-floor-14292]]", "[[E-746-ch2-small-time-expanded-gtsp]]", "[[scientific-bug-surfacing-method]]"]
---
# E-753 — Ch2-small joint-SA "breakthrough" was a feasibility-check bug (RETRACTED, caught by verification)

8h-window "never give up": built a joint order+epoch SA on small with the official `kt.fitness` (E-753). It
appeared to smash 112.996 -> 95.8d -> eventually **0.039d** (physically impossible for 49 cities) — the tell.

## The bug — my feasibility check, not kt.fitness
`kt.fitness` returns `[makespan, perm_c, dv_cnt-(n-1), time_cnt-(n-2), exc_cnt-n_exc]`; **makespan =
times[-1]+tofs[-1]**, and `is_feasible` requires `f[2]==0 AND f[3]==0` (EQUALITIES) — f[3]=time_cnt-(n-2) is the
**chronological-consistency** count (arrive before next departure). My SA used `max(f[1:]) <= 1e-6`, which wrongly
accepts **negative** f[3] (chronologically INCONSISTENT schedules). The SA exploited this: drive times[-1]→0 with
non-monotone times → makespan→0 while my broken check called it "feasible." 95.8/0.039 were never valid solutions.

## Correction — confirms the floor
Fixed the check to `kt.is_feasible` (f[1]==0, f[2]==0, f[3]==0, f[4]<=0). The corrected SA does **NOT** beat
112.996 (20k iters: best stays 112.996, only explores worse). So **small is genuinely floored at 112.996** for
chronologically-valid solutions — confirming [[ch2-small-floor-14292]] and [[E-740-ch2-small-deepaudit-order-search-untried]].
The bank `small.json` was never corrupted (verified intact at 112.996 throughout; SA banks only at end + the
corrected one finds nothing <112.996).

## Lessons
1. **Optimistic-evaluator class bug, self-inflicted:** the campaign's recurring failure mode (proxy/partial
   evaluator) reappeared in MY check (`max<=eps` vs the equality `is_feasible`). Use the provided `is_feasible`,
   never hand-roll constraint logic.
2. **Rigorous skeptical verification WORKED:** the 0.039d tell + the independent re-derivation (feas, exc<=5,
   chronology) caught a false rank-1 before any bank/submission. This is exactly the deepaudit discipline.
3. Do NOT propagate the broken SA to medium/large — it would exploit the same gap. (The is_feasible-fixed SA may
   still be applied as a *correct* probe, but small shows it confirms floors rather than breaking them.)

## Bank impact
None. Small held at 112.996 (rank 6). No rank gain. All ch2 banks intact.
