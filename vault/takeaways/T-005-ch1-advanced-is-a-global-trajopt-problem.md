---
id: T-005
type: takeaway
status: final
tags: [ch1, astrodynamics, bcp, framing, decision-rationale]
hypothesis: "[[H-002-ch1-trajectory-greedy]]"
created: 2026-05-19
supports_verdict: inconclusive
confidence: high
generalizability: subgoal-wide
goal_contribution: "Ch1-advanced: pipeline+geometry solved; the real hurdle is global low-ΔV (Sun-assisted, long-TOF) transfer optimisation — shooting is the wrong tool. Frame/Moon-motion is verified bit-exact, not the bug."
effort_person_hours: 0.5
superseded_by:
invalidated_by:
invalidated_at:
---

# T-005 — Ch1-advanced is a global trajectory-optimisation problem

## Summary

Across E-006…E-011 (forward & backward shooting, patched-conic &
Lambert seeds, radius- and ΔV-objectives): the **validation pipeline
and geometric targeting are fully solved** (LLO hit to 2 m forward,
Earth hit to 0.12 m backward), but **no positive-mass transfer** —
every geometry-valid solution has pathological ΔV. The binding
difficulty is *finding a low-ΔV transfer*, which stiff single-
shooting cannot do (ΔV-objective diverges, E-009).

## Answer to "is a fundamental assumption wrong? (Moon motion?)"

- **Frame / Moon-motion: verified, not the bug.** Our
  `state2earth/2moon` inverses round-trip the *official UDP*
  bit-exactly (Earth & Moon round-trips pass the 1e-6 scorer
  tolerance). In the synodic BCP the Moon is fixed at (1−μ,0,0); its
  inertial motion is correctly carried by the official velocity
  de-rotation `(vx−y, vy+x, vz)·V` minus the body velocity — which
  we mirror exactly. Whatever the README prose, the UDP **is** the
  scorer and we are faithful to it, so a synodic-vs-inertial misread
  cannot be the failure.
- **The genuinely wrong assumption is the transfer *family* and the
  *method*.** We searched short Hohmann-like TOF (3–8 d) via local
  shooting. The challenge ships the **Sun** (bicircular, not CR3BP),
  a **200-day** horizon, and tight tolerances — these deliberately
  reward **long, Sun-perturbed low-energy / ballistic-capture**
  transfers (near-zero LOI), and make naive direct shooting
  pathological. *This is the designers' "analytical-capacity
  hurdle".*
- Direct transfers are **not** impossible: a well-designed direct
  Earth→LLO is ≈ 3.9 km/s ⇒ m_l ≈ +892 kg (positive). Our solver
  just finds 20+ km/s monsters — an *optimisation* failure, not an
  infeasibility.

## Implications

1. Abandon stiff geometric shooting for the transfer. Use **global
   trajectory optimisation** (pygmo / pagmo) with the **official
   `fitness` as the objective** (it already encodes ΔV→mass and the
   time discount correctly), over a **wide TOF range incl. long
   Sun-assisted arcs**, decision vars = the 21-tuple (or a reduced
   parametrisation). The validated pipeline is exactly the objective
   function such an optimiser needs — a durable asset.
2. Expect low-energy (long-TOF, Sun-phased) transfers to dominate
   rank-competitive mass; direct is at best a weak baseline.

## Position vs goal

- **Contribution:** H-002 effort now ≫ its 12 h estimate with 0
  points; pipeline validated (asset) but no artifact. Ch1 matching
  (~11 pts) remains the only banked Ch1 score.
- **Where we stand:** Ch2 (3 instances) entirely untouched; the
  rank-3-each-instance goal is broad. H-002 ROI is now uncertain
  and high-cost.
- **Next move:** strategic re-prioritisation with the user — global
  optimiser for H-002 vs timebox-and-pivot to Ch2 breadth (M-018 /
  effort-escalation escalation).

## Caveats

A global optimiser over the BCP is itself substantial; success not
guaranteed. The pivot decision is ROI under finite campaign time.
