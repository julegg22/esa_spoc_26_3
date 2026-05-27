---
date: 2026-05-27
tags: [audit, ch1, trajectory, bcp-apogee, bugs, structural]
status: COMPLETE — multiple bugs found, top hypothesis identified
bank_at_audit: 186,636 kg / 294 transfers
target: 453,000 (R3) / 473,332 (R1)
---
# A-2026-05-27 — Ch1 trajectory pipeline audit (ultrathink)

Drives at the question: why are we at 186,636 kg when R1=473k? The hypothesis going in was that we have a structural bug we keep building around. **Outcome: yes — multiple bugs found, one of which is structurally large.**

## TL;DR — Findings ranked by estimated kg impact

| # | Severity | Item | Est. kg impact |
|---|---|---|---|
| 1 | **HIGH** | Plane change happens at *perilune* (close to Moon, high v) instead of at *Moon-orbit apoapsis* (far from Moon, low v) for high-eL targets. | +30–50k kg |
| 2 | **HIGH** | Arrival point over-constrained: pv_tgt fixes raan_l=argp_l=0, ea_arr ∈ small grid. Spec says raan/argp/ea are *free*. | +15–30k kg |
| 3 | **HIGH** | 3-impulse DC matches arrival position only; dv2 is post-hoc. Joint (dv0, dv1, dv2, T1, T2) NLP minimizing total dv would find better splits. | +20–40k kg |
| 4 | **MED**  | idD assignment is per-transfer greedy on c_ld, ignores global bipartite competition between high-m_l transfers for high-c_ld idDs. | +5–15k kg |
| 5 | **MED**  | Hungarian uses m_l (un-discounted) instead of m_d = min(m_l, (200−ΔT)·c_ld). Pairs near the c_ld cap get over-prioritized. | +3–10k kg |
| 6 | **LOW**  | Frame mismatch in `syn_to_inertial_earth`: R(t) rotation applied for dv0 derivation but result is treated as synodic. Only bites for t0 ≠ 0 cycles (we mostly used t0=0). | <2k kg |

**Conservative bound on bugfix headroom: +70k kg** (toward ~257k kg / R5 territory). The remaining ~200k to R1 is the legitimate **physical ceiling** imposed by the 92/74/193/41 LEO-mid-high-MEO mix and the absence of low-iL high-eL Moon orbits.

---

## A. Spec interpretation (verified against authoritative UDP)

Source: `reference/SpOC4/Challenge 1 Luna Tomato Logistics/README.md` and the official `reference/spoc4_udp/trajectory-matching.py` (the GraphQL-fetched UDP we mirror in `src/esa_spoc_26/ch1_trajectory.py`).

- **A1. Fitness sign & shape — verified.** UDP returns `[-tomatoe_mass]` (PyGMO convention). Any invalid chromosome → `[0]`. Verified by quoting `reference/spoc4_udp/trajectory-matching.py:113`. Our mirror at `ch1_trajectory.py:210` matches byte-for-byte.
- **A2. Rocket constants — verified.** m_w=5000, m_dry=500, Isp=311 s, g0=pk.G0=9.80665 in both UDP (line 107) and ours (line 201).
- **A3. Decision vector — verified.** 21 floats per transfer; t0/T1/T2 are *non-dimensional BCP time* (UDP line 250: `ta.propagate_for(time)` on raw chromosome value). Our rebank's `T_unit_to_days = pk.SEC2DAY * 3.7567696752e5` correctly converts to days.
- **A4. 200-day deadline — confirmed PER-TRANSFER.** `_real_tomatoe_mass` uses `dt = sum(Ts) * T * pk.SEC2DAY` per transfer (UDP line 76). There is **no global mission-time constraint** — each transfer independently has up to 200 days.
- **A5. cld discount — CRITICAL re-read.** `m_d = (200 − ΔT) · c_ld if (200-ΔT)·c_ld < m_l else m_l` (UDP line 32). So the *delivered* mass is min(m_l, (200−ΔT)·c_ld). Our rebank's idD assignment greedy-picks max c_ld per transfer locally; **does not consider that a high-m_l transfer may waste a high-c_ld idD that a low-m_l transfer needs.** See B5 below.
- **A6. Validation tolerance — confirmed.** `_match_orbit` uses 1e-6 absolute on (e, i) and 1e-6 *relative to L* on a (= 384 m). Tight; explains why our `solve_arrival_eccentric` uses tol=1e-6.

