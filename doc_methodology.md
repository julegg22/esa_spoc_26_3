# doc_methodology.md — how we find the wall, and how the vault mirrors it

**Central, living synthesis.** This is the hub document for the methodology we
derived while breaking a string of false "walls" (2026-06 → 2026-07). It
describes in detail: (1) the **abstraction ladder** (the levels a mismatch can
live at), (2) the **vault structure that mirrors it** (how conclusions carry
their assumptions), and (3) the **processes** that run on that structure
(sweep, invalidation cascade, housekeeping).

It is a *synthesis and index*, not the sole source of truth. The atomic,
canonical versions live in `vault/methodology/M-general-*` and are linked
inline. **Keep this file in sync**: when the ladder, the rules R1–R5, the
Assumption-Register schema, or the cascade change, update this file in the
**same commit** (a `doc-methodology-stale` habit is a bug). CLAUDE.md §5 and
META.md point here.

Canonical sources:
- `vault/methodology/M-general-abstraction-ladder-audit.md` — the ladder + sweep + R1–R5
- `vault/methodology/M-general-assumption-provenance-and-invalidation.md` — the vault-as-assumption-TMS
- `vault/methodology/M-general-resource-commitment-gate.md` — when to commit long compute
- `vault/methodology/M-general-deep-single-prompt-audit.md` — the audit these plug into
- `vault/assumptions.md` — the live Assumption Register
- `META.md §15` — the invalidation cascade (now generalized to all levels)
- `doc_lessons.md` — **companion case library**: how we failed (harness+methodology root causes) + the directives that broke walls, each now codified as a rung/rule/trigger

---

## 0. The core thesis — search the structure, not the encoding

Our recurring failure was running **generic search** (ALNS / beam / DP / MILP)
on a **convenient encoding** (e.g. a uniform time grid), then declaring the
problem "walled" when that search converged. The rank-1 teams instead first
**discover the problem's native structure** (narrow phasing windows, node
clusters, components), match the representation and evaluator resolution to
that structure's scale, **decompose → specialize → couple**, and only then
search — on the structured representation.

Every past "wall" is re-read as *generic search exhausted on a mismatched
choice at some level of abstraction* — never as the problem's true optimum.
The rest of this document makes that operational.

---

## 1. The Abstraction Ladder — where a wall can live

A candidate solution and the search that produces it rest on a **stack of
choices**. A mismatch can sit on any rung; **the higher the rung, the more
futile all effort below it.** Eight rungs in three tiers:

### Tier A — Are we solving the right problem, and do we see its structure?
- **L1 Objective** — Are we optimizing the true root goal, or a proxy?
  *Mismatch looks like:* a metric that improves while rank/score doesn't.
  *Probe:* re-state the current target in the root objective.
- **L2 Model / Formulation** — Does our model faithfully capture the real
  problem's constraints / physics / feasibility?
  *Mismatch:* a hidden hardcode or wrong feasibility test (idD=0; eccentric
  departure; solver "valid" flag ≠ official gate).
  *Probe:* re-validate against the official scorer/code, not our prose.
- **L3 Structure** — Have we identified the native exploitable structure
  (windows, clusters, components) and are we decomposing along it?
  *Mismatch:* treating a decomposable problem as monolithic.
  *Probe:* measure the structure (window widths, component sizes, cluster count).

### Tier B — Can we even represent and score the optimum?
- **L4 Encoding / Representation** — Can our encoding *represent* a solution as
  good as the target, at the structure's scale?
  *Mismatch:* fixed grid can't sit in ~0.002 d windows; retiming a fixed order
  can't remove order-forced idle; the epoch-shift trap.
  *Probe:* can the current encoding even *express* a known-better solution?
- **L5 Evaluator / Oracle** — Is fitness/feasibility faithful and at the right
  resolution? Does it tell the truth?
  *Mismatch:* coarse evaluator blind to narrow windows; the 8-probe cheap-graph
  undercount; optimistic/partial evaluators.
  *Probe:* diversity-of-method cross-check; reconstruct the banked objective exactly.

