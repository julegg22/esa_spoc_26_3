---
id: C-033
type: concept
status: confirmed
tags: [methodology, evaluator, precompute, lambert, ch2, technique]
scope: algorithm/evaluator-design
confidence: high
created: 2026-06-23
sources:
  - "Internal: E-710 M0a-c (ch2_giant_table_audit.py, ch2_giant_window_continuity.py)"
  - "Internal: E-710 M2 fine-tof beam (ch2_giant_fine_beam.py)"
related: ["[[C-031-grid-quantization-mismatch]]", "[[C-012-earliest-feasible-tof]]", "[[C-026-dp-on-time-expanded-graph]]", "[[C-034-time-aware-beam-narrow-window-tdtsp]]", "[[M-general-foundation-then-search]]"]
---

# C-033 — Fast-faithful oracle (table-propose + fine-verify)

*The primitive that breaks the accurate-vs-fast dilemma for narrow-window
time-dependent edge evaluation. Use a coarse precomputed table only to
PROPOSE a candidate (epoch, tof); confirm it with ONE exact evaluation.*

## The dilemma it solves

When edges are feasible only in narrow windows (Ch2 giant: cheap-tof
bands ~0.002 d wide), every prior edge evaluator was caught in a
two-horned trap:

- **Faithful scan** (exact Lambert at many tofs): accurate, but ~100
  calls/edge → a faithful beam W=12 reached <50/601 in 6 min. Too slow.
- **Table substitution** (use the precomputed table's stored tof as the
  realized tof): fast, but OVERFITS — the table's bucket-epoch tof, used
  at the actual continuous departure time, is wrong, so the realized
  schedule inflates (E-672 1d-beam looked 0.3 d/leg on the table,
  "retimed" to 1099 d). See [[C-031-grid-quantization-mismatch]].

## The primitive

```
fine_cheap_arrival(i, j, t, dv_cap):
    # 1. PROPOSE: table gives the open grid epoch(s) >= t and a tof hint
    for e in nearest_open_epochs(i, j, t):
        dep = max(t, EPOCHS[e]);  h = table_tof[i, j, e]
        # 2. VERIFY: a FINE local search around the hint, EXACT Lambert
        for tof in arange(h - δ, h + δ, fine_step):
            if compute_transfer(i, j, dep, tof) <= dv_cap:
                return dep, tof, dep + tof       # realized tof is EXACT
    return None
```

The table is used **only for candidate generation / pruning** (which
(i,j) are plausibly cheap near `t`). The returned tof is computed by an
exact evaluator at the *actual* departure, so there is **no overfit**.
Cost ≈ the few Lambert calls inside the fine band (~1–30), not the ~100
of a full scan — and the table prunes ~120 neighbours down to ~10–20
candidates, so a state expansion is cheap.

## Why it works here (the enabling measurements — E-710 M0b/M0c)

1. **Table is faithful** (precision audit): 200/200 stored (epoch, tof)
   cells verify exactly under the online evaluator → the table is a
   *trustworthy proposer* (false positives only cost a bounded verify).
2. **Feasible bands are sub-quantum in tof** (~0.002 d): so the verify
   must be FINE (≤ 0.0005 d) — a 0.01 d verify finds the cheap tof only
   11 % of the time. This is the whole reason naive verify failed.
3. **Windows are continuous & wide in epoch** (~12 d, ≫ 1 d grid): so
   the table's nearest grid epoch is always close to any real departure,
   the tof hint barely drifts, and a tight band around it suffices.

If (1) fails → the table is corrupt, rebuild it. If (3) fails (windows
narrower than the epoch grid) → the proposer misses windows; densify the
table's epoch axis first.

## Cost model

| evaluator | calls/edge | overfit? | beam feasible? |
|---|---|---|---|
| full faithful scan | ~100 | no | no (too slow) |
| table substitution | 0 | YES (1099 d) | yes but wrong |
| **fast-faithful oracle** | ~1–30 | no | **yes** (W=60 at ~5 s/depth) |

## Generalization

Any time-dependent / windowed feasibility search where (a) an exact
evaluator is expensive, (b) a coarse table exists or is cheap to build,
and (c) the table is a faithful *proposer* even if its stored cost is
imprecise. Pattern: **table for recall, exact eval for precision.**
The table's job is "where to look," never "what the answer is."

## In practice

- `scripts/ch2_giant_table_audit.py` — the precision audit (step 1).
- `scripts/ch2_giant_window_continuity.py` — epoch-continuity (step 3).
- `scripts/ch2_giant_fine_beam.py` — the oracle inside a beam (C-034).

## See also

- [[C-031-grid-quantization-mismatch]] — the failure mode this avoids
  (and its online-evaluator manifestation, the "phantom wall").
- [[C-012-earliest-feasible-tof]] — the per-leg quantity being computed.
- [[M-general-foundation-then-search]] — validate the evaluator first;
  this primitive was built only after the precision/continuity audits.
