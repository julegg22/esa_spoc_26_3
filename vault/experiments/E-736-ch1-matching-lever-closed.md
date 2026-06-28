---
id: E-736
type: experiment
tags: [ch1, trajectory, matching, closed, deep-audit-followup]
date: 2026-06-28
status: DONE — cheap diagnostic CLOSES the E-733 surviving matching lever; Ch1 at tooling floor
closes: [E-733]
related: ["[[E-733-ch1-trajectory-deepaudit-capture-floor]]", "[[ch1-matching-solver-bound-refuted]]", "[[ch1-trajectory-udp-floor-confirmed]]"]
---
# E-736 — Ch1 matching lever CLOSED (cheap diagnostic, no solver sweep needed)

E-733's deep audit named one surviving Ch1 lever: a **restricted joint realized-cost (idl) matching re-opt** on
the ~140 worst transfers, on the premise that the cld-cap loss (~20,507 kg, stale figure) was matching-recoverable
toward rank-5 (+16,179). A cheap diagnostic on the **current bank** (no trajectory solves) closes it:

## Measured (pos-control + bank arithmetic)
- **Current Ch1 bank = 361,014 kg** (not 356,550 — improved since, likely E-706 idd banking). +11,715 to rank-5
  (372,729). feasible (udp.fitness<0).
- **cld-cap loss = 19 kg over just 8 capped transfers.** The "20,507 kg cld cap" premise (E-733/older) is STALE —
  E-706's idd Hungarian already recovered the cld side **fully**. No matching headroom on the cld axis.
- **392/400 transfers are MASS-BOUND** (cap ≥ mass; the binding term is trajectory ΔV, not the cld cap). The
  fleet loss is on the **mass/ΔV side**, which needs *cheaper trajectories*, not re-matching.
- The 10 worst-realized transfers are all **circular Moon orbits (eL≈0.00-0.02) with high capture DV2** (546-1702
  m/s) — exactly E-733's **physics-floored** circular-capture case. 250/400 transfers are circular (eL<0.1),
  realized mean 763 kg vs eccentric (eL>0.4) 1135 kg.

## Verdict — matching is at its joint optimum; Ch1 is at our tooling floor
Re-matching `idl` cannot help: (a) the **cld side is already recovered** (19 kg residual, idd Hungarian-optimal
E-706); (b) the **mass side is irreducible capture physics** — the 250 circular Moon orbits must each be captured
expensively *regardless of which Earth orbit pairs with them* (capture ΔV is Moon-orbit-side geometry, E-733
corr(DV2,eL)=−0.71). So the realized-ΔV matching matrix re-opt that E-704 deemed "280 CPU-h" was not worth
building — the cheap arithmetic shows its ceiling is ~0. **E-733's surviving lever is CLOSED.**

Ch1 is now at our tooling's floor on all axes: departure floored (E-701 eccentric fix), capture physics-floored
(circular orbits, E-733), idd Hungarian-optimal (E-706), idl matching at joint optimum (this node). The +11,715
to rank-5 would require **cheaper capture/departure trajectories** (physics-floored) — no admissible lever remains
without a fundamentally better low-energy capture for circular LLOs (E-604 WSB refuted; the one unrefuted
long-shot is re-verifying the WSB window for circular targets isn't a scan-resolution artifact, E-733 path #3 —
low prior). Diagnostic only; bank unchanged, nothing submitted.
