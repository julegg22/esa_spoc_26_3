# doc_lessons.md — case library: how we failed, and what broke the walls

Companion to `doc_methodology.md`. That file is the *system* (levels, vault
structure, cadence). This file is the *evidence*: concrete cases from the
campaign (2026-05 → 2026-07), split into **(1) failures** — the harness +
methodology **root cause** that let a false verdict or waste persist (not just
"a bug") — and **(2) breakthrough directives** — the explicit user prods that
surpassed an assumed wall, plus **how each is now codified** so the prod is no
longer needed.

The through-line: **almost every "wall" was a mismatch at some abstraction
level, or a proxy/assumption error — never the problem's true optimum.** The
human repeatedly supplied the prior "this is not a real wall." The goal of the
new methodology is to make that prior *structural* — the ladder, the assumption
register, the triggers — so we generate it ourselves.

Keep current: add a case whenever a wall is broken or a process root-cause is
identified. Cross-refs point to `doc_methodology.md` rungs (L1–L8) / rules
(R1–R5) and the vault nodes.

---

## Part 1 — Failure cases (harness + methodology root cause)

### F1. The control layer grinding the cheap rung — "try finer resolution or add operators"
- **What happened.** A `/loop` directive's plateau branch read *"if it
  plateaus → finer resolution OR add 2-opt/ruin-recreate moves."* That jumps
  straight to rungs **L8 (params)** / **L7 (operators)**.
- **Root cause (harness + methodology).** The control tool (`/loop`) is
  *time-paced*, but the methodology's real trigger on a plateau is *semantic*
  (run a ladder sweep). With no semantic trigger encoded, the directive
  defaulted to the **cheapest low-rung tweak** — cost-asymmetry bias (**R5**)
  baked into the control layer itself. The tooling shaped the error.
- **Now prevented by.** `doc_methodology.md §7.3` corrected `/loop` skeleton
  (plateau → **ladder sweep**, act at the highest mismatched rung) + the CLAUDE.md
  §5a plateau trigger + the `/goal` escape-clause rule (§7.2). *(Self-caught this
  session — the directive I had just written violated the rule I had just
  written.)*

### F2. "GTSP closed for small" — a tool wall filed as lever death
- **What happened.** The small joint sequence+epoch lever was filed **closed**
  (E-746) because GLKH couldn't express the ≤5-exception constraint (it abused
  exceptions → 75.2 d infeasible, or stranded when penalized).
- **Root cause.** No separation of the **lever** (abstraction: joint
  window-indexed search) from the **implementation** (GLKH). A wall at **L6
  (solver)** was mis-attributed to the whole lever. Per-instance silos hid that
  the **sibling medium engine** (exact continuous-time DP + LNS) enforces ≤5
  *natively* — it was the fix all along.
- **Now prevented by.** **R2** (tool wall ≠ lever death → minimal
  level-changing swap), **R3** (sibling-transfer scan), **R4** (relaxation hit
  75.2 d ≪ 100.4 d → the structure *contains* the answer; the gap is
  constraint-handling, not search). Register `SOLVER-gtsp-exc` (L6) → **RE-RUN**
  (E-760, running).

### F3. Encoding invisible to our audits for weeks
- **What happened.** Ch2 "floors" (medium/small) persisted; the real limit was
  the **L4 encoding** (uniform time grid retiming a fixed order can't remove
  order-forced idle). Our audits *listed* "encoding" but never pressure-tested it.
- **Root cause.** A **flat assumption list** gets uneven, low-biased coverage —
  you enumerate a few cheap assumptions, feel thorough, and never probe the high
  rungs. Assumptions weren't first-class or ladder-tagged, so nothing forced a
  top-down pass.
- **Now prevented by.** The **abstraction ladder as the forced spine of Phase 1**
  (rung-by-rung, top-down) + the **Assumption Register** with ladder-tagged rows
  (`ENC-grid` L4 = REFUTED, E-759: idle 100 % order-forced).

### F4. The 16 h precompute that starved the search
- **What happened.** On deadline day, a precompute chain (e531 10.8 h + e542
  5.0 h ≈ 16 h) consumed the window; the actual DP-ALNS got ~1 h and produced
  nothing.
- **Root cause.** No **resource-commitment gate** and no backward budgeting:
  precompute and search must *both* fit a hard bound. The precompute was correct;
  committing to it without reserving search time had negative ROI.
