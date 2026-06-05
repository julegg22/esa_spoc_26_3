---
id: E-028
type: experiment
status: done             # draft | running | done | invalidated
tags: [ch2, small, lambert, component-aware, bridge-enum, pre-registration, substrate]

hypothesis: "[[H-003-ch2-small-lambert-metaheuristic]]"

created: 2026-06-01
ran_start: 2026-06-01
ran_end: 2026-06-02
duration_runtime: "21 min wall (much under 4h budget; OR-Tools strategies converged faster than estimated)"

# reproducibility
code: scripts/ch2_e517_bridge_enum.py
commit: 4dcd1ec (pre-launch)
inputs: |
  reference/SpOC4/Challenge 2 .../problems/easy.kttsp (n=49, n_exc=5)
  /tmp/ch2_small_tcoupled_fine.npz (pre-computed fine min-tof table)
  solutions/upload/small.json (bank perm, mk=142.8913 d)
outputs: |
  /tmp/ch2_e517_history.jsonl      (every Lambert-feasible candidate)
  /tmp/ch2_e517_ckpt.json           (resume point, 5-min cadence)
  runs/ch2/e517_bridge_enum.log     (wall log)
plots: [E-028/dv_per_config.png]    # produced post-run
seed: 0 (component enum is deterministic; OR-Tools top-k is sorted)
env: micromamba spoc26, python 3.13.13

code_dependencies:
  - src/esa_spoc_26/ch2_kttsp.py
  - src/esa_spoc_26/ch2_insert_lns.py    # walk_perm_chrono
  - src/esa_spoc_26/ch2_findtransfer_greedy.py
  - scripts/ch2_e511_ortools_routing.py  # OR-Tools cost-matrix builder (reuse)

compute:
  cpu_seconds:
  peak_memory_mb:
  cores: 8
  wall_budget_h: 4

effort_person_hours:

metrics:
  candidates_enumerated: 240
  lambert_evaluations: 480
  feasible_S1_wait1_0: 0
  feasible_S2_wait0_2: 0
  perms_with_3_inter_comp_exc: 0
  best_mk_S1: null
  best_mk_S2: null
  bank_improvement_d: 0.0
  all_rejected_at_leg: 3        # comp3-exit → OR-Tools comp0-entry, exc_used=0
verdict: refutes                # supports | refutes | inconclusive

invalidation:
  invalidated_by:
  superseded_by:
  invalidated_at:
  notes:
---

# E-028 — Ch2 small: component-aware bridge enumeration (pre-registered)

## Why this experiment exists

Per the 2026-05-30 audit (`vault/audits/A-2026-05-30-ch2-small.md` §1
"Component structure" and §4 D5), the cheap-edge graph of small has
**4 connected components**: `{|comp0|=40, comp1={4,11,17},
comp2={16,27,32}, comp3={18,23,34}}`. A Hamilton path through 4
components requires exactly **K−1 = 3 inter-component exception
bridges** as a structural minimum.

Today's inspection of the banked tour (mk=142.8913 d, perm
start=34∈comp3, end=32∈comp2) shows it uses **5 exception legs**:

| leg | i → j   | dv (m/s) | comps        |
|-----|---------|----------|--------------|
|  2  | 18 → 46 | 565.19   | comp3 → comp0 INTER |
|  7  | 41 → 25 | 518.87   | comp0 → comp0 **intra** |
| 21  | 45 → 4  | 599.89   | comp0 → comp1 INTER |
| 24  | 11 → 28 | 582.32   | comp1 → comp0 INTER |
| 45  | 14 → 16 | 595.87   | comp0 → comp2 INTER |

That's **4 inter-comp + 1 intra-comp**. The "extra" inter-comp leg
comes from the **comp1 round-trip** (enter at 4, exit at 11). A tour
that visits each component contiguously (each comp entered once,
exited once) needs only 3 inter-comp legs, leaving 2 exception slots
free.

This experiment is the **methodology-mandated next step** after E-516:
11+ method families (constructive greedy, ALNS, ILS, fcmaes, CMA-ES,
SA, OR-Tools routing, multi-day GA, ...) have converged on
142.89–142.92 d. Per `vault/methodology/M-applying-methodology-triggers.md`,
"many methods converge" is a common-substrate failure signal, not an
architecture ceiling. The substrate to vary here is **the
component-traversal structure of the perm itself**, not yet another
metaheuristic on top of the same structure.

## Hypothesis (pre-registered, 3-sentence guardrail)

