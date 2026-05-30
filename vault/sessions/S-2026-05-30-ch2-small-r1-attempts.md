---
date: 2026-05-30
tags: [session, ch2, small, lns, r1-attempt]
status: bank 142.8913d (down from 142.9183, -0.027d via E-508). LNS basin exhausted; R1 needs different solver.
bank_before: 142.9183
bank_after: 142.8913
R3: 111.76
R1: 101.65
---
# S-2026-05-30 — Ch2 small heavy-compute R1 push

## What was done
1. **Audit + methodology bootstrap** — `vault/audits/A-2026-05-30-ch2-small.md`
2. **E-501 CP-SAT relaxed LB**: 74.33d feasible (relaxed; not chronological)
3. **E-504 param sweep**: 81 min, no improvement
4. **Fine 0.5d×100tof edge table** (50 min precompute) — `/tmp/ch2_small_tcoupled_fine.npz`
5. **E-508 fast-walker LNS**: 8 workers × 25 min → bank 142.92 → **142.89 d** (−0.027d)
6. **E-509 diverse-seed LNS**: 8 workers × 40 min + 1500 Lambert validations → no further improvement

## Results
- Bank: 142.9183 → **142.8913 d** (UDP-validated feasible, banked at `solutions/upload/small.json`)
- 30,764 unique perms validated with full Lambert in E-509; ZERO beat 142.8913

## What we learned
- Fast walker (0.5d quantum) has 20d quantization overhead vs Lambert truth
- Fast-walker basin around bank perm is very deep: all 30k perms cluster at fmk ≥ 151.75
- Random / shuffle seeds can't even produce ONE feasible fast walk — 4-comp graph too sparse
- Lambert variance around fmk = ±5d; finds bank-equivalents but not breakthroughs
- The bank perm's structural choices (which 5 exception bridges, in what positions) are locally optimal

## Why R1 (101.65) wasn't reached
- Bank is at LOCAL optimum in (perm × times × tofs) joint space
- LNS within the basin returns 142.89 invariant
- R1 (101.65) requires DIFFERENT perm structure — different exception bridge nodes,
  different cluster traversal order, possibly different start node — beyond LNS reach
- Realistic path: proper time-coupled MILP/CP-SAT (hours of solve), or
  custom constructive heuristic that explores different bridge configurations

## Next levers (if/when user authorizes more compute)
- **CP-SAT with fine table**: full time coupling, 2-4h MILP run with symmetry breaking
- **Bridge-node sensitivity sweep**: for each of the 4 cheap-edge components, enumerate
  all possible "entry node" / "exit node" pairs; for each combination, run a focused LNS
- **Custom Lagrangian relaxation**: dualize the chronological constraint, solve relaxed
  TSP, recover primal feasibility via local search
- **Build CONSTRUCTIVE solver**: use Concorde-style methods on the directed time-expanded
  graph (each pair × t_start = node; edges by chronological feasibility)

## Artifacts committed
- `vault/audits/A-2026-05-30-ch2-small.md` — methodology audit + decomposition
- `scripts/ch2_e501_cpsat_lb.py` — relaxed LB CP-SAT
- `scripts/ch2_e504_param_sweep.py` — hostile-default cross-product sweep
- `scripts/ch2_e505_beam_search.py` + `_beam_v2.py` — beam-search attempts (failed: directed dead-ends)
- `scripts/ch2_e506_lns_table_filter.py` — LNS with table filter (filter too tight)
- `scripts/ch2_e507_cpsat_tcoupled.py` — proper CP-SAT (180s gave no feasible)
- `scripts/ch2_e508_fast_lns.py` — fast-table LNS (yielded 142.89d bank)
- `scripts/ch2_e509_diverse_lns.py` — diverse-seed LNS (null result)
- `scripts/ch2_fast_walker.py` — table walker (1000+ walks/sec)
- `scripts/ch2_precompute_fine.py` — fine edge table precompute
- `scripts/ch2_tcoupled_walk.py` — table re-walk
- `/tmp/ch2_small_tcoupled.npz`, `/tmp/ch2_small_tcoupled_fine.npz` — edge tables

## Memory pointers
- `ch2-small-audit-2026-05-30.md` — audit findings (cheap graph 4-comp, hostile wait_dt=1.0 default)

