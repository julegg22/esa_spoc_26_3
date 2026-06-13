---
id: S-2026-06-13
type: session
tags: [session, audit, assumption-audit, methodology, ch1-trajectory, ch2-small, ch2-large, wsb, anti-oscillation]
date: 2026-06-13
participants: [JJ, Claude Code]
claude_model: claude-opus-4-8
commits: [e49945c, 0b80ae7, 4f9ecc8, f86a46c, 713da82, 6bc584d, 52da7b0, 8199843, ca2ebc4, a7c2702, a842dbe, 6e77cbd, 7db5639, 2ad643d, 19b0d6a, 987ac81, 22f7737, 63c79a8]
created_nodes: [[[E-602-ch1-trajectory-gap-anatomy]], [[E-603-ch2-small-gap-anatomy]], [[E-591-ch2-large-epoch-connectivity]], [[M-general-deep-single-prompt-audit]]]
---

# S-2026-06-13 — Deep single-prompt audits (Ch2-large, Ch1-trajectory, Ch2-small) + methodology capture

## Scope

A day of the autonomous campaign loop punctuated by **three user-requested
"deep single-prompt audits"** — structured one-shot prompts that treat a
leaderboard-better solution as ground truth and hunt for the *flaw* in our
"exhausted" verdict rather than optimizing further. The three targets were Ch2
large, Ch1 trajectory, and Ch2 small. The day ended by **generalizing the
technique into a methodology note** so future audits are repeatable and so this
is reportable chronologically.

Background grind continued throughout (Ch1 matching closure, Ch2-large bank
descent); this journal foregrounds the audits.

## Chronological narrative

### 00:00–05:00 — Ch1 matching/trajectory closure + Ch2-large bank descent (background loop)
- Ch1 free-RAAN/argp feasibility lead **refuted** (E-047, `0b80ae7`); the probe
  was confounded — solver failed its own positive control (E-572, `e49945c`).
- Both Ch1 **matching** instances exhausted under connected-region exact LNS
  (E-048, `f86a46c`); pivot to trajectory per-pair DoF (`713da82`), which also
  came back **exhausted** (E-049, `6bc584d`).
- Ch2 **large** bank ground down across the night via recovered windowed-LNS +
  guard-banking: 1013.29 → 970.07 (`52da7b0`) → 947.80 → 942.07 (`ca2ebc4`).
- Ch2 **medium** 192.90 → **189.10 d** via ultrafine retime-DP (E-568,
  `8199843`) — extends RANK 1.

### 05:53–08:18 — Ch2-large: timing axis floored, then "connectivity wall"
- Departure-time waiting lever banked −7.63 (E-588, `a7c2702`); per-component
  LKH closed as an epoch-shift dead-end (E-587). Global retime-DP banked −1.91
  to **932.53 d** (E-589, `a842dbe`) — the timing axis is floored for the fixed
  tour. Endgame reorder NULL (E-590, `6e77cbd`).
- The epoch-connectivity diagnostic (E-591, `7db5639`) initially concluded 22
  nodes are "intrinsically" cheap-edge-starved ⇒ rebuild hopeless.

### 09:20 — AUDIT #1 (Ch2 large): "connectivity wall" was a probe-resolution artifact
- **User:** deeply explore the connectivity direction.
- Auditing E-591's own diagnostic (hostile-default discipline) found its
  "intrinsic" verdict rested on a **25-random-target sample (2.4 %) + 0.5 d tof
  grid + 30 d window — all three biased toward false-intrinsic.** The
  all-1050-target fine-grid re-scan **overturned** it (flagged nodes have 10–30
  cheap neighbors at every epoch).
- **Decisive measurement:** 932.53 d = 0.86 d/leg vs r1's 0.40 ⇒ the gap is
  *global routing/partition* (whole tour ~2× too long per leg) with rich
  cheap-edge supply — reachable only by a from-scratch global time-dependent
  constructor, not within-topology polish. Re-opened the multi-day rebuild as a
  justified (point-EV-0-until-sub-r1) lever. Correction committed `2ad643d`.

### 09:54 — AUDIT #2 (Ch1 trajectory): "exhausted" was architecture-conditional
- **User:** 4-phase assumption audit; treat leaderboard-better as ground truth;
  find the flaw, don't optimize.
- Re-read the official BCP (Sun-perturbed) validator. Three cheap arithmetic
  probes (ch1_e600/601/602; bank reconstructs to 236,420.5 kg exactly):
  idD layer **closed** (+0.13 %); matching **closed** (1.6° headroom; 65/65
  stranded high-incl Earth orbits have a Moon orbit within 0.2°); residual cost
  is **lunar capture, not plane change** — corr(dv, eL) = −0.71, and 131
  near-coplanar pairs still average 4927 m/s.
- **Self-correction:** the audit first blamed plane-change-via-Sun; the
  arithmetic showed plane change is cheap (272 m/s) and re-pointed the lever to
  **eL-stratified WSB ballistic capture.** Writeup E-602 (`19b0d6a`).
