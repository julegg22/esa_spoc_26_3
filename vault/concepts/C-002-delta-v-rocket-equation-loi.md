---
id: C-002
type: concept
status: confirmed
tags: [astrodynamics, propulsion, ch1]
scope: astrodynamics/propulsion-and-transfers
confidence: high
created: 2026-05-19
sources:
  - "Tsiolkovsky rocket equation (classical)"
  - "Curtis, Orbital Mechanics for Engineering Students — Hohmann transfers, patched conics"
  - "reference/spoc4_udp/trajectory-matching.py (mass model + LOI validation)"
related: ["[[C-001-cr3bp-and-bicircular-problem]]", "[[H-002-ch1-trajectory-greedy]]"]
---

# C-002 — Δv, the rocket equation, transfers, and LOI

*Primer for non-experts: the "currency" of spaceflight and why
delivering tomatoes is a fuel-budget problem.*

## Definition

- **Δv ("delta-vee")**: the total change in velocity a spacecraft
  must produce with its engine to do a manoeuvre, in m/s. It is the
  universal *price tag* of any orbital change.
- **Impulsive manoeuvre**: an idealised instantaneous engine burn —
  velocity jumps, position doesn't. Real burns are short enough that
  this is a good model. Ch1 allows up to **3 impulses** per transfer.
- **LOI — Lunar Orbit Insertion**: the braking burn that converts a
  fast arrival trajectory into a bound orbit *around the Moon*.
  Without it the craft just flies past.

## Why it matters here

Ch1 converts Δv directly into delivered tomatoes via the
**Tsiolkovsky rocket equation**:

> `delivered_mass = 5000 · e^(−Δv / (Isp·g₀)) − 500`,
> with Isp = 311 s, g₀ = 9.80665 m/s².

The cost is **exponential**: every extra 100 m/s of Δv multiplies the
remaining payload by ~0.97. So *minimising Δv ≡ maximising tomatoes*.
A 4000 m/s transfer delivers ~850 kg; a 3000 m/s one ~1350 kg. This
is why "low-energy" transfers (`[[C-001-cr3bp-and-bicircular-problem]]`)
are tempting despite taking longer. In our solver, the arrival burn
(**LOI**) is exactly the `DV2` produced by `solve_arrival_dv`
(`[[H-002-ch1-trajectory-greedy]]` Step 2).

## Mechanics

A classic Earth→Moon transfer has three pieces:

1. **Departure burn (DV0 / TLI)** — speed up in the parking orbit to
   stretch it out toward the Moon ("trans-lunar injection").
2. **Coast** — engine off, gravity does the work for several days.
3. **Arrival burn (DV2 / LOI)** — slow down at the Moon so lunar
   gravity captures you onto the target orbit.

**Patched conics** is the cheap approximation: pretend only one body
pulls at a time (Earth, then Moon), glue two Kepler arcs together.
It gives a good *initial guess* but is wrong in detail — in the real
BCP the trajectory won't arrive exactly where patched conics
predicts, which is precisely the targeting difficulty in H-002
(our first direct attempt missed the lunar-orbit radius by
~11 000 km — a real cislunar *differential correction* is needed,
not just a coast-time scan).

## In practice

The Moon orbits in this problem are nearly **circular** (e ≈ 1e-7)
at ~1.8e6 m radius, validated to 1e-6. That makes LOI a *tight*
target: the coast must deliver the craft to almost exactly the
right lunar radius before DV2 can circularise it. Trade-off baked
into Ch1: a longer coast can lower Δv (more tomatoes) but eats into
the 200-day mission horizon and the per-day delivery capacity.

## References

Tsiolkovsky; Curtis (Hohmann/patched conics); the UDP mass model.
