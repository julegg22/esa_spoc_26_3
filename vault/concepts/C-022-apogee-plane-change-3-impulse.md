---
id: C-022
type: concept
status: partial
tags: [ch1, trajectory, 3-impulse, plane-change, classical-mission-design]
parent: "[[observations/O-013-plane-change-at-earth-bug]]"
created: 2026-05-26
---

# C-022 — Plane-change-at-apogee 3-impulse architecture

## Classical mission design (Wiesel §6.5, Vallado §11.4)

For LEO+inclined-Moon transfers, the cheapest place to plane-change
is at APOGEE (= Moon distance), where velocity is ~188 m/s. Compare:
- Plane change at LEO velocity (7.8 km/s): dv = 2*v*sin(Δi/2) = HUGE
- Plane change at apogee (~188 m/s): dv = ~50-200 m/s for Δi=30-60°
- Plane change at LLO circular (1.6 km/s): dv = 700-1500 m/s

## Architecture (3-impulse)

```
1. pv0 in Earth orbit (tilted plane)
2. dv0 = pure prograde burn in Earth orbit's plane → Hohmann transfer ellipse
3. Coast to apogee (~Hohmann half-period, 5d for LEO)
4. dv1 = plane-change burn at apogee (LOW velocity = cheap)
5. Coast briefly to Moon SOI
6. dv2 = capture into target Moon orbit
```

Crucial: dv0 must NOT include any z-velocity-killing component. It
purely accelerates in the Earth orbit's tangent direction.

## Test results (5 pairs)

| Pair | iE | iL | 2-impulse | apogee 3-imp | dv1 | Note |
|---|---|---|---|---|---|---|
| (0,0) | 0 | 0 | 819 kg | 534 kg | 515 | Worse — dv1 unnecessary |
| (213,19) | 0.20 | 1.07 | 5 | 1 | 1660 | Worse — bad phasing |
| (303,109) | 0.19 | 1.08 | 24 | 507 | 525 | **21× better!** |
| (244,105) | 0.34 | 0.50 | 49 | 475 | 568 | **10× better!** |
| (227,315) | 0.41 | 0.47 | 27 | 9 | 1080 | Worse — bad phasing |

## When it works vs when it doesn't

**Works when:** the Hohmann transfer geometry naturally aligns apogee
position with Moon's position at TOF, AND the relative orbit-plane
angle is in a "favorable" basin for low-cost rotation.

**Fails when:**
- Phasing mismatch (apogee at wrong time/place vs Moon)
- DC can't converge from default seed for high-Δi pairs

## Improvement path

Multi-start with proper PHASING — pick (raan_e, argp_e, ea_dep, TOF)
such that apogee position == Moon position at TOF arrival. This
requires solving the phasing equations explicitly, not just sweeping.

Alternative: hybrid approach — try both 2-impulse and 3-impulse-at-
apogee per pair, keep best of both. Marginal gains (~5%) but safe.

## Implementation reference

- `src/esa_spoc_26/ch1_apogee_plane_change.py` — core 3-impulse builder
- `scripts/ch1_apogee_polish.py` — applies to all banked transfers