### A7. Spec quote that has been UNDER-EXPLOITED (E-002 / O-013 ancestor)
> "The remaining elements [RAAN, argp, ea] are considered to be not important and thus need not to be targeted." — README.md L161 (Earth orbits), L173 (Moon orbits)

**The UDP `_match_orbit` only checks (a, e, i).** Our `try_bcp_apogee_3impulse` constrains the arrival to a *specific point* on the Moon orbit (`pv_tgt = moon_orbit_state(... ea_arr)` at fixed raan_l=argp_l=0). This is an unforced restriction. See B2.

---

## B. Bugs & risks (each grounded in code or test)

### B1. **HIGH — Plane-change point: code does perilune, spec wants apolune of target orbit**

`src/esa_spoc_26/ch1_bcp_apogee.py:73-82` calls `track_to_perilune` (which scans BCP propagation for *minimum distance to Moon center*) and then applies dv1 at that point. For high-eL Moon orbits with r_apo = a_L·(1+e_L) up to ~8.7×10⁶ m **from Moon center**, the proper plane-change point is at `r ≈ r_apo` from Moon (slow in Moon-relative frame), **not** at perilune (close, fast).

**Quantification:**
- For a high-iE LEO → high-eL Moon target, the bank's (38, 157) transfer at 841 kg uses dv1 = 619 m/s. Implied plane-change velocity ~1200 m/s ⇒ perilune ~ 50,000-100,000 km from Moon.
- Plane change at r_apo (8 × 10⁶ m, Moon-relative velocity ~456 m/s): dv1 for 30° plane change = 2·v·sin(15°) ≈ 236 m/s. **Savings ≈ 380 m/s**, equivalent to ~150 kg per transfer.
- Affects ~150 high-iL high-eL Moon orbits in the dataset.

**Repro:** `python -c "import sys; sys.path.insert(0,'src'); from esa_spoc_26.ch1_trajectory_solve import track_to_perilune; ..."` then compare `r_min` for a high-eL target vs the orbit's r_apo.

**Why this slipped past us:** the function name `track_to_perilune` is correct for LMO targets (eL≈0, r_peri≈aL), where perilune = orbit insertion point. The bug only manifests for high-eL targets where perilune ≠ insertion point.

### B2. **HIGH — Arrival pv_tgt over-constrains raan_l, argp_l, ea_arr**

`src/esa_spoc_26/ch1_bcp_apogee.py:85`:
```python
pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)
```
With `raan_l=0.0, argp_l=0.0, ea_arr ∈ {0, π/2, π, 3π/2}`. The DC then forces position match.

But spec A7 confirms RAAN, argp, ea are *free*. The DC is solving a harder problem than needed: forcing arrival at *one specific point in inertial space* rather than *anywhere on the orbit*.

**The right structure is already in `solve_arrival_eccentric` (`src/esa_spoc_26/ch1_arrival_v2.py:33`)**: given arrival position r_mf, find dv2 such that orbital elements (a, e, i) match — RAAN/argp/ea fall out as whatever satisfies the constraint. We use this for dv2 but not for the upstream DC.

**Fix sketch:** drop pv_tgt entirely; propagate to a chosen arrival time/point, then call `solve_arrival_eccentric` directly. The 4-point `ea_arr` sweep becomes a sweep over *arrival time* instead, which is the real free parameter.

