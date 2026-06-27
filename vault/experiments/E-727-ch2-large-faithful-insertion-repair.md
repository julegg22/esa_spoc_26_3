---
id: E-727
type: experiment
tags: [ch2, large, rank-1, insertion-repair, regret, lns, faithful-evaluator, retry-queue]
date: 2026-06-27
status: ACTIVE — re-try-queue #1 (insertion-repair on FIXED tools) executed; still walls; resolves the item
related: ["[[A-2026-06-27-broken-tool-retry-queue]]", "[[E-726-ch2-large-ultrathink-audit-rank1-reachable]]", "[[E-720-ch2-large-ultradeep-audit]]", "[[E-721-ch2-large-foundational-graph-undercount]]"]
corrects: [E-721]
---
# E-727 — Ch2-large rank-1: faithful insertion-repair (re-try-queue #1, executed on FIXED tools)

The re-try queue ([[A-2026-06-27-broken-tool-retry-queue]]) flagged the E-721 "insertion cascade → local repair
blocked" verdict as a TOOL-ARTIFACT (broken evaluator T1 sparse table + T2 long-tof-blind retimer). This node
**executes the re-run with the fixed tools** and answers it honestly.

## What was built (`scripts/ch2_giant_completion_repair.py`)

- **Fast validated W-beam retimer** (the key enabler): W=1 greedy strands feasible orders (the earliest-arrival
  trap); a small **window-branching beam (K=3, W=16)** over a **combined window source** — faithful epoch-dense
  short-tof (E-726d) ∪ dense1d long-tof (0–950, CT-verified) — retimes the GRASP seed g (328 cities) to exactly
  **452.0 d / 0 strands in 0.1–0.3 s**, matching GRASP. (Earlier the W=200 timebeam took >200 s/eval — too slow
  for repair; the small beam is the fix.)
- **Mid-tour insertion-repair** (what a forward beam cannot do): place a missing city between two existing legs,
  allowing re-phasing wait, with lazy full-retime validation. Two selection rules tested: greedy-cheapest and
  **regret-2** (insert the most-constrained city first, while slack exists).

## Result — both wall, the cap is GENUINE phasing (not the broken evaluator)

Seeded from GRASP g (328 @ 452 d, maxwait 60):
- **Insertion fills existing slack for free up to ~368/601** — makespan *drops* 452 → 439.6 d while adding 40
  cities (d/leg 1.382 → 1.198). First method to grow toward completion without inflating makespan: it packs
  cities into the seed's idle waits.
- **Then the slack runs out and it walls, two ways:**
  - **greedy-cheapest:** spends free slack on easy cities → reaches **438/601 but makespan blows to 908.5 d**
    (d/leg 2.08 = rank-2 pace) forcing hard cities in at large wait.
  - **regret-2:** holds makespan flat (**460.9 d**) but **caps at 385/601** — refuses large-wait insertions, hits
    a dead-end order where the remaining 216 constrained cities have *no feasible slot at all* (corner-paint).
- **Neither reaches 601 at < 424 d (rank-1).** Even the low-makespan region is ~1.2 d/leg (rank-2 pace); rank-1
  needs 0.71 d/leg over the whole 601. The deep/high-inclination cities cannot be phased into the tour without
  large waits — the **genuine TD-TSP phasing tax**, now confirmed on a CORRECT evaluator.

## Verdict — resolves re-try-queue #1

The E-721 "cascade" *numbers* were tool-inflated (the broken evaluator over-counted strands), **but the
conclusion stands on fixed tools**: insertion/local repair cannot complete the giant at rank-1 pace. Re-try-queue
item #1 is **executed and closed: still walls.** This *strengthens* the honest verdict — rank-1 is research-grade
global phasing, not a tool artifact — because it is now demonstrated on the faithful evaluator, not asserted from
broken ones. Corrects the artifact-inflated framing of [[E-721-ch2-large-foundational-graph-undercount]].

## Named next step (NOT a stop — CLAUDE.md §5b)

Single-pass insertion is deterministic and dead-ends. The basin-overarching escape is an **ALNS destroy-repair
loop with acceptance** (destroy the high-wait legs that block completion → regret-repair → accept on (depth,
−makespan)). A first `lns_loop` was coded but has a **destroy-rebridge bug**: removing a mid-tour city breaks the
tightly-phased chain (the re-joined a→b leg strands), and the code rejects the candidate *before* repairing it —
so no iterations land. **Fix next:** destroy must remove cities AND let the repair re-bridge the gap in one pass
(don't require the gapped order feasible pre-repair). The retimer + regret machinery are validated and reusable.

Banks held/unsubmitted (user gate). Rank-2 (932.53) secure. Methodology: re-try-queue execution per
[[M-general-retraction-annotation]] (TOOL-ARTIFACT items must be RE-RUN, not assumed).
