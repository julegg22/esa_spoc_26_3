---
id: E-039
type: experiment
tags: [experiment, ch1, matching, evaluator-audit, foundation-then-search, refuted]
date: 2026-06-12
status: AUDIT COMPLETE — evaluator-divergence hypothesis REFUTED; our model is faithful to the official UDP; gap is exact-solver power, not the model
instance: matching-i / matching-ii
script: none (read-only audit, bg agent af600ebd)
related: [[E-001-ch1-matching-first-attempts]], [[E-004-ch1-matching-i-exact-polish]], [[M-general-foundation-then-search]], [[O-002-leaderboard-2026-05-18]]
---

# E-039 — Ch1 matching: official-evaluator/model audit (hypothesis REFUTED)

## Hypothesis (from 2026-06-12 deep analysis)

Six methods converging on exactly 33,338.184 while 8 teams sit 0.02–0.65%
above (r1=33,555.61) is the foundation-then-search trigger → suspect the
MODEL/EVALUATOR, since (premise) "the starter kit has no official Ch1
Python evaluator" and nothing was ever submitted (no ground truth).

## Result: REFUTED on all four audit dimensions

**Decisive find: the premise was wrong.** Official PyGMO UDPs DO exist
locally at `reference/spoc4_udp/matching-i.py` / `matching-ii.py`
(only `reference/SpOC4/` lacks them; I verified the files directly).
The two are byte-identical except the instance path
(`random_harder_5000.txt` vs `random_hard_10000.txt`).

1. **Instance parsing — MATCHES.** Official `parse_input` reads 4
   whitespace fields (a,b,c,w)/line; our `load_instance`
   (src/esa_spoc_26/ch1_matching.py:29-35) np.loadtxt → same edge list,
   same order. Row counts (25,000 / 92,103) = number of CANDIDATE
   TRANSFERS; the "5000/10000" in official filenames are node-set sizes
   (id spans confirm). No comment lines in either file.
2. **Constraint semantics — MATCHES; free-recombination REFUTED.**
   Official fitness iterates `zip(x, self.edges)` — selection from GIVEN
   rows only; any duplicate e/l/d ⇒ whole solution scores 0. Unlisted
   triples physically cannot be scored. Our ILP enforces exactly ≤1 per
   node, nothing extra.
3. **Fitness — MATCHES (both i and ii).** matching-ii is the same class,
   plain Σw. No time windows / mass term (that's the Advanced
   trajectory-matching problem).
4. **Submission encoding — MATCHES.** Binary vector of length |T|,
   index-aligned to file rows; our artifacts verified (byte sizes
   75,092 / 276,402 ≈ N×3 + envelope). Official local score of our bank
   = 33,338.18 exactly.

## Reframe of the "6-method consensus"

It was never an independent-model consensus: E-002/3/4 + T-004 show one
HiGHS-based family's asymptote (29,792→33,134→33,320→33,338); exact
HiGHS timed out at 122% gap (E-001), CP-SAT 7200s warm-start matched the
bank exactly with bound 34,339 (gap 2.92%). **33,338.184 was never
proven optimal.** The leaderboard packing (8 teams within 0.65%, far
below the 34.3k bound) is the signature of everyone solving the same
NP-hard 3-index assignment with stronger exact solvers — a model
divergence would show a discontinuous jump, not a 7-point miss of the
(2026-05-18) r5 cutoff 33,345.05.

## Consequences

- **No change to evaluator/encoding.** Submission-format risk on Ch1
  matching is low (calibration via first submission still wise).
- **The lever is exact-solver power on the pure ILP:** tighter 3-index
  formulation for CP-SAT, LP-guided branching, much longer budgets, or a
  Gurobi-class solver (user decision). Teams are packed every few kg →
  each small gain ≈ a rank step (×1 weight on matching-i).
- Caveat: local instance files vs live URLs not byte-re-verified
  (network blocked this session); id ranges/row counts match.
