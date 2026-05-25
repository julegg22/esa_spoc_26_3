---
id: O-013
type: observation
status: confirmed
tags: [ch1, trajectory, bug-diagnosis, plane-change, soi, ultrathink, critical]
source: "Bank analysis 2026-05-25: LEO+inclined-Moon transfers consistently 1500+ m/s above Hohmann"
created: 2026-05-25
referenced_by: []
---

# O-013 — Solver does plane change at Earth, not at lunar SOI

## The pattern

Analysis of 156-transfer bank (108,825 kg):

**LOW-MASS transfers (LEO + inclined Moon orbit):**
| mass | dv0 | dv2 | aE | iL |
|---|---|---|---|---|
| 5 kg | 4792 | 2199 | LEO | 1.07 rad |
| 23 kg | 4156 | 2732 | LEO | 0.72 rad |
| 27 kg | 5661 | 1204 | LEO | 0.47 rad |

dv0 is 1500-2400 m/s ABOVE Hohmann theoretical (3242 m/s for LEO).

**HIGH-MASS transfers (GEO + eccentric Moon):**
| mass | dv0 | dv2 | aE | iL |
|---|---|---|---|---|
| 2628 kg | 1116 | 314 | GEO | 0.55 rad |
| 2599 kg | 1128 | 332 | GEO | 0.55 rad |

These are near-Hohmann optimal (dv0 ≈ 1100 m/s for GEO).

## Diagnosis

For inclined Moon orbits (iL > 0), our solver targets an out-of-plane
arrival point via 2-body Lambert. Lambert provides a trajectory that
tilts the orbital plane FROM EARTH, requiring plane-change at Earth
velocities (~7.8 km/s for LEO). Cost: 2*v_circ*sin(iL/2) = 4000-10000 m/s.

The correct architecture: coplanar Lambert to lunar SOI, plane-change
at SOI (v_inf ~ 800 m/s), arrive at Moon orbit. Cost: 2*v_inf*sin(iL/2)
= 400-800 m/s.

**The leaders avoid this 1500+ m/s "tax" on every LEO+inclined-Moon
transfer.** Standard mission design wisdom (Wiesel §6.5, Vallado §11.4).

## Why 3-impulse polish (Tier 1B) didn't find this

Tier 1B starts from 2-impulse trajectory and adds dv1. The polish is a
LOCAL search. To put plane change at SOI requires moving dv1 from "0
near departure" to "non-zero magnitude at mid-trajectory." This is a
discrete topology change — Nelder-Mead can't traverse.

## Required fix: explicit SOI plane-change solver

3-impulse architecture by construction:
1. Lambert in SYNODIC XY plane (Earth to SOI), giving dv0
2. dv1 at SOI = plane-change burn (rotate velocity into Moon orbit plane)
3. dv2 at Moon orbit = small circularization

Per-pair compute similar to 2-impulse (~30s). Implementation effort:
~4-8h.

## Expected impact

- LEO + iL>0.3 pairs: 50-100% mass increase (300 → 500-600 kg)
- These represent ~60% of our 156 banked transfers
- Bank could grow from 109k → 160-200k kg from this fix alone

Combined with idE-expansion (more transfers) and t0/argp sweeps:
realistic path to 250-350k kg (rank 3-4 territory). Beyond that needs
either WSB (H-009) or another insight.