**Quantification:** for the 32 banked (LEO, favorable-Moon) pairs at avg ~700 kg, removing the spurious phase constraint should let the DC settle on lower-dv configurations. ~150 kg/transfer × 32 = ~5k kg. Plus enables previously-rejected pairs for high-eL Moon. Total ~15-30k kg.

### B3. **HIGH — 3-impulse DC is dv1-only; dv0/dv2 don't co-optimize**

`ch1_bcp_apogee.py:89-101` — the DC has 3 dofs (dv1 vector) and 3 constraints (arrival position). **Determined system, not optimization.** The seed `np.zeros(3)` means the DC settles at the smallest-||dv1|| feasible solution, but the *total* (dv0+dv1+dv2) is never minimized.

**Evidence:** in the bank, top-5 mass transfers (idE=277, 270, 279, 261, 263) ALL have `dv1=0`. The 3-impulse architecture collapses to 2-impulse when the geometry is friendly. But for mid-range pairs, dv1 may be doing more work than necessary.

**Fix sketch:** scipy.optimize.minimize on `[dv0_3, dv1_3, T1_scalar, T2_scalar, dv2_3] = 11 vars`, objective = total dv, with equality constraint `state2moon(pv_arr+dv2) ≈ (aL, eL, iL)` (3 equations) — well over-determined, gives an actual minimum. Per-pair cost ~30s; 294 transfers × 30s / 8 workers ≈ 20 min. Likely +20-40k kg.

### B4. **MEDIUM — idD assignment is local-greedy, not global-bipartite**

`scripts/ch1_hungarian_rebank.py:91-105` — for each picked (idE, idL), pick the unused idD with max c_ld. **No consideration that another transfer with higher m_l could use that idD better.**

The 160,000-entry c_ld matrix is fully dense (every idL→idD has a c_ld). Mean=8.4, max=75 kg/day. For high-mass transfers (m_l = 2000+ kg, ΔT = 8d, m_l/cap ratio = 2000/((200-8)·c_ld)), we want c_ld ≥ 10 to avoid cap-limit. Low-mass transfers (~400 kg) are fine with c_ld = 3.

Optimal: **second Hungarian on (transfer_index, idD) with weight = min(m_l, (200−ΔT)·c_ld)**, run after the (idE,idL) Hungarian. NP-hard if joint, but the two-stage approximation is much better than greedy.

**Quantification:** sample 10 transfers in the bank, compute m_d_actual vs m_d_optimal (under perfect bipartite c_ld assignment). My guess: +5-15k kg.

### B5. **MEDIUM — Hungarian score uses m_l, not m_d**

`scripts/ch1_hungarian_rebank.py:73-76`:
```python
M[idE, idL] = mass  # mass is m_l from results (un-discounted)
```

But the objective is m_d = min(m_l, (200−ΔT)·c_ld). If a transfer has m_l = 1000 kg but its best-available c_ld gives cap = 200 kg, the contribution to the objective is 200, not 1000. Hungarian over-values such transfers and may displace a 500-kg-m_l transfer with a much better cap.

**Fix:** score M[idE, idL] = max over idD of min(m_l, (200−ΔT)·c_ld), then do bipartite idD on the picked transfers. Or jointly solve 3D assignment (NP-hard; approximate via LR or matheuristic).

**Quantification:** probably modest (+3-10k kg) because cap-limit is rare (mean c_ld=8.4 is mostly above m_l/(200−ΔT)).

### B6. **LOW — Frame mismatch in dv0 direction for t0 ≠ 0**

`ch1_bcp_apogee.py:36-43`:
```python
def syn_to_inertial_earth(pv_syn, t):
    ...
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return R @ r_syn * L, R @ v_syn_inertial * V
```

This applies the rotation R(t) so that `v0_si` is the spacecraft's *inertial* velocity expressed in *inertial-frame basis*. Then:

```python
dv0_si = v0_si * ((v_peri_trans - v_mag) / v_mag)  # still in inertial basis
dv0_syn = dv0_si / V                                # just rescaled, NOT de-rotated
```

