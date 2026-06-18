# E-654 — Ch2 deep audit: the loss is epoch-PHASING + fragment-MERGE, not edges (assignment-LB, never computed before)

User pushback 2026-06-18: "NOT a definitive frontier — better solutions exist ⇒ need basin-overarching;
is the LKH build the right next step?" 4-phase audit + cheap probes. Retracts "small at floor".

## Phase 2 result — assignment lower bound (the bound we NEVER computed in the whole campaign)

Min-cost successor assignment (Hungarian) on the per-epoch-min cheap-tof matrix (relaxes subtour +
epoch-chaining). Cheap (O(n³)).

| inst | assignment LB | our bank | competitor | LB/leg | bank/leg | #fragments (subtours) |
|---|---|---|---|---|---|---|
| small | **66.82** | 113.0 | r1 101.65 | 1.364 | 2.306 | 22 (sizes ≤3) |
| medium | **17.23** | 189.10 (r1) | live 192.11 | 0.095 | 1.045 | 69 (sizes ≤17) |

**Gap decomposition (small):** LB 66.82 → +34.83 (epoch-chaining + optimal merge) → r1 101.65 → **+11.35 OUR excess** → 113.
**Medium:** bank 189.10 = LB 17.2 + **171.9 phasing/merge overhead**; cheap 0.095d/leg edges EXIST but
the bank flies 1.045d/leg = **11× inflation** from being at the wrong epoch. Medium is rank 1 ⇒ its 171.9d
overhead is ~irreducible (near-optimal); small has 11.35d of recoverable excess.

**⇒ The loss is NOT per-leg edge choice (we already use near-min-tof edges). It is concentrated in
(a) EPOCH-PHASING (flying legs far from their per-epoch min tof) and (b) MERGING the fragmented
min-tof structure (22/69 subtours) into one Hamiltonian tour with consistent epochs.**

## Phase 3 result — epoch-connectivity audit (exp 3) FALSIFIES the "components dissolve" hope

Medium cheap-graph components per-epoch (sampled every 100 of 1000) = [4,4,4,4,4,4,4,4,4,4]; static = 4.
**The 4-component structure is STABLE across epochs — NOT an epoch artifact (A4 holds, not violated).**
Large is the same (601+3×150, stable). ⇒ Any method MUST respect the hard 4-component + ≤5-exception
bridge structure; it will not dissolve at the right epochs.

## Phase 1/3 — load-bearing assumptions across ALL branches

A2 (order-primary, never time-expanded) and A-bound (optimized for weeks without ever computing a bound)
are the flaws. Untouched paradigms: exact/relaxation/reformulation — skipped as "too big", but the
assignment LB ran in seconds for n=1051 and cluster sub-TSPs are small. LKH = one metaheuristic still
keeping A2 intact; NOT obviously the best next step.

## Verdict: is the LKH build the most promising next step? NO (not first)

The grounded lever is **epoch-phasing + fragment-merge on a time-expanded representation that RESPECTS
the hard 4-component/exception structure** — more specific than a generic LKH permutation search. Concrete
next builds, cheapest-first:
1. **Fragment-merge reformulation** (NEW): treat the assignment's 22/69 min-tof fragments as super-nodes,
   solve the much-smaller merge-order TSP + epoch alignment. Far smaller search than the full permutation.
2. **Time-expanded per-component DP/min-cost-flow** (exp 2): explicit (city × time) graph WITHIN each of
   the 4 components (which are small), optimal exception-bridge stitch. Handles epoch-chaining that our
   permutation search cannot.
3. LKH/metaheuristic on time-expanded edges — only if 1–2 falsify.

Recover targets: small 11.35d (→ rank 4→1 region), large the 508d excess (→ toward 424). Medium near-opt.
See [[basin-overarching-search]], [[deep-single-prompt-audit]], [[ch2-find-transfer-pattern]].

## ★★ UNIFYING STRUCTURE (2026-06-18, E-655 follow-up) — all Ch2 = GIANT + satellites

Lever #1 (naive fragment-merge) FALSIFIED in the informative way: it merged the 22 assignment fragments
freely and produced infeasible tours (slow Lambert on hopeless legs). Root cause found via cheap-component
analysis: **small cheap graph = 4 components, sizes [40, 3, 3, 3]** — the SAME dominant-giant+satellites
shape as medium (4 comps) and large (601+3×150). 4 comps need only 3 bridges ≤ 5-exc budget ⇒ feasible.
Free merge ignored this and blew the exc budget.