### Tier C — Can our search find it?
- **L6 Solver / Algorithm family** — Right paradigm for this structure? Can it
  express **all** constraints natively?
  *Mismatch:* GLKH/GTSP can't express the ≤5-exception constraint; MILP too big.
  *Probe:* does the solver even admit the constraint / size?
- **L7 Operators / Neighborhood / Acceptance** — Can the moves reach the
  optimum's basin?
  *Mismatch:* local moves only, no destroy+rebuild (basin-locked).
  *Probe:* does an acceptance metaheuristic + structural ruin cross the basin?
- **L8 Parameters / Resolution / Compute** — Tuning, grid resolution,
  iterations, restarts, budget. *Usually **not** where big gaps live — but
  where we habitually reach first.*

> **Empirical pattern:** our breakthroughs have walked *down* the ladder —
> L2 model bugs → L5 evaluator undercount → L1 proxy skew → L6 solver
> expressiveness → now **L4 encoding / L3 structure**. Each was an assumption
> flip one rung deeper. The remaining rungs are where rank-1 sits.

---

## 2. The sweep + the five rules

**When it fires:** any "stuck / walled / plateau / ceiling / exhausted"
verdict, **or** the instinct "more compute / another solver variant."

**Procedure — sweep TOP-DOWN.** For each rung: state the current choice; name
what a mismatch *looks like*; run the **cheapest probe** that would reveal one
(often arithmetic on the banked artifact); mark it **ruled-out (by measurement)**
or **SUSPECT**. **The wall is the highest rung whose probe returns "mismatch."
Fix there.** Complete the pass — don't stop at the first convenient (low) mismatch.

**The rules:**
- **R1 — Name the level.** No "exhausted/walled/closed" verdict is admissible
  unless it states *"exhausted at level L, levels 1..L-1 ruled out by
  measurement M."* Exhausted *within* a level ≠ exhausted *of* the problem.
- **R2 — A tool wall is a solver-level (L6) fact, not lever death.** Before
  abandoning a lever (L3/L4), try the **minimal level-changing swap** (a solver
  that expresses the constraint). Separate ABSTRACTION from IMPLEMENTATION.
- **R3 — Sibling-transfer scan.** If the problem is one of a family
  (sizes/variants), ask: does a tool/insight from a *sibling* instance realize
  this lever? Search siblings' subtrees.
- **R4 — Relaxation-beats-target ⇒ constraint-handling gap.** If a relaxed run
  blows *past* the target (e.g. 75.2 d with 25 exceptions vs 100.4 d with ≤5),
  the structure **contains** the solution; the gap is **constraint-handling**
  (L4/L6), not search. Find a tool that enforces the constraint natively —
  never file "capped."
- **R5 — Cost-asymmetry counter-bias.** High rungs are expensive to reconsider,
  low rungs cheap — so you are biased to grind L7/L8. The top-down order exists
  to counter exactly this. Reaching for compute/restarts/another solver variant
  *without a completed sweep* is the tell: STOP and sweep.

---

## 3. Conditional validity — every conclusion inherits its branch's assumptions

A conclusion (a bank, a floor, a "walled" verdict) is only valid **given the
assumptions of its experiment**, and those assumptions are **inherited from the
whole branch** that produced it. When an assumption at any rung flips, every
downstream conclusion that rested on it becomes conditional — potentially a
wide swath of the tree, cutting across derivation branches (two different
branches can share the encoding assumption).

This is a **truth-maintenance** problem: conclusions are *justified by*
assumptions; retract an assumption → dependents lose justification → re-triage.
The vault must represent the **assumption-dependency relation**, which is *not*
the same as the derivation (`parent`) relation.

---

## 4. The vault structure that mirrors the ladder

We keep the derivation tree (`parent` = narrative/history) and **overlay** two
relations on it:

**(a) The Assumption Register — `vault/assumptions.md`** (tier-1 active memory).
The single home for **load-bearing assumptions** (the assumption analogue of
the single-frontier `open-paths.md`). Each row:

| ID | ladder level | falsifiable statement | status {holds\|suspect\|refuted} | underpins | on-flip action |

Rows are seeded from our own history and grouped by status. A `holds` row is a
currently-trusted premise; a `refuted` row has dependents needing triage.

**(b) `assumes:` provenance on conclusions.** Load-bearing nodes (banks,
floors, wall verdicts) carry `assumes: [ID, …]` in frontmatter — their **new**
assumptions. **Effective validity = `assumes` ∪ the transitive closure up
`parent`.** That is the vault encoding of "all previous branch assumptions
play a role." Exploratory probes may skip it.

**(c) Ladder tags on nodes.** Every wall verdict carries `wall_level: Lx` (R1);
the `invalidation:` overlay carries `level: Lx` (which rung failed). This makes
"which level are we stuck on / grinding" queryable.

**(d) Lever / implementation split** (R2). A tool wall is recorded on the
*implementation* node (`wall_level: L6`); the *lever* (its H, its `open-paths`
entry) stays **open**. A lever leaves `open-paths.md` only when its **level** is
R1-exhausted — not when one tool fails. `open-paths.md` carries a ladder-level
column so high-rung (Tier A/B) levers stay visible (R5).

**Why not just the tree?** The derivation tree is right for history and the
episodic loop, but validity is a *different* relation that doesn't coincide
with it. So: **keep the tree, overlay the assumption-dependency DAG (register +
`assumes:`) and the ladder tags.** The vault already proved it can carry
overlay-invalidation (META §15 code cascade); this generalizes it to all rungs.

---

## 5. The processes on the structure

### 5.1 Invalidation cascade (META §15, trigger **T6**)
When a register row flips to `suspect`/`refuted` at **any** level:
1. **Find dependents:** `git grep -l "assumes:.*<ID>"` + branch inheritance;
   the row's `underpins` names the class up front.
2. **Overlay, don't delete:** add the `invalidation:` block with `level: Lx`.
   The original `verdict` stays — it was true under its assumptions.
3. **Triage each dependent into one bucket:**
   - **RE-RUN** — a tool/encoding artifact; redo under the corrected assumption
     (the [[broken-tool-retry-queue]] / TOOL-ARTIFACT 🔧 bucket).
   - **REFRAME** — meaning changes, no re-run (e.g. a proxy-skew re-statement).
   - **STILL-HOLDS** — the assumption wasn't load-bearing here; annotate.
4. **Backlog + cadence:** retro-tag incrementally, highest-value first; the
   weekly review consumes the queue.

*Old experiments are never wrong or deleted* — they recorded a real result
under their assumptions; they gain an overlay and a triage bucket.

### 5.2 Housekeeping (keeps the mirror honest)
`scripts/housekeeping_check.py` (run at resume + wind-down + every loop tick):
- `check_assumption_register` — refuted/suspect assumptions with dependents
  that cite them via `assumes:` but carry no `invalidation:` overlay (the
  un-triaged backlog). Forward-looking: quiet until `assumes:` is adopted.
- existing: uncommitted vault, untracked scripts, dangling links, MEMORY.md
  pointer rot, cache-without-generator.

A wall verdict without `wall_level`, or a load-bearing conclusion without
`assumes:`, is drift to fix.

### 5.3 Resource-commitment gate (for long compute)
Before any **>10 h** job (`vault/methodology/M-general-resource-commitment-gate.md`):
commit only if **(1) confident** (grounded in a measurement), **(2) validity
pre-tested** (positive control passes in minutes, evaluator faithful, small dry
run reproduces), **(3) live-monitored** (checkpoint + resumable + a metric that
advances + a kill criterion). Budget backward from any hard bound so the
*search* never starves behind the *precompute*.

---

## 6. Worked example — the Ch2 encoding case (the whole loop in one)