`dv0_syn` is then passed to `track_to_perilune` (`ch1_trajectory_solve.py:247`) which adds it to **synodic** velocity components. **The direction is wrong by R(t0).**

For t0=0, R(0)=I, no error. For t0=π, dv direction flips in xy. Our v6/v7/v8/v9 all used `t0_val ∈ {0.0}` only; v2 used `(0.0, π)` so some early candidates may have been mis-evaluated. **The bug is real but mostly silent given our schedule.**

**Fix:** drop the R(t) rotation entirely. Use the same form as `state2earth` (line 57-66 of `ch1_trajectory.py`), which keeps everything in synodic-at-instant basis — perfectly sufficient since (a, e, i) and dv-magnitude calculations are basis-invariant.

---

## C. Validated assumptions (these are CORRECT)

- **C1.** `state2earth` / `state2moon` derivations match the UDP byte-for-byte; the (vx−y, vy+x, vz) inertial-in-synodic-basis convention is correct and basis-invariant for (a, e, i) computation.
- **C2.** `propagate` (`ch1_trajectory.py:105-142`) faithfully mirrors the UDP's propagator: builds heyoka taylor_adaptive, applies DV[0] at start, propagates Ts[i], applies DV[i+1] sequentially, rejects on Earth/Moon impact. The UDP rebuilds the integrator each call (wasteful but correct); we cache via `_ta()` in `ch1_trajectory_solve.py` — equivalent results, just faster.
- **C3.** `earth_orbit_state` / `moon_orbit_state` round-trip through `state2earth` / `state2moon` to machine precision (the self-test at `ch1_trajectory.py:217-238` confirms).
- **C4.** `solve_arrival_eccentric` correctly handles eL > 0 — the v1 bug (rejecting r ≠ a_L) was real and fixed (S-2026-05-24). The v2 implementation samples multiple velocity seeds and picks min-norm dv2; the (r, v) residual targets (a, e, i) with RAAN/argp/ea free.
- **C5.** Earth-orbit and Moon-orbit dataset sizes: 400 each. Both have 400 unique values, no duplicates. LTL.txt is fully dense (400 × 400 = 160,000 entries). Our loaders read all of it.
- **C6.** Rocket equation (`mass = 5000·exp(-dv/(Isp·g0)) − 500`) is correctly applied with Isp=311, g0=pk.G0=9.80665.
- **C7.** The 200 m (1e-6 × L = 384 m) tolerance on `a` is tight enough that our DC convergence target (1e-3 nondim ≈ 384 km) needs verification per pair; check passes on bank entries we re-evaluate (mass returns same value).

---

## D. Unexplored branches abandoned on weak evidence

### D1. **The v9 "0% valid in 100 pairs" conclusion was premature**

`runs/ch1/59_bcp_apogee_expand_v9.log` recorded 0 valid in the first 100 pairs at t_max=40d + raan_l sweep, and we killed it. But:
- 0/100 success could be because the *pair selection* (iL-matched top-5 unused for the HARD 106) is testing pairs where physics genuinely doesn't allow a transfer (high-iE LEO + high-iL Moon, both > 1.2 rad)
- The conclusion "architecture saturated" doesn't follow from "this *particular* selection fails"
- B1 and B2 above (perilune vs. apolune; over-constrained arrival) are confounders — fix those first, re-test, *then* claim saturation

### D2. **No exploration of the *Earth-apogee* plane change (the actual C-022 name)**

C-022's name says "apogee plane change" but the code does perilune. **We never tried what the name implies.** For LEO Hohmann transfers, the trajectory's Earth-frame apogee is at Moon distance (~3.84×10⁸ m from Earth) where speed is ~190 m/s — extremely cheap plane change point. Plane change there + LOI at Moon would be a different architecture than current.

This was conflated with "perilune" in the implementation (commit fec0f68). The vault note S-2026-05-26 talks about "BCP-tracked apogee" but the function called is `track_to_perilune`. **Branch never opened.**

