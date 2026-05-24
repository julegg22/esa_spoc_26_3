# Lessons learned — 2026-05-24

## The bug

**`solve_arrival_dv` in `ch1_trajectory_solve.py:72`:**

```python
if abs(r - a_m) >= L * tol:  # 384m
    return None
```

This filter only allows arrival radius within 384m of `aL`. **Correct
for circular orbits (eL ≈ 0), wrong for eccentric.** Valid arrival
radii for a Moon orbit `(aL, eL, iL)` span `[aL(1-eL), aL(1+eL)]`. For
eL=0.65, this is a 6,700 km window — we were rejecting all of it.

**Impact:** 150 of 400 Moon orbits have eL > 0.3. ~58 of 400 have
eL > 0.01. Even small non-zero eL was rejected unless the trajectory
happened to land within 384m of `aL`. This made the solver appear to
fail for ~99% of pairs, masking the real per-pair mass potential.

**Symptoms before fix:**
- Our bank: 14.82 kg (one pair, coplanar circular)
- 20/20 inclined pairs failed validation
- "30000× gap" to leaderboard R3
- Conclusion drawn: needs research-grade patched-conic SOI handoff

**Reality after fix (test pairs):**
- (0,0): 14.82 → 819 kg
- (267,181) GEO+eL=0.65: FAIL → 2037 kg
- (266,234) GEO+eL=0.64: FAIL → 1211 kg
- (27,116) LEO+iE=0.11: FAIL → 332 kg

The leaders aren't doing exotic physics. They have a solver that
handles eccentric Moon orbits — which is most of them.

## Why we missed it for 6 days

### Day 1-3 sequence
1. Banked 14.82 kg with solve_transfer_direct
2. Polished it via various methods (LNS, Nelder-Mead, joint SLSQP)
3. Found "thin feasibility ridge" — interpreted as physical
4. Pursued "better physics" (Lambert+BCP DC, patched-conic, WSB)
5. Each attempt failed on inclined/eccentric pairs
6. Concluded "research-grade trajectory dynamics required"

### Root cause of the misdiagnosis
We **never sanity-checked the solver's assumptions against the data
distribution**. The solver was written assuming circular Moon orbits
(target `(a, e, i) = (r, 0, i_m)`). The data contained orbits with
eL up to 0.65. We had the eccentricity distribution in memory but
never traced "what's the maximum eL?" to "does our solver handle that?"

Earlier observations (O-012) diagnosed an *adjacent* bug (under-
determined residual in solve_transfer_back) but missed the arrival-
filter bug. We treated O-012 as the complete bug list and moved on.

## The pattern we should learn

When you observe a solver "failing for 99% of inputs":

1. **NOT "the problem is hard"** — solvers fail systemically. Look for the systemic cause.
2. **NOT "we need more compute"** — random search through 1e36-volume manifolds can't be fixed by 10× more compute.
3. **YES "what assumption did our solver bake in?"** — match each assumption against the data distribution.

When you observe a 30000× gap to leaderboard:

1. **NOT "they have better physics"** — competitors work with the same data and tools.
2. **NOT "research-grade techniques needed"** — leaderboard #1 likely uses textbook methods.
3. **YES "what fundamental assumption am I making about the problem?"** — Hungarian theoretical bound vs achieved is a sanity check that fires early.

## Checklist for future projects (added 2026-05-24)

Before declaring "this is hard" on a benchmark:

- [ ] **Compute the theoretical optimum/bound** for the metric you're optimizing.
  - For Ch1 trajectory: Hungarian on Hohmann-theoretical mass matrix = 445k kg.
  - Our achievement = 14.82 kg = 30000× gap.
  - This ratio alone should have flagged "solver bug, not physics."

- [ ] **For each solver assumption, verify against the data distribution.**
  - solve_arrival_dv assumed eL ≈ 0 (circular target).
  - Data had eL up to 0.65.
  - Distribution check would have caught this on day 1.

- [ ] **Test the solver on >10 diverse inputs early.** A solver that works on (0,0) is not validated. Need to sample LEO + MEO + GEO × low/mid/high inclination × low/mid/high eccentricity.

- [ ] **Look for "miraculous" successes.** If your solver works for ONE input out of 100, ask "what's special about that one?" — usually it's a degenerate case where bugs cancel out.

- [ ] **Read the original problem spec end-to-end.** Don't rely on summaries. The README told us moon orbits had eccentricity up to 0.65, but we never traced that through to solver requirements.

## How this changes affected work

### Trajectory bank
The 14.82 kg banked solution is correct (it's a valid trajectory). It
will be superseded by the production sweep's output (currently
running, expecting 200-500k kg).

### Vault observations
The following contain conclusions that pre-date this fix and may be
partially wrong:
- O-012-ch1-traj-under-determined-residual: diagnosed a real but
  ADJACENT bug. The 14.82 kg result it explained is OK; the
  "research-grade fix needed" tone is wrong.
- O-002-leaderboard: "30000× gap" framing is misleading post-fix.
- All sessions S-2026-05-18 through S-2026-05-23 contain Ch1
  trajectory dead-end exploration that was solver-bug-induced.

### Scripts
22 files reference solve_arrival_dv. After the in-place fix, all
benefit. They remain valid history.

## Permanent change

Adding a checklist item to META.md / project methodology:
- **Before declaring "research-grade compute needed"**: compute a
  theoretical bound, verify solver assumptions against data
  distribution, test on ≥10 diverse inputs.
