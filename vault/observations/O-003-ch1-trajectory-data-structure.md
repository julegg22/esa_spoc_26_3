---
id: O-003
type: observation
status: confirmed
tags: [ch1, astrodynamics, bcp]
source: "reference/SpOC4/Challenge 1 Luna Tomato Logistics/{Earth_orbits,Moon_orbits,LTL}.txt + README.md (shallow clone)"
created: 2026-05-18
referenced_by: ["[[H-002-ch1-trajectory-greedy]]"]
supersedes:
superseded_by:
---

# O-003 — Ch1 trajectory-matching data structure

## Observation

- **Earth_orbits.txt**: 400 orbits (header + 400). `id SMA(m) Ecc
  Incl(rad)` — Earth-centred, xy = Earth-Moon plane, x along
  Earth-Moon at t0 (unusual frame, README).
- **Moon_orbits.txt**: 400 orbits, same format, Moon-centred.
- **LTL.txt**: header + 160000 = **400×400** rows `l_id d_id c_ld`
  — full Moon-orbit→destination capacity matrix (kg/day).
- Decision vector 8400 = up to 400 transfers × 21:
  `[e,l,d, t0, r0(3), v0(3), DV0(3), DV1(3), DV2(3), T1, T2]`;
  unused → `e=-1`. Each e/l/d used ≤1 (3-D matching, as in beginner).
- Mass: `m_l = 5000·exp(-ΔV_tot/(311·9.80665)) − 500`; delivered
  `m_d = min(m_l, (200−ΔT)·c_ld)`, ΔT = transfer days; horizon 200 d.
- Dynamics: BCP (Simó 1995, Earth+Moon+Sun); non-dim μ=0.01215058…,
  μ_s=3.32946e5, ρ_s=388.811143, ω_s=−0.925195985; L=3.84405e8 m,
  T=3.7567696752e5 s. Validation tol 1e-6 on (a,e,i), SMA non-dim.
- **No provided UDP/validator for Ch1** (unlike Ch2/Ch3) — BCP
  propagation must be implemented (heyoka).

## Why it matters

Confirms the decomposition for [[H-002-ch1-trajectory-greedy]]:
a per-(e,l) Earth→Moon transfer-cost model (ΔV → m_l, ΔT) feeding
the **same 3-D assignment** we solved for beginner (reuse
`ch1_matching` MIP-LNS on the discounted-mass weight matrix). Hard
part = the transfer model; Team HRI reached rank-3 with a "Greedy
solution" (O-002), so a cheap ΔV model + strong assignment is a
viable rank-3 route. Cutoff: mass ≥ 452819.87 (O-002).