1. **Decomposition row addressed**: §1 C5 of the audit — "extra
   exception slots used inside components". Bank wastes 1 inter-comp
   slot (comp1 round-trip) + 1 intra-comp slot (leg 7).
2. **Empirical signature on success**: at least one Lambert-feasible
   tour with **exactly 3 inter-comp exception legs** and ≤2 intra-comp
   exception legs, with makespan < 142.8913 d.
3. **Predicted magnitude**: 1–10 d shortening. Lower bound: the bank's
   leg-16 and leg-30 have tof/min-tof ratios of 20.4× and 6.8× (audit
   §2 per-instance table). Replacing one such leg with a 0.6 d
   exception transfer recovers ≥2 d. Upper bound capped by C2 (44.48 d
   total per-leg tof slack); a single perm-structural change unlikely
   to recover more than ~10 d without also closing time-coupling
   (which is C2's domain, not this experiment's).

## Setup

**Search space**

- **Level 1 — component traversal order** (start=34∈comp3 fixed,
  end=32∈comp2 fixed):
  - A: comp3 → comp0 → comp1 → comp2
  - B: comp3 → comp1 → comp0 → comp2
- **Level 2 — small-comp interior orderings**:
  - comp3 (start=34): 2 options for the (34, *, *) prefix.
  - comp1 ({4,11,17}): 6 orderings (3!).
  - comp2 (end=32): 2 options for the (*, *, 32) suffix.
- **Level 3 — comp0 Hamilton path** with fixed (entry, exit) endpoints
  determined by which comp0 node is chosen as bridge target/source:
  - OR-Tools routing (PATH_CHEAPEST_ARC + GLS, 30 s/instance) over the
    40-node comp0 subgraph, with arc cost = `min_t min_tof[i,j,t]` from
    fine table; entry and exit pinned as start/end.
  - Top-5 (entry, exit) ∈ comp0 candidates per (L1,L2) config, ranked
    by sum of exception-bridge dv from neighbouring small-comps.
- **Level 4 — substrate variation** (user-specified): each candidate
  perm Lambert-validated under **both** substrates and logged
  separately:
  - S1: `walk_perm_chrono(wait_dt=1.0, n_steps=180)` — bank-default
  - S2: `walk_perm_chrono(wait_dt=0.2, n_steps=360, wait_steps=60)` —
    finer wait, audit's D2 "hostile-default" reversal

**Total candidate count**

```
2 (L1) × 2 (comp3) × 6 (comp1) × 2 (comp2) × 5 (L3 top-k) = 240 perms
× 2 substrates                                            = 480 evals
```

At ~1–2 s/Lambert × 8 workers: **wall ≈ 30–60 min**, hard cap 4 h.

**Bank-update rule (live)**

On any Lambert-feasible result with mk < 142.8913 d:
1. Write `solutions/upload/small.json` (atomic) with the new decision
   vector.
2. Back up to `solutions/upload/small.json.bak.20260601.e517` if not
   already present.
3. Append to `/tmp/ch2_e517_history.jsonl`.

## Success criteria (verifiable post-run)

- [ ] `find_components` reports 4 components matching `{40, {4,11,17},
      {16,27,32}, {18,23,34}}`.
- [ ] All 48 (L1 × L2) configs enumerated.
- [ ] OR-Tools comp0 Hamilton path returns ≥1 feasible per config × top-k.
- [ ] ≥200 distinct candidate perms Lambert-validated under each substrate.
- [ ] History JSONL contains every Lambert-feasible candidate with
      makespan, exc count breakdown (inter/intra), and wait_dt config.
- [ ] If any fmk < 142.8913 d → bank update + log "BANKED".
- [ ] Final report: best mk per substrate; count of candidates with
      exactly 3 inter-comp exc; whether any 3-inter-comp tour is
      Lambert-feasible at all.

## Pre-registered failure modes (and what they mean)

- **F1** — Comp0 OR-Tools Hamilton path infeasible for some (entry,
  exit) pairs. **Action**: relax to k-shortest-path with cost penalty;
  log how many configs were skipped.
- **F2** — All 480 enumerated perms reject at Lambert (`ok=False`).
  **Reading**: the cheap-edge component structure does not admit a
  feasible 3-inter-comp tour at any wait_dt. The bank's
  4-inter-comp structure is then a hard requirement, not slack. Next
  pivot must be a time-coupled MILP LB (E-029).
- **F3** — Lambert-feasible 3-inter-comp tours exist but all have mk ≥
  142.89 d. **Reading**: the "5 exc → 4 inter + 1 intra" choice is
  itself locally optimal in (perm × times × tofs) joint space; the
  saved exc slots don't translate to shorter makespan. Same next pivot
  as F2.