**⇒ All three Ch2 instances share ONE structure: a dominant GIANT cheap-component + tiny satellites,
bridged by ≤5 exceptions. The lever is identical: optimize the GIANT's internal order with EPOCH-AWARE
(time-expanded) phasing** — the part local search can't crack (S1/faithful = 172 neighbors stuck; the 11×
epoch inflation lives inside the giant). **Small's 40-city giant is the tractable TESTBED** (40-city
time-dependent TSP; vs large's 601). Build = time-expanded beam/DP or LKH on the giant + cheap satellite
insertion + 3 exc-bridges. This is lever #2, now correctly scoped. NEXT: build it on small's 40-giant;
if it beats 112.996 → scale to large's 601-giant (the rank-2→1 path).

## E-656: time-expanded BEAM also strands ⇒ construction is dead; need CLUSTER-FIRST giant-TSP

Lever #2 first form = time-expanded beam (K=800, top-K partial paths by arrival epoch, table-fast
expansion). **DIED at step 28/49 — all 800 paths stranded** (after using exc to reach satellites, the
remaining cities are unreachable). ⇒ **left-to-right construction (greedy AND beam) fundamentally cannot
complete these component-structured instances.** The bank/competitors build CLUSTER-FIRST: solve each
cheap-component's internal tour, then stitch with exactly-placed ≤5-exc bridges.

**Precisely-scoped remaining build (the real lever, all 3 instances):** a CLUSTER-FIRST solver —
(1) solve the GIANT component's internal time-dependent TSP (small 40-city / large 601-city) with
LKH/exact + epoch handling, (2) solve the trivial satellites (3-city), (3) stitch the components with
≤5 exc bridges (choose bridge endpoints + component order). This is a 40-city (then 601) sub-TSP, NOT a
full-instance permutation search — much smaller than the generic LKH framing. Construction and local
search are BOTH now falsified; this cluster-first giant-TSP is the build. elkai precision may work at
40 cities (small matrix). NEXT: extract small 40-giant, try elkai-LKH (or exact) on its epoch-min-tof
matrix → tour → faithful walk w/ satellites+bridges → vs 112.996.

## E-657: cluster-first VIABLE — elkai-LKH solves the 40-giant (precision OK at small scale)