1. **Stuck:** Ch2 medium/small "floored"; small GTSP filed "closed."
2. **Sweep (top-down):** L1 objective ✓ (rank is the goal). L2 model ✓. L3
   structure — narrow windows, real. **L4 encoding — MISMATCH:** E-759 shows
   medium idle (12.4 d) is 100 % *order-forced*, 0.0 d retime-removable → a
   fixed-order-on-a-grid encoding cannot reach the optimum. **L6 solver —
   MISMATCH:** GLKH can't express ≤5 exceptions (R4: relaxed run hits 75.2 d ≪
   100.4 d target → constraint-handling gap, not search).
3. **R2 + R3:** the small "GTSP closed" verdict was a *tool* wall (L6), not
   lever death; the sibling **medium** engine (exact continuous-time DP + LNS)
   enforces ≤5 natively → it *is* small's fix.
4. **Register:** flip `ENC-grid` (L4) and `SOLVER-gtsp-exc` (L6) to REFUTED;
   dependents (the retiming/GTSP "floors") → **RE-RUN** bucket.
5. **Act:** run the exact-DP+LNS on small (E-760) — the RE-RUN — toward rank-1;
   on validation, graduate to medium (reorder) then large (cluster-decompose +
   couple).

---

## 7. Cadence & triggers — when each action fires

Actions here are driven by **three kinds of trigger**, not one:
- **Event/state triggers** (the majority) — a run completes, a wall verdict
  forms, an assumption flips, a metric plateaus. Fire the moment the condition
  holds, regardless of the clock.
- **Time/cadence triggers** — the loop heartbeat (minutes), the weekly review.
- **Pre-action gates** — a checklist that must pass BEFORE a heavy/irreversible
  action (long compute, writing a wall verdict, adding a default).

The recurring error is running everything on the *time* heartbeat (babysitting)
while the methodology's real triggers are *semantic*. Map each action to its
**true** trigger.

### 7.1 Trigger table

| # | Action | Trigger (type) | When / cadence | Why | How |
|---|--------|----------------|----------------|-----|-----|
| 1 | Health-check jobs + light housekeeping | heartbeat (time) | every `/loop` tick (~10–25 min) | keep cores productive; catch dead runs early | ps/grep liveness, log freshness, `housekeeping_check.py` |
| 2 | Validate result; record verdict (+`assumes`,+`wall_level`); pick next lever | completion (event) | on task-notification / Monitor hit | act on results at once, not next heartbeat | re-verify with the official evaluator; write the E node |
| 3 | **Ladder sweep → act at highest mismatched rung** | **plateau (state)** | K attempts / T hours at one rung, no target-progress | R5: stop grinding the cheap rung | §1–§2 top-down sweep; NOT a finer-resolution / more-operators reflex |
| 4 | R1 admissibility check | wall-verdict (pre-write gate) | before writing "walled/exhausted/closed" | no false exhaustion | name the level + measurement ruling out higher rungs; else sweep first |
| 5 | Register flip + **T6 cascade** | assumption-flip (event) | a sweep/audit/bugfix refutes a premise | propagate invalidation | flip row → grep `assumes:` → overlay `invalidation:{level}` → triage RE-RUN/REFRAME/HOLDS |
| 6 | Resource-commitment gate | pre-long-launch (gate) | before any >10 h job | don't waste compute | 3 checks (confident / validated / monitored); budget backward |
| 7 | Hostile-default audit | pre-default (gate) | adding a default value | bug-surfacing | what if maximally adversarial? |
| 8 | Ladder sweep (upgraded convergence pivot) | convergence (state) | 3+ same-family methods converge (M-004) | family-convergence ≠ ceiling | run the full sweep, not just an orthogonal-family swap |
| 9 | Orientation / housekeeping / session note / §15 checklist | session-boundary (event) | resume + wind-down | continuity + drift control | CLAUDE.md §7 reads; `housekeeping_check.py`; write the S node |
| 10 | Weekly review + backlog drain | weekly (time) | cloud cron, 7-day | consolidation | `reviews/`; drain the RE-RUN queue, dangling links, un-triaged assumptions |

### 7.2 Control primitives — `/loop` (explore) vs `/goal` (exploit)

Two-level control that mirrors explore/exploit:

- **`/loop` = the OUTER research loop (exploration).** Diagnosis-driven,
  open-ended: health-check → on plateau run the **ladder sweep** → pick the
  lever at the identified rung → maybe delegate a bounded sub-task to `/goal` →
  on result, record + pivot. Handles triggers 1–3, 8. Time-paced heartbeat with
  event-gating (Monitor / task-notification wake it sooner). **Never auto-stops
  (open-ended research); never auto-submits.**
- **`/goal` = the INNER bounded execution (exploitation).** Drive ONE
  *validated, level-checked* lever to a *verifiable, reachable* target — e.g.
  `/goal solutions/upload/small.json is_feasible AND makespan ≤ 111.76, OR stop
  after 15 turns / after 5 turns with no proxy improvement`. The `/goal`
  evaluator reads only the transcript, so **our turns must print the metric it
  checks.** Two hard cautions: **(a)** always include an **escape clause**
  (turn-cap or no-improvement-cap) so hitting a wall kicks back to `/loop` for a
  ladder sweep — `/goal` has no sweep of its own and will otherwise grind a
  mismatched level (an **R5 violation at the control layer**); **(b)** never put
  a submission in a `/goal` condition (user-gated).

Realization: heartbeat → `ScheduleWakeup`; completion → task-notification /
`Monitor`; plateau → a counter carried in the loop state, checked each tick;
weekly → `CronCreate` (cloud). The semantic gates (R1, T6, resource gate) fire
**inline** by following the CLAUDE.md §5a triggers — they are not scheduled.

### 7.3 Adjusted `/loop` directive skeleton

The prior template's plateau branch ("finer resolution OR more operators") was
itself an **R5 violation** — it jumped to L8/L7 without a sweep. Corrected:

```
Each tick:
  1. health-check the active job(s); run housekeeping_check.py (light).
  2. on completion/new-best: re-verify with the OFFICIAL evaluator; record the
     verdict (+assumes +wall_level); if a premise was refuted, flip its
     register row + run the T6 cascade; pick the next lever.
  3. PLATEAU CHECK: if K ticks / T hours at one rung with no target-progress
     -> run the ABSTRACTION-LADDER SWEEP (top-down); act at the HIGHEST
     mismatched rung. Do NOT default to finer resolution / more operators.
  4. before any >10 h launch: resource-commitment gate.
  5. report: stage + best-vs-target + which RUNG we are working; RESCHEDULE.
  NEVER auto-stop (open-ended). NEVER auto-submit (user-gated).
```

### 7.4 Proposed commands (build when recurrence justifies it)

- **`/cascade <assumption-id | description>`** — runs the T6 procedure
  end-to-end: flip/confirm the register row, `git grep` the dependents, add
  `invalidation:{level}` overlays, print the RE-RUN / REFRAME / STILL-HOLDS
  triage. *Trigger:* an assumption flips. *Why a command:* mechanical + recurring
  (our history flips premises often) and benefits from a checklist.
  **Recommended.**
- **`/sweep <instance>`** — a fast standalone ladder sweep (§1–§2) emitting the
  highest mismatched rung + the fix, *without* the full 4-phase `/deepaudit`.
  *Trigger:* plateau / convergence / "stuck". *Why maybe not yet:* `/deepaudit`
  already embeds the ladder as its Phase-1 spine — build `/sweep` only if we want
  the quick check separate from the full audit.

## 8. Change log (keep this current)

- **2026-07-01** — Created. Consolidates the abstraction-ladder audit, the
  assumption-provenance / multi-level invalidation model, and the
  resource-commitment gate, derived post-challenge (final standing 7th) after
  HRI rank-1 intel (structure + specialized metaheuristics, not compute).
- **2026-07-01** — Added §7 Cadence & triggers: the event/time/gate trigger
  taxonomy + table, the `/loop`(explore)–`/goal`(exploit) two-level control
  model, the corrected `/loop` skeleton (the old plateau branch was an R5
  violation), and proposed `/cascade` + `/sweep` commands.