### D3. **No exploration of multi-revolution / Sun-assist trajectories**

BCP includes the Sun (BCP_MU_S = 3.33×10⁵). For long-duration transfers (TOF > 30 days), Sun's gravity can lower dv requirements (low-energy / WSB transfers). Our t_max = 20-40 days is enough to *reach* but maybe not enough for *exploit*. The leaderboard's 1183 kg/transfer average is **below the impulsive Hohmann+LOI minimum (3.94 km/s ⇒ 892 kg)** for LEO, which strongly suggests competitors use non-Hohmann transfers.

For LEO low-iE, our top is 1095 kg (idE=21, idL=200) at dv=3484 m/s — already *below* canonical Hohmann (3940 m/s). That mass is achievable because we arrive at high-eL Moon apoapsis. So our architecture *can* do non-Hohmann; we just haven't optimized for it broadly.

### D4. **No attempt at unique-idD bipartite reassignment after each rebank**

`ch1_hungarian_rebank.py` does idD assignment ONCE, greedy. We never re-ran a second Hungarian on the (transfer, idD) bipartite graph after picking the top transfers. Could be added in ~50 lines.

### D5. **No attempt to score Hungarian with m_d not m_l**

Easy code change to test (B5). Hasn't been done.

---

## E. Pair-selection priors re-examined

### E1. **"236 unused idEs are all LEO" — verified.**
At session start, all 236 had aE ∈ [6.6, 7.98] × 10⁶ m and iE ∈ [0.19, 1.56] rad. All 41 high-aE (MEO/GEO) Earth orbits were used. So the *bank's* LEO-dominance is real and reflects the dataset (90% LEO).

### E2. **"Favorable 42 Moon idLs" = aL > 4.5e6 & eL > 0.4 — re-derived.**
Of 400 Moon orbits:
- 150 in (high-aL, high-eL, high-iL): the "favorable" cluster, but iL > 0.5 always.
- 0 in (high-eL, low-iL): **the dataset contains NO low-iL high-eL Moon orbits.** So coplanar-LEO → cheap-apoapsis-arrival is impossible by dataset design. *Every* high-eL pair requires plane change.

Distribution by category:
| aL | eL | iL | n | used | unused |
|---|---|---|---|---|---|
| lo (<3M) | lo (<.3) | lo (<.5) | 60 | 28 | 32 |
| lo | lo | hi | 90 | 69 | 21 |
| hi (≥3M) | lo | lo | 38 | 27 | 11 |
| hi | lo | hi | 62 | 37 | 25 |
| hi | hi | hi | 150 | 133 | 17 |

### E3. **The "hard 106" failure mode is not characterized.**
v9 returned `valid=0, uE=0, uL=0` for 100 pairs but the log doesn't say *which* failure: impactor / dv-cap / DC-no-convergence / fitness-rejected. Without this distribution, "architecture is saturated" is unsupported.

---

## F. Top hypothesis for the leaderboard gap

**Ranked by likelihood and grounded in evidence:**

1. **[STRONG] We are leaving ~70k kg on the table from bug B1 + B2 + B3 combined.** Plane-change point misplaced + arrival over-constrained + dv1-only DC. Fixing all three would push us toward ~257k kg without changing the underlying architecture or adding compute. Evidence: top-5 transfers in the bank already prove the architecture can achieve >2500 kg per transfer (dv1=0 collapse to 2-impulse Hohmann+apoapsis-arrival); the LEO low-iE distribution has Q3=696 kg but Q1=228 kg with the same architecture — the gap is implementation-quality, not theoretical ceiling.

