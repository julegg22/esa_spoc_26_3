---
id: O-004
type: observation
status: confirmed
tags: [ch1, astrodynamics, bcp]
source: "GraphQL ProblemType.udpFile (spoc-4-luna-tomato-logistics) + reference/spoc4_udp/{matching-i,matching-ii,trajectory-matching}.py, fetched 2026-05-19"
created: 2026-05-19
referenced_by: ["[[H-002-ch1-trajectory-greedy]]", "[[L-002-udp-served-via-graphql-not-git]]"]
supersedes: "[[O-003-ch1-trajectory-data-structure]] (the 'no provided UDP/validator for Ch1' line only)"
superseded_by:
---

# O-004 — Ch1 UDPs exist (via API); BCP constants correction

Append-only correction to [[observations/O-003-ch1-trajectory-data-structure|O-003]]
(user-prompted, 2026-05-19). O-003's geometry/mass facts stand; its
"no provided UDP/validator for Ch1" statement is **wrong**.

## Observation

Official Ch1 UDPs are served at `ProblemType.udpFile`:
- `matching-i` / `matching-ii`: 46-line binary 3-D-matching UDP —
  fitness = `[-Σw]` over selected edges, `[0]` if any a/b/c reused.
  **Identical to our ILP** → banked results valid (no cascade).
- `trajectory-matching`: 264-line UDP — the authoritative oracle:
  - `μ = MU_MOON/(MU_MOON+MU_EARTH)`,
    `μ_s = MU_SUN/(MU_MOON+MU_EARTH) ≈ 3.289e5` (**README's
    3.3294e5 is wrong**), `ρ_s=388.811143`, `ω_s=-0.925195985`,
    `MU_SUN=1.32712440041279419e20`, `MU_EARTH=398600435507000`,
    `MU_MOON=4902800118000`, `L=3.84405e8`, `T=3.7567696752e5`.
  - `bcp_dyn()`: synodic BCP EOM (form matches our derivation).
  - `propagate(posvel,t0,DVs,Ts)`: heyoka `taylor_adaptive`
    tol 1e-16, **non-terminal Earth/Moon impact events**
    (Earth R+99 km, Moon 1737.4+30 km) → returns `[]` on impact.
    Applies DV0 to v, integrates T1, +DV1, integrates T2, +DV2.
  - `state2earth/2moon`: derotate `v±=(vx∓y,vy±x,vz)·V`, subtract
    primary velocity, translate, then `pk.ic2par(r,v,MU_*)[:3]`.
  - `_match_orbit`: `|a_el−a|/L<1e-6 ∧ |e−e|<1e-6 ∧ |i−i|<1e-6`.
  - `fitness`: 21-wide rows `[e,l,d,t0,r0,v0,DV0,DV1,DV2,T1,T2]`,
    `e<0` skips; initial state must already match Earth orbit;
    final must match Moon orbit; `mass=exp(-Σ|DV|·V/311/G0)·5000−500`;
    `m_d=min(mass,(200−ΣTs·T·SEC2DAY)·c_ld)`; each (e,l,d) once.

## Why it matters

H-002 must optimise against the **official** `propagate`/`fitness`
(in `reference/spoc4_udp/trajectory-matching.py`) as the truth
oracle — not README constants. See
[[lessons/L-002-udp-served-via-graphql-not-git|L-002]].