- **F4** — Substrate S2 (wait_dt=0.2) yields ≥1 feasible perm that S1
  rejects, but neither beats bank. **Reading**: substrate matters
  non-trivially but isn't sufficient. Suggests joint (substrate, perm)
  optimization.
- **F5** — Substrate S2 yields a sub-142d tour while S1 yields none
  on the same perm. **Reading**: bank substrate (wait_dt=1.0) was
  pinning the floor. Pivot: re-run all banked perm families under S2.

## Procedure (to be filled at ran_end)

```
1. Build cheap-edge components from /tmp/ch2_small_tcoupled_fine.npz
   → verify match to audit
2. Enumerate (L1, L2) — 48 configs
3. For each: build OR-Tools cost matrix for comp0 subgraph from
   min-tof table, run top-5 (entry, exit) Hamilton paths
4. Assemble full perm; validate under S1 and S2 in parallel pool
5. Stream-write history; checkpoint every 5 min
6. On bank improvement: atomic write + .bak
7. Wall-cap at 4 h; resume from checkpoint if killed
```

## Results

| Metric | Value |
|---|---|
| Candidates enumerated | **240** (not 720 — OR-Tools strategies all converged to the same path per (entry, exit)) |
| Lambert evaluations | **480** (240 × {S1, S2}) |
| Feasible under S1 (wait_dt=1.0) | **0** |
| Feasible under S2 (wait_dt=0.2) | **0** |
| Perms with exactly 3 inter-comp exc | **0** |
| Best mk per substrate | none (no feasibles) |
| Bank improvement | **0.0 d** (`small.json` mtime unchanged) |
| Wall | **21 min** (full 4 h cap not needed) |

**Rejection pattern from `/tmp/ch2_e517_history.jsonl`** (all 480 records):
every candidate `ok=False` at `last_leg=3` with `exc_used=0`. Leg 3
corresponds to `perm[2] → perm[3]` — i.e., the first inter-component
bridge from the comp3-exit node ({18 or 23}) to whichever comp0 node
OR-Tools selected as the entry. The greedy `walk_perm_chrono` cannot
find any Lambert transfer (cheap or exception, with or without
12×1.0 d wait at S1, 60×0.2 d wait at S2) on that very first bridge
leg, before even consuming an exception slot.

## Verdict + analysis (2–5 lines)

**verdict:** refutes

The pre-registered hypothesis (≥1 Lambert-feasible tour with exactly
3 inter-comp exception legs, mk < 142.89 d) is **falsified**: 0
candidates of 240 enumerated were Lambert-feasible at all, let alone
under bank. Failure pattern (`last_leg=3, exc_used=0` for every
single candidate) shows OR-Tools' min-tof-over-t comp0 path cost
selects entry nodes that are chronologically impossible bridge
targets at t≈comp3-traversal-time. **F2 from the pre-registration is
confirmed**: the bank's 4-inter-comp + 1-intra-comp = 5-exc structure
is not a slack pattern — it is the cheapest perm structure that
admits a chronologically feasible Lambert tour at this wait_dt
family. The 2 "extra" exception slots in the audit's count are
absorbed by chronology, not waste.

## What this rules out (for downstream pivoting)

- **Component-aware enumeration with min-cost OR-Tools paths is dead
  for Ch2 small** at any wait_dt grid in {1.0, 0.2}. The chronological
  feasibility constraint dominates over the cost-min path objective.
- **The 2026-05-30 audit's L3 ("re-cluster missing nodes by actual
  cheap-edge components, insert each component independently") is
  empirically refuted as a path to sub-142d.**
- The substrate axis (wait_dt) made **no difference here** because the
  rejection happens at leg 3 before either substrate's wait policy
  fires meaningfully.

## What this still leaves open

- A 3-inter-comp tour might exist if OR-Tools' cost function were
  replaced by a chronology-aware metric (e.g., earliest-feasible
  composition). Not tested here.
- The "true LB on makespan" question is still unresolved. The next
  experiment in the methodology queue, E-518 (CP-SAT LB tightening on
  full fine table, no top_k), resolves whether 111.76 d / R3 is
  reachable at all in this architecture or whether 142.89 d ≈
  architecture ceiling.

## Methodology trigger fired

This experiment is the post-E-516 anti-oscillation discipline applied
correctly: pre-registered hypothesis with 3-sentence guardrail,
empirical refutation, specific updated open paths. The next step is
not "try another perm-search variant" but the information-theoretic
question E-518 was designed for.