- **Now prevented by.** `M-general-resource-commitment-gate` (confident /
  validity-pre-tested / live-monitored) + "budget backward from any hard bound"
  (`doc_methodology.md §5.3`, trigger #6).

### F5. "575/601 = a moonshot wall" — judged by the wrong metric
- **What happened.** The Ch2-large beam was judged by **completeness** (cities
  threaded); 575/601 read as a wall / moonshot — when it was already at rank-1
  *pace* (≈0.51 d/leg).
- **Root cause.** A **proxy metric (L1)** substituted for the root objective
  (rank/makespan). A correct result in the wrong metric steers the whole program.
- **Now prevented by.** **L1** rung + the "re-state every wall in the ROOT
  objective" trigger + register `OBJ-completeness` → **REFRAME**
  (root-objective-proxy-skew).

### F6. The 8-probe cheap-graph undercount
- **What happened.** Ch2-large's cheap-edge graph was built from **8 fixed
  (t,tof) probes per pair**, missing ~6,200 narrow recurring edges; the "566
  wall / 4-component-dominates / 35-hard-cities" story was substantially artifact.
- **Root cause.** A coarse **evaluator (L5)** was trusted; its resolution
  (probe spacing) wasn't matched to the structure's scale (~0.002 d bands). We
  didn't audit the evaluator first.
- **Now prevented by.** **L5** rung + foundation-then-search ("audit the
  evaluator before the search") + register `EVAL-8probe` → RE-RUN (E-721
  rebuilt on the faithful graph, +6,200 edges).

### F7. Self-inflicted "infra death" and blind runs
- **What happened.** During the autonomous window: my own kill-all cleanups
  were misread as *"multiprocessing is broken"*; oversubscription (competing
  jobs) was read as *"precompute infeasible"*; E-646 ran 85 min with **no output**
  before it could be judged.
- **Root cause (harness discipline).** Not instrumenting (no positive control,
  no progress log), and **misreading process state** (`pgrep -fc` false matches;
  attributing self-inflicted issues to infra). The harness was fine; the reading
  of it wasn't.
- **Now prevented by.** instrument-before-launch (see-it-working + trust-signal
  in ~2 min), count procs via `ps -eo cmd | grep | grep -v grep | wc -l` (not
  `pgrep -fc`), and "test validity before declaring infeasible."

---

## Part 2 — Breakthrough directives (the prods that broke walls) → now codified

Each of these was a **human prior that overruled a false wall**. The point of
the new methodology is that we now *generate* the prior ourselves.

### D1. "I don't buy it — there always existed a lever when we supposedly hit a wall. Reconsider every conclusion that led to the 'walled' verdict, seek attacks, go for the one with highest uncertainty."
- **Wall broken.** Ch1 trajectory "walled" → found idD=0 + the fake solver-
  "valid" flag + stale high-v_inf transfers → **+7,712 kg, a rank gain**.
- **What it revealed.** A wall is a hypothesis about *our reasoning*, not the
  problem; attack the highest-uncertainty load-bearing conclusion first.
- **Now codified as.** The **abstraction-ladder sweep** (mandatory on any wall)
  + **R1** (name the level, rule out higher rungs by measurement) + the
  **Assumption Register** (every load-bearing premise is a falsifiable,
  flippable row) + exhaustion-is-a-transition. We no longer wait for the prod —
  a wall verdict is inadmissible without the sweep.

### D2. "Exhaustion is a transition, not a stop — the difficulty IS the build spec." (2026-06-25, Ch2-large rank-1)
- **Wall broken.** Pivoting to a low-value grind instead of building the hard
  forward path (continuous-time TD-TSP + fast evaluator).
- **Now codified as.** CLAUDE.md **§5b** + `M-general-exhaustion-is-a-transition`
  + the self-check phrase list ("research-heavy", "multi-day", "the competitor's
  method" = build specs, not stop reasons).

### D3. "When experiments are exhausted WITHIN an architecture, reopen the exploration floor — the gap *magnitude* is the discriminator." (2026-06-15)
- **Wall broken.** Grinding local search inside one architecture on a large gap.
- **Now codified as.** Ladder rungs **L3 (structure)** / **L4 (encoding)** +
  architecture-change-on-large-gaps; a large gap ⇒ suspect a high rung, not L8.

### D4. "We're basin-locked, not at a ceiling — need acceptance metaheuristics + targeted destroy + structural rebuild." (2026-06-14)
- **Wall broken.** Many methods converging read as a ceiling.
- **Now codified as.** Ladder rung **L7 (operators/basin)** + basin-overarching-
  search + the **convergence trigger** (3+ same-family methods converge → sweep,
  `doc_methodology.md §7.1 #8`).

### D5. "There is no sandbox — check that. Tooling was often faster than originally estimated."
- **Wall broken.** A self-imposed "medium precompute is infeasible (68 h)"
  estimate — actually oversubscription + a wasted epoch range; clean rate was 4×
  faster.
- **Now codified as.** The **resource-commitment gate** (validity **pre-tested**
  with a real small run before believing an estimate) + "don't declare infeasible
  from a guess — measure it cheaply first."

### D6. HRI rank-1 intel: "not compute — structure discovery + specialized metaheuristics." (2026-07-01)
- **Wall broken.** The whole "we need 10–20× compute / it's a moonshot" framing.
- **Now codified as.** The core thesis **"search the structure, not the
  encoding"** + rungs **L3/L4** + the rank-1 method (discover structure → match
  resolution → decompose/specialize/couple → then search).

### D7. "Marginal or zero improvement is itself a trigger — do an in-depth gap analysis and explore architecturally *different* approaches, not just more local search." (2026-06-15)
- **Wall broken.** Treating a plateau as "done / near-optimal."
- **Now codified as.** The **plateau trigger** → ladder sweep
  (`doc_methodology.md §7.1 #3`); a plateau is a *diagnosis* signal, not a stop.

---

## Part 3 — The meta-pattern

1. **Walls are level-mismatches, not optima.** Every case above resolved to a
   specific rung (L1 proxy, L2 model, L4 encoding, L5 evaluator, L6 solver, L7
   basin) or a resource/harness-discipline gap — never "the problem is just hard."
2. **We drifted low; the human pulled us high.** Left alone we reached for L8/L7
   (compute, params, another solver variant); the prods repeatedly redirected to
   L1–L4 (objective, model, structure, encoding). The ladder's **top-down** order
   is the internalized version of that pull.
3. **A conclusion is only as valid as its assumptions.** The biggest wins were
   flips of a single load-bearing premise; the Assumption Register + T6 cascade
   make those flips propagate instead of hiding.
4. **The aim of this file:** make the human prod unnecessary. Each directive
   above is now a rung, a rule, or a trigger. When we next write "walled,"
   the system — not a person — must first ask *at which level?*

## Change log
- **2026-07-01** — Created. Seven failure cases (F1–F7) with harness+methodology
  root causes, seven breakthrough directives (D1–D7) with their codification, and
  the meta-pattern. Companion to `doc_methodology.md`.
