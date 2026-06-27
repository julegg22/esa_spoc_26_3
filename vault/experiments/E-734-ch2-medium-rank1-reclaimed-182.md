---
id: E-734
type: experiment
tags: [ch2, medium, rank-1, breakthrough, order-search, precompute, validated]
date: 2026-06-28
status: DONE — VALIDATED rank-1 182.11d (official kt.fitness feasible); submission user-gated (HELD)
related: ["[[E-731-ch2-medium-deepaudit]]", "[[ch2-medium-bank]]", "[[foundation-then-search-methodology]]"]
---
# E-734 — Ch2-medium RANK-1 reclaimed: 189.10 → 182.11d (validated, held for submission)

**Result:** full cheap-edge precompute (3157 edge-windows) + 4 fast DP-only order-search chains found
**182.11d official-feasible** for Ch2-medium — beating live rank-1 (186.27) by **4.16d** and our prior bank
(189.10) by **6.99d**. All four chains hit rank-1 independently: m4 **182.11**, m1/m3 183.15, m2 184.31.

## What unlocked it
The finders were CPU-bound at ~3.7s/iter (per-move uncached cheap-edge scans). Precomputing ALL 3152 cheap
edge-windows to a shared base (`cache/ch2_medium_edgewin_0.05_0.02.pkl`, 506 MB, ~2.2 h, E-731 machinery) made
the search **DP-only (~ms/iter, ~400 it/s)**. With the full edge set available (not just the bank's edges), the
or-opt/2-opt search reached far better orderings within minutes (m4 at 182.11 by it125434/733s).

## Validation (positive-control gated — this campaign's bug-history demands it)
Independent fresh-process `kt.fitness` on the official medium instance:
- **POS-CTRL submitted bank → 189.1000d** (reproduces exactly) ⇒ judge faithful.
- **POS-CTRL 188.110 file → 188.110d.**
- **m4 ckpt schedule → 182.1100d, all 4 violations exactly 0.0, 181/181 unique cities, times monotonic,
  schedule chains (arr_k ≤ dep_{k+1}), last_arr = makespan.** A genuine official-feasible solution.

The finder's built-in official gate (order_search.py:205 — `kt.fitness` before saving to ckpt) means the
`ordersearch_{tag}.json` ckpt files are real; they need no proxy trust.

## Methodology note — the mirage detour (a self-correction worth recording)
I briefly mis-read this as a coarse-grid mirage: the **harvester** re-timed m1's *proxybest* (the ungated file,
saved on every 0.05d proxy-improvement) with its own 0.025d DP → 189.835d, which looked like a 4d optimistic
proxy bias. **That was a red herring**: the harvester validates the wrong file. The finder's *ckpt* (official-
`kt.fitness`-gated) was right all along, and independent re-scoring confirmed it. Lesson: when two evaluators
disagree, re-score the concrete artifact with the OFFICIAL judge + a positive control — don't infer "mirage"
from a secondary re-timer. (The harvester should read ckpt, not proxybest — minor fix, not load-bearing now.)

## State
- Best validated: `cache/ch2_medium_RANK1_182.110.json` (full dv) + `cache/ch2_medium_BEST.json` (pointer).
- Finders STILL running — may improve below 182.11; BEST.json updated so all chains build on m4's order.
- **Submission HELD** (user-gated, never auto-submit). Submitting 182.11 reclaims Ch2-medium rank-1.
- Banks unchanged on disk: `solutions/upload/medium.json` still 189.10 until user approves the swap.
