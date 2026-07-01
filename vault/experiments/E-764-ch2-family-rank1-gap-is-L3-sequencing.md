---
id: E-764
type: experiment
status: analyzed — Ch2 rank-1 gap is L3 (sequencing), NOT L4; corrects the E-760/E-761 L4 labels
date: 2026-07-02
level: L3
wall_level: L3
assumes: [EVAL-lambert, MODEL-official-feas]
code: (inline tof-inflation probe)
commit: 522e705
related: ["[[E-760-ch2-small-exact-dp-lns-validated]]", "[[E-761-ch2-medium-exact-dp-lns-L4-wall]]", "[[E-763-ch2-large-decompose-refuted-reframe]]", "[[assumptions]]"]
corrects: ["[[E-760-ch2-small-exact-dp-lns-validated]]", "[[E-761-ch2-medium-exact-dp-lns-L4-wall]]"]
---
# E-764 — Ch2 rank-1 gap is L3 sequencing (not L4 encoding); L7-ruleout was over-claimed

**Measurement.** small bank (111.96): per-leg tof median 2.03 d, and **0/43 legs
have a shorter cheap tof available at the banked epoch** — the tofs are already
minimal. So small is **NOT** L4 (tof/encoding) inflatable. Same as large (E-763:
33/588). Medium's idle was already shown *order-forced* (E-759).

**Correction.** The whole Ch2 family's rank-1 gap is **L3 (sequencing)** — a
different *order* whose legs are intrinsically shorter — not L4 encoding. The
windows/tofs are fine; the ORDER is the lever. The E-760/E-761 `wall_level: L4`
labels are corrected to **L3** here.

**And L7 was over-claimed.** E-760/E-761 "ruled out L7" via 3 converging configs —
but all three used the **same** cheap-restricted or-opt/2-opt neighborhood. That
rules out L7 only *within that neighborhood family*, not L7 broadly. A
fundamentally different sequencer (unrestricted / larger-neighborhood moves,
ruin-recreate, GRASP, a time-aware beam, or relaxing the cheap-edge move
restriction) has NOT been tried on small/medium and could reach lower. (Classic
"exhausted-within-a-basin ≠ exhausted" — the methodology's own warning applied to
ourselves.)

**Consequence.** The Ch2 rank-1 lever is a **stronger global sequencer** (or a
less-restricted move set / a directed-time-aware decomposition for large), on the
*existing* window representation. This is one shared L3 problem across small
(tractable proving ground), medium, and large (hardest). It is genuine research —
the same reason large walled 7+ methods — but the cheapest next test is on small:
does relaxing the cheap-edge move restriction / a larger neighborhood beat 111.96?

**Bank impact.** None. This is a diagnostic re-labeling (L4→L3) + an honest
retraction of the over-broad L7 ruleout.