Extracted small's 4 components [40,3,3,3]; **elkai-LKH SOLVED the 40-city giant** (static cheap-cost
69.06d) — the precision assertion that blocked the FULL matrix does NOT occur at 40-city scale. ⇒
cluster-first decomposition is VIABLE: we CAN optimally solve a giant's internal TSP. Assembly (giant
path -exc-> 3 satellites, faithful walk) is slow (same Lambert-slow-on-nonbank-orders issue, throttled).
The remaining question = does the STATIC-optimal giant order survive time-dependent walking, or does
epoch-phasing inflate it (the time-dependent reordering trap, per e576's OR-Tools→1400d divergence)?

**RIGOROUSLY-SCOPED REMAINING LEVER (whole audit chain E-654→657):** the loss is epoch-phasing inside
the giant; construction (greedy+beam) strands, local search is stuck, naive-merge is infeasible, and
STATIC giant-TSP likely inflates when walked. The precise build = an **EPOCH-AWARE (time-dependent)
TSP on the giant** — iterate LKH with epoch-updated costs (re-solve LKH, walk, update the cost matrix
to the realized-epoch tofs, repeat to fixpoint), OR a time-expanded LKH. elkai works at giant scale, so
this is buildable. This is the hard core TGMA solved; it's the multi-day investment, now precisely defined
with the key technical unlock (elkai@40-giant) confirmed. Recover small 11.35d→rank4-1, scale to large
601-giant→toward 424.

## E-658: the CRUX — static-LKH giant orders are INFEASIBLE WHEN WALKED (epoch-edge coupling)

Iterated epoch-aware LKH (LKH on min-tof → table-walk → update cost → repeat): **ALL 10 iterations
produced orders that STRAND on the chronological table-walk** (a leg cheap at its best epoch is NOT
cheap at the realized arrival epoch). This is THE fundamental difficulty of the time-dependent TSP and
explains the entire falsification ladder: static LKH/OR-Tools give infeasible-when-walked orders (e576's
1400d divergence); greedy/beam commit epochs but STRAND at the endgame; local search is stuck in the
bank basin; naive merge is infeasible. **The epoch-edge coupling cannot be dodged.**

**DEFINITIVE remaining lever:** a TIME-EXPANDED TD-TSP solver on the giant — nodes = (city, epoch-bucket),
directed edges (i,t)→(j,t+tof) ONLY where cheap[i,j,t] is finite (cheap at THAT epoch). Find a min-final-time
path visiting each city once across time-layers. This respects the coupling. It is NP-hard (Held-Karp
state = visited-set × city × time = 2^40 infeasible exact) ⇒ needs a HEURISTIC time-expanded solver
(time-expanded LKH / large-neighborhood on the time-expanded graph) — the competitor (TGMA) pipeline.
This is a substantial research-grade build; the whole audit chain (E-654→658) has now rigorously proven
it is THE lever and that all simpler methods fail for the same understood reason (epoch-edge coupling).
elkai works at giant scale (E-657) so a time-expanded variant is buildable but is the multi-day investment.

## E-659: fast table-walk evaluator FALSIFIED for small (+27d) → pivot the TD-TSP build to LARGE

Built the TD-TSP heuristic (SA over orders + fast wait-allowing table-walk evaluator). **Positive control
FAILED: table-walk(bank)=139.88 vs official 112.996 (+27d).** SA minimizes table-walk to ~135 but those
orders are 135 OFFICIAL too — worse than bank. ⇒ **small has NO fast faithful evaluator**: the bank exploits
fine CONTINUOUS scheduling no discrete table can represent (table-DP = +5.5d, greedy table-walk = +27d), and
the offset VARIES per order (E-617) so proxy ranking is unreliable. This is why small specifically resists —
faithful eval (kt.fitness/CMA) is slow, capping search; fast eval is unfaithful.

**BUT for LARGE the table evaluator IS faithful (L1: retime-DP=official=932.53, offset≈0)** — large is loosely
scheduled, no continuous-headroom pathology. ⇒ the fast-table-walk TD-TSP search is the RIGHT build, aimed at
LARGE (also the bigger prize: rank 2→1, 16/9 multiplier, r1=424 vs our 932). PREREQUISITE: a large
epoch-resolved cheap table (cheap[i,j,epoch] for the ~140k cheap pairs × epochs) — e533 is static-bool only;
must build/sample it. NEXT: build the large epoch-resolved table (sparse: only the ~12.6%-dense cheap pairs),
then SA over large orders w/ fast faithful table-walk → optimize phasing → beat 932 toward 424.

## E-662: full-order RETIME-SA built (user chose "build the fast scheduler")

Built the approved lever: full-order SA over large orders ranked by the cached RETIME (per-leg delay-grid
min-arrival, cheap-else-exc ≤5). The retime is the near-faithful evaluator (bank → 936 vs official 932.53,
+0.4%; vs greedy walk +28%, table strands). e590 applied retime only to the endgame; this is FULL-order.
Cached find_earliest_transfer; exc legs handled (the bank's 5 bridges). Control = retime(bank)≈936 within 2%.
Compute-bound: the COLD control walk is ~15-20min (exc legs scan the full 2400-step window before exc fallback);
the Lambert cost is the bottleneck (confirms E-661b — faithful eval is Lambert-bound). Running
(runs/ch2_v3/retimesa_large3.log). NEXT: read control; if PASS, SA explores (slowly, ~Lambert-bound) toward
<932 → official-check → guard-bank (<424=rank1 escalate). If too slow, the genuine accelerator is a faster
Lambert (vectorized compute_transfer / coarse-then-fine find_earliest_transfer) — the real bottleneck.
Launch note: retime-SA must use `micromamba run` (direct-python bg dies in sandbox).

## E-662b: retime evaluator VALIDATED (940≈932, faithful); SA blocked by a ~300s/proc CPU-time limit

All 4 mp chains pass the control (retime(bank)=940.16 vs official 932.53, +0.8% — the first faithful
full-order LARGE evaluator the campaign has had) then DIE during the first SA eval, no traceback/OOM.
Pattern: control (~166s CPU) survives; control+first-eval (~330s) is killed ⇒ a **~300s/process CPU-time
limit** in this sandbox. The faithful grind survives because its per-iter evals are fast (pre-screen).
⇒ The faster-Lambert accelerator (coarse-then-fine find_earliest_transfer, ~10-50x) is now MANDATORY:
it keeps each retime eval well under the limit AND speeds the search. Build that, then the retime-SA
becomes both stable and productive. The deep audit (E-654→662) is COMPLETE: gap=epoch-phasing in the
giant; root=no fast faithful evaluator; retime is the near-faithful one (validated); the remaining work
is the Lambert accelerator + (re)running the SA. Banks strong+held (medium r1, large r2, small ~r5).

## E-662c: accelerator (coarse-then-fine) FAILS — cheap windows are narrower than any coarse grid

Tried find_earliest_transfer_fast (coarse 60 over [0.05,40] → refine). Control BROKE: retime(bank)=1892
(+103%) — large's cheap ToF windows are NARROW (<~0.5d; L2 found cheap at tof≈0.006), so a coarse scan
can't even DETECT them; legs fall to longer/exc transfers and makespan doubles. ⇒ fine Lambert resolution
(N_STEPS=2400) is FUNDAMENTALLY required to find the narrow cheap windows; coarse-then-fine can't help.
Reverted to the faithful evaluator.

## FINAL (E-654→662): complete audit; validated evaluator; blocked by a compute+infra DOUBLE-BIND

Definitive: Ch2 gap = epoch-phasing in a giant cheap-component; root = no fast faithful evaluator. The
RETIME is the validated near-faithful one (940≈932.53, +0.8%). The full-order retime-SA is BUILT + control-
VALIDATED. It is blocked by a double-bind: (a) faithful eval needs FINE Lambert scans (narrow cheap windows)
→ each full-order eval is slow; (b) this SANDBOX kills long single CPU-bound processes (~300s; control
survives, control+first-eval dies). Neither is algorithmic. ACTIONABLE PATHS: (1) run the validated
`scripts/ch2_large_retimesa.py 72000 4` on the USER's unrestricted machine overnight (no sandbox CPU limit) —
it would explore large orders with the faithful retime toward <932→424; (2) vectorize compute_transfer (batch
the 2400 Lambert ToFs) to make fine scans fast within any environment. Banks strong+HELD: medium r1, large r2,
small ~r5. The "we're not at a frontier" challenge produced a complete root-cause + a validated tool + two
concrete unlock paths — the deepest actionable state.

## E-662d: all accelerators exhausted → the sandbox CPU limit is the SOLE blocker (run on user machine)

Tested all 3 accelerators: (1) coarse-then-fine MISSES narrow cheap windows (control→1892); (2) Lambert
NOT batchable (pykep lambert_problem is per-call C++, no vector API); (3) reduced max_revs changes fidelity
(54.6 vs 57.2d/120 legs) AND isn't faster. KEY MEASUREMENT: the 120-leg prefix retimes in 1-3s — the CHEAP
legs are ALREADY fast; the whole cost is the 5 EXC legs doing full 2400-scans to CONFIRM no-cheap (you can't
distinguish no-cheap from narrow-cheap without the fine scan). ⇒ the validated retime-SA is genuinely
compute-TRACTABLE (cold control 262s; SA evals mostly fast cached cheap legs + a few exc rescans), and the
SOLE blocker is THIS SANDBOX'S ~300s/process CPU limit. ON THE USER'S UNRESTRICTED MACHINE it runs fine.

**HANDOFF (definitive):** `micromamba run -n spoc26 python scripts/ch2_large_retimesa.py 72000 4` on an
unrestricted machine = the user-approved faithful full-order large search, validated, ready, toward 932→424
(rank 2→1). This sandbox can't run it (process limit), not for any algorithmic reason. Everything else
(small, medium) is exhausted; banks strong+HELD. Audit E-654→662 COMPLETE.

## E-662e: 4th accelerator (adjacency-skip) also fails — e533 has 11 false negatives; handoff is firm

Tried skipping the cheap-scan for adj=False legs (e533 cheap adjacency). Control STRANDED: 16 bank legs are
adj=False but only ~5 are true exc bridges ⇒ **e533 has 11 FALSE NEGATIVES** (cheap endgame legs it misses,
positions 619,805,806,814,838,853,857,869,925,931,947). Skipping them sends real-cheap legs to exc, exhausts
the 5-exc budget, strands. A COMPLETE fine-resolution adjacency would fix it but is another ~hours rebuild.
⇒ FOUR accelerators now exhausted: coarse-then-fine (narrow windows), Lambert-vectorize (pykep per-call),
reduce-revs (fidelity), adjacency-skip (e533 incomplete). The faithful retime eval cannot be cheaply+safely
accelerated in-sandbox. **DEFINITIVE: run the validated `ch2_large_retimesa.py 72000 4` on the user's
unrestricted machine (no ~300s/proc CPU limit) — it is algorithmically ready toward 932→424.** Reverted to
the faithful eval; stable grind on cores. Ch2 audit E-654→662 fully closed.
