---
id: E-731
type: experiment
tags: [ch2, medium, deep-audit, rank-1, frozen-order, edge-truncation, reorder-lever]
date: 2026-06-27
status: ACTIVE — deep audit; overturns "189.10 converged/rank-1-floored" as an optimality claim
corrects: [E-040]
reframes: [E-654]
related: ["[[M-general-deep-single-prompt-audit]]", "[[E-652-ch2-medium-assumption-audit]]", "[[E-653-ch2-medium-short-tof-edges]]", "[[ch2-medium-bank]]"]
---
# E-731 — /deepaudit ch2 medium: the 189.10 "floor" is the retime-optimum of a FROZEN, edge-truncated order

User ran `/deepaudit ch2 medium`. Trigger: medium just LOST the rank-1 window (live r1 195.68 → **186.27**; our
bank **189.10** now ranks ~2). The "189.10 = converged / rank-1 / done" verdict must be re-diagnosed.

## Step 0 — X, Y, and the questioned results

- **Y (bank):** 189.10 d, n=181, official `kt.fitness` feasible `[0,0,0,0]` (re-verified this audit). Built by
  RETIMING one inherited order: 274.5 → 228.97 (DP) → 195.77 (epoch-aware cluster) → 192.9 → **189.10** (E-040
  ultrafine retime). **The ORDER was never globally re-searched for walked time** — every gain came from
  retiming a fixed permutation.
- **X (target):** live r1 **186.27** (need −2.83 d = −1.5 % to reclaim rank-1). Deeper oracle: E-652 static-flight
  LB ≈ 89 d ⇒ bank = **2.13× LB**; plausible true optimum ~110–130 d (~30–40 % headroom).
- **Questioned verdicts:** "M1 schedule-CMA converged ⇒ done" (true only for THIS order); "rank 1 ⇒ near-optimal"
  (rank-relative, now STALE); E-654's "171.9 d overhead ~irreducible" (asserted *because* rank 1, not bounded).

## Phase 1 — Assumptions shared across ALL medium branches

| # | Assumption | Violating solution looks like | Status |
|---|---|---|---|
| A1 | Candidate edges = the precompute table (tof ≥ 0.025 d) | an order using a sub-0.025 d cheap hop where the table forced a long leg | **FALSIFIED** (E-653: 207 cheap edges below the floor) |
| A2 | The visit ORDER is fixed (inherited cluster-decomp); only the SCHEDULE is searched | a different order with lower *walked* time | **untested for walked cost** |
| A3 | Order search scored on fixed-reference-time tof PROXY | an order good under the CHRONOLOGICAL walk, not the proxy | proxy is orthogonal to walk cost (E-037) → past order search MISLED |
| A4 | 4-component [121,20,20,20] / 5-exc-bridge skeleton forces the route | — | REAL (stable across epochs, E-654); but intra-component order is free |
| A5 | "rank 1 ⇒ near-optimal ⇒ deprioritise" | — | **STALE** (now rank-2) |

## Phase 2 — Gap accounting (measured on the banked artifact)

makespan 189.10 = **177.22 d flight + 11.88 d idle/wait (6.3 %)**. Loss is concentrated in:
- **Long legs:** 71/180 legs have tof > 1 d, summing **132.7 d** (70 % of flight in 40 % of legs); 20 legs > 2 d
  (66.8 d). Walked median tof 0.748 vs cheap min-tof ~0.126 (E-652) = **~6× per-leg inflation** — the order routes
  through long legs where a short one was available.
- **Idle:** 40/179 legs wait > 0.05 d, total 9.68 d. But M1 proved the schedule is floored *for this order* — the
  idle is *forced by the order's phasing*, so it is **only reclaimable by REORDERING**, not retiming.
- **Scale of the prize:** the idle alone (11.9 d) is **~4× the 2.83 d** needed to reclaim rank-1; the long-leg
  inflation is far larger again. The gap is tiny relative to the available headroom.

## Phase 3 — Paradigm inventory

| Paradigm | Touched? | Survives Phase-1 scrutiny? |
|---|---|---|
| Retime-only (fixed order) | YES — floored 189.10 | floor is real but order-conditional (A2) |
| Order local-search on PROXY cost | YES — plateaued | **misled by A3**; not a real exhaustion |
| **Order search on FAITHFUL chronological walk + FULL edge set (incl sub-0.025)** | **NO (medium)** | the lever — skipped by A1+A3, and deprioritised by A5 |
| Time-expanded joint (order, schedule) respecting 4-comp/≤5-exc | built for LARGE only, **never run on medium** | tractable at n=181; skipped by A5 |
| DP-ALNS on a pair-keyed fine table | proposed, never built | skipped by A5 |

## Verdict

**The "189.10 converged / rank-1-floored" verdict is FALSE as an optimality claim.** 189.10 is the retime-optimum
of a single inherited order that (a) was built on a **truncated edge set** (A1 falsified — 207 unsampled cheap
short-tof edges) and (b) was **never globally re-searched for walked time** (A2/A3 — the only order search ran on
an orthogonal proxy). The load-bearing flaw is the **frozen, edge-truncated order**; the schedule "floor" (M1
null) is downstream of it. Two oracles (live 186.27; static LB 2.13×) prove the achievable region extends well
past 189.10; reclaiming rank-1 needs only 1.5 %, and the idle + long-leg inflation dwarf that. **Medium is a LIVE
lever, not a closed one** — the rank-1 deprioritisation premise (A5) is stale.

## Further exploration paths (3, cheapest information-gain first)

1. **Long-leg targeted reorder probe** (violates A2). Take the 20 legs with tof > 2 d; for each, or-opt the local
   segment to route via a cheaper available edge (incl the 207 sub-0.025 d edges), gate on faithful `kt.fitness`.
   **Binary:** any swap < 189.10 ⇒ frozen-order (A2) is the flaw, reorder lever LIVE. Cheap (~tens of faithful
   evals, single core). ← take this first.
2. **Full-edge faithful order LNS** (violates A1+A2+A3). Rebuild the medium candidate edges WITHOUT the 0.025 d
   tof floor; run destroy-repair LNS on the chronological-walk faithful evaluator (port the large CLS to n=181 —
   tiny, fast). **Binary:** < 186.27 ⇒ reclaim rank-1; < 189.10 ⇒ better bank.
3. **Time-expanded joint (order, schedule) search** (violates A2+A4-skeleton-preserving), the named M3 built for
   large. n=181 is ~6× smaller than large's 1051 → tractable. **Binary:** < 186.27 rank-1, or floors ⇒ the wall
   holds at this scale too.

Diagnostic only — no bank change, nothing submitted (user-gated). Per CLAUDE.md §5b, taking step #1 next.
