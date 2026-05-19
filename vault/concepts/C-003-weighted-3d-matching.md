---
id: C-003
type: concept
status: confirmed
tags: [optimization, combinatorics, ch1]
scope: optimization/combinatorial
confidence: high
created: 2026-05-19
sources:
  - "Garey & Johnson, Computers and Intractability (3-dimensional matching is NP-complete)"
  - "Korte & Vygen, Combinatorial Optimization"
related: ["[[H-001-ch1-matching-mip]]", "[[T-001-ch1-matching-needs-strong-search]]", "[[C-004-mip-and-mip-lns]]"]
---

# C-003 — Weighted 3-dimensional matching (set packing)

*Primer for non-experts: the combinatorial heart of Ch1.*

## Definition

You are given many **triples** `(e, l, d, w)` — an Earth orbit `e`,
a Moon orbit `l`, a destination `d`, and a weight `w` (delivered
mass). Pick a subset of triples to **maximise total weight** such
that **no e, no l, and no d is used more than once**. This is
**weighted 3-dimensional matching** (equivalently a **set-packing**
problem).

## Why it matters here

It is *literally* Ch1. The "beginner" instances (`matching-i`,
`matching-ii`) give the weights directly. The "advanced" instance
(`trajectory-matching`) is the **same problem** where each weight
must first be computed by designing a real BCP trajectory
(`[[C-001-cr3bp-and-bicircular-problem]]`). Solve the matching well
and the tomatoes are maximised.

## Mechanics

- **2-D matching** (only `e` and `l`, no `d`) is *easy* — solvable
  exactly in polynomial time (it is bipartite; the assignment
  problem). Intuition often (wrongly) carries over from here.
- **3-D matching is NP-hard** (Garey & Johnson). Adding the third
  coordinate destroys the nice structure; no known efficient exact
  algorithm for large instances.
- A natural heuristic is **greedy**: sort triples by weight, take
  each if its e/l/d are still free. Fast, but we *proved* it is a
  hard **local optimum**: every excluded triple was blocked by an
  already-chosen heavier one, so no "swap one in, kick its
  conflicts out" move ever improves it
  (`[[T-001-ch1-matching-needs-strong-search]]`). Greedy reached
  only 89 % of the rank-3 score; escaping it needed
  `[[C-004-mip-and-mip-lns]]`.

## In practice

Written as a binary **Integer Linear Program**: a 0/1 variable per
triple, maximise `Σ wᵢxᵢ`, with one "≤ 1" constraint per distinct
e, per l, per d. `matching-i` = 25 000 variables / 15 000
constraints; `matching-ii` = 92 103 / 30 000. The relaxation (allow
fractional picks) is *weak* for 3-D matching, so naive exact solvers
flounder — see `[[C-004-mip-and-mip-lns]]`.

## References

Garey & Johnson 1979; Korte & Vygen; campaign nodes H-001/T-001.