2. **[STRONG] Beyond bugfix, the physical ceiling under the (90% LEO, 0% low-iL-high-eL Moon) dataset is roughly 350-400k kg.** Compute:
   - 36 GEO-low-iE × 2000 kg = 72k
   - 5 GEO-mid-iE × 1800 kg = 9k
   - 92 LEO-low-iE × 1100 kg = 101k (theoretical with apoapsis arrival)
   - 74 LEO-mid-iE × 800 kg = 59k
   - 193 LEO-high-iE × 600 kg = 116k (with cheap plane-change at apolune)
   - Total: **357k kg** without any exotic physics.
   To reach R1's 473k, we need an additional **+116k kg** from somewhere — most likely **BCP Sun-assist / multi-revolution / low-energy transfers** that drop dv below the impulsive Hohmann baseline. The R1 average dv of 3320 m/s is *below* the impulsive Hohmann from LEO (3940 m/s), which is strong evidence they exploit Sun-assisted trajectories.

3. **[MODERATE] B4 + B5 (idD assignment) is worth +10-20k kg.** Independent of trajectory physics — pure operations research. Run a second-stage Hungarian on (transfer, idD) with m_d weight, after the (idE, idL) Hungarian.

4. **[MODERATE] Rank-1 to Rank-3 cluster within 20k kg suggests they share a method that bottoms out at ~470-480k.** That implies a *known recipe* in the trajectory-optimization community (Sun-assisted WSB transfers, multi-rev lunar gravity assists) that they all implement. Not exotic.

5. **[LOW] We are computing something fundamentally wrong about the UDP fitness.** The mirror is byte-for-byte and round-trips. The bank fitness re-evaluates correctly on the UDP. This hypothesis is *not* supported by the audit.

---

## G. What to do (decision-grade, ranked by ROI)

In strict priority order — each one's effect can be measured against the bank before doing the next:

1. **Fix B5** (Hungarian m_d not m_l) — 1 hour, expected +3-10k kg, no risk.
2. **Fix B4** (second-stage bipartite idD) — 2 hours, +5-15k kg, no risk.
3. **Fix B2** (drop pv_tgt; use solve_arrival_eccentric directly) — 3 hours, expected +15-30k kg. Re-run v7+v8 with new arrival logic.
4. **Fix B1** (plane change at correct point — needs new "find apolune" or "find Earth-apogee" function) — 1 day, +30-50k kg. Open question: which point is the right one? Likely *Moon-orbit apolune* for high-eL targets and *target periapsis* for LMO. Decision tree per (eL, aL).
5. **Fix B3** (NLP joint optimization per pair) — 1 day, +20-40k kg. Per-pair cost ~30s, ~294 pairs × 30s / 8 workers ≈ 18 min full sweep.
6. **Investigate D3** (Sun-assist / multi-rev) — research-grade, days to weeks, +50-100k kg potential. Only worth pursuing AFTER fixes 1-5 land us at ~250-280k kg.

**Stop and submit at any step** where the bank surpasses your patience for further fixes. The current 186k is already a respectable mid-pack position.

---

## Appendix — file:line citations

- `ch1_bcp_apogee.py:36` — `syn_to_inertial_earth` (B6)
- `ch1_bcp_apogee.py:73` — `track_to_perilune` call (B1)
- `ch1_bcp_apogee.py:85` — `moon_orbit_state` with fixed raan_l/argp_l (B2)
- `ch1_bcp_apogee.py:89-101` — DC seed `np.zeros(3)`, dv1-only (B3)
- `ch1_trajectory_solve.py:239-277` — `track_to_perilune` body
- `ch1_arrival_v2.py:33-128` — `solve_arrival_eccentric` (the correct shape for the upstream solver, currently used only for dv2)
- `ch1_hungarian_rebank.py:73-76` — `M[idE, idL] = mass` (B5: uses m_l not m_d)
- `ch1_hungarian_rebank.py:91-105` — local-greedy idD (B4)
- `reference/spoc4_udp/trajectory-matching.py:32-39` — `_real_tomatoe_mass` (the discount law)
- `reference/spoc4_udp/trajectory-matching.py:53-56` — `_match_orbit` (tolerance + which elements are checked)
- `reference/SpOC4/Challenge 1 Luna Tomato Logistics/README.md` L161, L173 — "RAAN, argp, ea are not important"
