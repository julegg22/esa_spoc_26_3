# Assumption Register

The single home for **load-bearing assumptions** — the premises our banked
results and "walled/exhausted" verdicts rest on. The assumption analogue of the
single-frontier `open-paths.md`. Procedure: [[methodology/M-general-assumption-provenance-and-invalidation]].
Levels: the abstraction ladder ([[methodology/M-general-abstraction-ladder-audit]])
— L1 objective · L2 model · L3 structure · L4 encoding · L5 evaluator · L6 solver ·
L7 operators · L8 params.

**How to use.** A load-bearing conclusion (bank, floor, wall) lists in frontmatter `assumes:
[ID, …]` the premises it **depends on holding** (effective validity = that set ∪
the branch's inherited set). An experiment that is the **RE-RUN of a refuted
row** references it via `reruns: [ID]` — it *addresses* the flip, it doesn't
depend on the old premise holding — so it is correctly NOT flagged as an
un-triaged dependent. When a row flips to `suspect`/`refuted`, run the
propagation (META §15 + M-assumption-provenance): `git grep "assumes:.*<ID>"`,
overlay `invalidation:{level}`, triage each dependent → **RE-RUN / REFRAME /
STILL-HOLDS**. Never delete the old conclusion — it was true under its assumptions.

## Active (holds — currently trusted)

| ID | L | Assumption (falsifiable) | Status | Underpins | On-flip |
|----|---|--------------------------|--------|-----------|---------|
| `EVAL-lambert` | L5 | `compute_transfer` (pykep multi-rev Lambert about the Moon) is the faithful Δv oracle; it matches the official `kt.fitness`. | holds (pos-controls track official, viols 0) | all Ch2 edge costs | rebuild every Ch2 window/graph cache |
| `MODEL-official-feas` | L2 | `udp.fitness<0` / `kt.is_feasible` is the true feasibility gate (not a solver-internal "valid" flag). | holds | all banks (Ch1+Ch2) | re-validate every bank at the official gate |
| `STRUCT-cheap-windows` | L3 | Ch2 cheap-Δv transfers form narrow (epoch,tof) windows recurring on the synodic beat; the problem is joint order + window selection. | holds (E-710/E-759; HRI intel) | the whole Ch2 rank-1 method | re-derive the native structure |

## Suspect / under test

| ID | L | Assumption (falsifiable) | Status | Underpins | On-flip |
|----|---|--------------------------|--------|-----------|---------|
| `STRUCT-large-monolithic` | L3 | Ch2-large is best attacked as one 601-giant walk (not cluster-decomposed + coupled). | **suspect** (HRI intel: they cluster-decompose+couple) | large "601-giant wall" verdicts (E-710/E-750) | build cluster-decompose → per-cluster solve → couple |

## Refuted (flipped — dependents need triage)

| ID | L | Assumption (was believed) | Refuted by | Underpinned | Dependent triage |
|----|---|---------------------------|-----------|-------------|------------------|
| `ENC-grid` | **L4** | A Ch2 makespan-optimal tour is reachable by retiming a fixed visit order on a uniform time-grid encoding. | E-759 (idle 100% order-forced, 0.0d retime-removable); C-036 epoch-shift trap | Ch2 retiming-based "floor/walled" verdicts (medium M1 null; small retime floor) | **RE-RUN realized on small** (E-760): validated 112.996->111.96; the rank-1 residual is now L4. Medium/large RE-RUN pending. |
| `SOLVER-gtsp-exc` | L6 | GLKH/GTSP can enforce the hard ≤5-exception constraint. | E-746 (abuses exceptions → 75.2d infeasible, or strands when penalized) | "Ch2-small GTSP lever CLOSED" (E-746 verdict) | **RE-RUN realized on small** (E-760): exact-DP+LNS enforces ≤5 natively, validated (beats bank). R2/R4 case. |
| `EVAL-8probe` | L5 | The Ch2-large cheap-edge graph from 8 fixed (t,tof) probes/pair is complete. | E-721 (+6,200 cheap edges on faithful rescan) | large "566 wall / 4-comp-dominates / 35-hard-cities" | RE-RUN — done (E-721 rebuilt on faithful graph) |
| `MODEL-circular-dep` | L2 | Ch1 `solve_departure_dv` need only handle circular Earth orbits. | E-701 (eccentric mirror; ~8 prior "per-pair closed" were this bug) | ~8 Ch1 trajectory "per-pair CLOSED" verdicts | RE-RUN — done (eccentric backward-shoot) |
| `MODEL-idD0` | L2 | Ch1 `official_row` with idD=0 gives the correct cargo mass. | E-757 (wrong cld; forced-test "valid" ≠ official) | moderate-TOF "+611 kg" wins | RE-RUN — done (real-idD revalidation caught 0/246) |
| `OBJ-completeness` | L1 | Ch2-large beam quality is well-judged by cities-threaded (completeness). | root-objective-proxy-skew (already at rank-1 *pace* at 575/601) | "575/601 wall = moonshot" framing | REFRAME — judge by rank/makespan, not completeness |

---

*Pattern (see M-assumption-provenance §Evidence): our breakthroughs walk DOWN the
ladder — L2 → L5 → L1 → L6 → now L4/L3. The open frontier (`ENC-grid` L4,
`STRUCT-large-monolithic` L3) is where rank-1 sits.*