- **Flaw:** every saturation verdict was conditional on **A1 = impulsive
  patched-conic**, which the BCP validator never imposes. WSB fleet-scale lever
  (proven +17 % on n=1, mis-deprioritized as "multi-week") is **open**.

### 10:10 — Ch2-large exploration concluded; Ch1 WSB probe launched
- Ch2-large rebuild agent finished (no bank delta): cheap escapes ≤0.5 d
  everywhere (no speed limit), star topology real (5 bridges required),
  reconstructor didn't beat 932.53. Bank holds at 932.53 (R2). Tick `987ac81`.
- On freed cores, launched the **queued Ch1 WSB eL-stratified probe** (agent
  a86302d, bg) — control pair (118,171) validated **bit-for-bit** against the
  bank's WSB solution; full 25-pair run mid-flight (~29 min, /tmp only, no
  bank/submit).

### 10:42 — AUDIT #3 (Ch2 small): "DP-optimal" was basin-conditional
- **User:** same 4-phase audit on Ch2 small.
- Re-read the official KTTSP fitness (max_revs=20 **fixed** ⇒ leaders use
  identical physics ⇒ 101.65 is pure routing/timing). Decomposed the bank
  (116.3738 d): **makespan = flight 109.99 + idle 6.38.**
- **Decisive measurement:** **flight-only (zero idle) = 109.99 d is already
  below R3 = 110.88 d** ⇒ the entire R3 gap is phasing idle the DP cannot remove
  *for this perm*. 5 exceptions = 4 required connectivity bridges + 1 *chosen*
  intra-comp0 shortcut; comp0 has no degree-1 nodes ⇒ not forced to split.
- **Flaw:** "116.38 = DP-optimal / exhausted" holds only **within one topology
  basin.** Smoking gun (E-032): topology-changing ALNS operators produced
  **0/10 bankings** (all DP-infeasible) ⇒ the search was structurally confined;
  every path to a different exception-allocation passes through infeasible
  intermediates. Writeup E-603 (`22f7737`).

### ~10:26 — Methodology capture
- Generalized the three audits into [[M-general-deep-single-prompt-audit]]
  (`63c79a8`): the reusable verbatim 4-phase prompt, the operating rules
  (measure-don't-assert, self-correct mid-audit, diagnostic-not-productive), and
  the three case studies. Registered in `index.md`; memory pointer added.

## Key decisions

1. **The "deep single-prompt audit" is now a named, reusable technique** (user,
   2026-06-13). Fire it whenever a sub-problem is declared exhausted but an
   external oracle proves better exists. *Why:* it broke three standing verdicts
   in one day; the flaw was never raw search effort.
2. **Each audit is diagnostic, not productive** — no bank change is the expected
   outcome; the deliverable is a verdict + 3 information-ranked experiments.
3. **Ch1 trajectory and Ch2 small are RE-OPENED as questions** (not closed): Ch1
   via WSB fleet-scale, Ch2-small via exception-allocation basin search. Both
   queued, both point-positive in principle.

## Soft knowledge

- **The recurring flaw shape across all three:** *"exhausted within
  (architecture | search basin | probe resolution)" masquerading as "exhausted
  of the problem."* The decisive evidence in every case was a **cheap arithmetic
  measurement on the banked artifact** that the prior ceiling verdict had never
  taken.
- **Always reconstruct the banked objective exactly first** — it is the
  correctness gate that lets you trust every subsequent delta (236,420.5 kg for
  Ch1; 116.3738 d for Ch2-small).
- **Let the number overrule the story.** Both the Ch1 (plane-change → capture)
  and Ch2-large (intrinsic → routing) audits self-corrected an initial wrong
  mechanism via the arithmetic.

## Artefacts touched

- New experiments: [[E-602-ch1-trajectory-gap-anatomy]] (`19b0d6a`),
  [[E-603-ch2-small-gap-anatomy]] (`22f7737`),
  [[E-591-ch2-large-epoch-connectivity]] (`7db5639`, corrected `2ad643d`).
- New methodology: [[M-general-deep-single-prompt-audit]] (`63c79a8`) +
  `index.md` registration.
- Probe scripts: scripts/ch1_e600/601/602 (Ch1); /tmp/ch2s_decomp.py,
  /tmp/ch2s_topo.py (Ch2-small, diagnostic, not committed).
- Memory: corrected `ch1-trajectory-mass-lever-exhausted`; added
  `deep-single-prompt-audit`.
- Loop ticks through the day in `loop-state.md`.

## Open threads

- **Ch1 WSB eL-stratified probe** (agent a86302d) — decisive low-eL test in
  flight; on completion, if WSB wins on low-eL, scope the multi-day Ch1 R3 fleet
  build; if only high-eL, downgrade the fleet estimate.
- **Ch2-small experiment #1** — exception-allocation DP basin sweep (cheapest,
  most decisive); queued behind the WSB probe (no core competition).
- **Ch2-large** — from-scratch global TD constructor remains the only sub-r1
  lever (point-EV 0 until <424.62; rank-2 secure).
- Banks unchanged today on the audited instances; medium 189.10 (R1) + large
  932.53 (R2) UNSUBMITTED by the overall-rank-3 gate.
