"""E-566 — GO/NO-GO for impulsive-geometry Ch1 pivot.

Empirically test whether the "corrected patched-conic bound" (in-plane
perigee departure with free RAAN/argp + perilune-tangent LOI) is
REALIZABLE under the OFFICIAL BCP validator on 5 representative pairs.

Pairs:
  (a) (118,171) LEO i=25 -> high-e Moon  (E-036 pair, banked 949)
  (b) (277,189) GEO low-i -> high-e Moon  (our top bank 2628; "96%" test)
  (c) (0,150)   LEO i=0   -> high-e Moon  (not banked)
  (d) (5,1)     LEO i=89  -> LLO i=48     (written-off high-i corner, not banked)
  (e) (261,205) GEO i=2.9 -> high-e Moon  (banked 2567)

For each pair:
  1. Patched-conic CORRECTED bound (in-plane departure, perilune-tangent LOI).
  2. Geometric seed: prograde perigee departure on a free-RAAN/argp Earth
     orbit whose plane is chosen to contain the Earth->Moon line at
     encounter; Lambert to the lunar arrival point; exact eccentric dv2.
  3. Refine with 6-D DC (dv0+dv1, pos+vel match) so dv2 -> the eccentric
     arrival burn; sweep TOF / arrival anomaly / RAAN to maximise mass.
  4. Validate EVERY candidate through the OFFICIAL fitness (a,e,i tol 1e-6
     + BCP impact check). Trust only the official number.

Read-only w.r.t. deliverables. Light compute (<=2 cores).

Run: PYTHONPATH=src OMP_NUM_THREADS=2 micromamba run -n spoc26 \
        python scripts/ch1_e566_geom_gonogo.py
"""
from __future__ import annotations

import math
import time

import numpy as np
import pykep as pk

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON as MU,
    LtlTrajectory, earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

BASE = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
RE = 6378137.0
DAY = 86400.0 / T
G0 = pk.G0
ISP = 311.0

# pair -> (idD for cap, current banked m_l, "label")
PAIRS = [
    (118, 171, 213, 949.4, "(a) LEO i25 -> hi-e Moon  [E-036]"),
    (277, 189, 157, 2628.3, "(b) GEO low-i -> hi-e Moon [top bank]"),
    (0, 150, 248, 0.0, "(c) LEO i0  -> hi-e Moon  [unbanked]"),
    (5, 1, 289, 0.0, "(d) LEO i89 -> LLO i48     [hi-i corner]"),
    (261, 205, 123, 2566.8, "(e) GEO i3  -> hi-e Moon  [banked]"),
]


def mass_from_dv(dv_ms):
    return math.exp(-dv_ms / ISP / G0) * 5000.0 - 500.0


# --------------------------------------------------------- patched-conic bound
def patched_conic_bound(aE, eE, iE, aL, eL, iL):
    """CORRECTED impulsive bound (m/s and kg) per the analysis:

    dv0: from Earth-orbit perigee, raise apogee to the lunar distance
         (Hohmann-like departure; in-plane, free RAAN so node aligns).
    dv1: small midcourse / plane-twist, here taken 0 (best case).
    dv2: perilune-tangent insertion (Oberth) to a high-e Moon orbit.
         arrive on a hyperbola at the Moon orbit's PERILUNE radius;
         burn tangentially from v_hyp_peri to v_orbit_peri.

    Inclination cost: with free RAAN the departure can be in-plane;
    the only plane mismatch is between the arrival hyperbola plane and
    the target Moon-orbit plane. Best case it is absorbed by choosing the
    asymptote in-plane => 0 plane-change penalty. This is the OPTIMISTIC
    bound the GO/NO-GO is testing.
    """
    D = L  # Earth-Moon distance ~ a of synodic frame
    rp_E = aE * (1 - eE)
    # departure: from rp_E, vis-viva on transfer ellipse with apogee ~ D
    a_t = 0.5 * (rp_E + D)
    v_peri_E = math.sqrt(MU_EARTH * (2.0 / rp_E - 1.0 / aE))      # current
    v_peri_t = math.sqrt(MU_EARTH * (2.0 / rp_E - 1.0 / a_t))     # transfer
    dv0 = abs(v_peri_t - v_peri_E)
    # arrival v_inf at Moon: speed of transfer ellipse at r=D minus Moon orbital speed
    v_arr = math.sqrt(MU_EARTH * (2.0 / D - 1.0 / a_t))
    v_moon = math.sqrt(MU_EARTH / D)
    v_inf = abs(v_arr - v_moon)
    # perilune-tangent insertion onto target Moon orbit at its perilune
    rp_M = aL * (1 - eL)
    v_hyp_peri = math.sqrt(v_inf ** 2 + 2.0 * MU_MOON / rp_M)
    v_orb_peri = math.sqrt(MU_MOON * (2.0 / rp_M - 1.0 / aL))     # high-e orbit perilune speed
    dv2 = abs(v_hyp_peri - v_orb_peri)
    dv = dv0 + dv2
    return dv, mass_from_dv(dv), (dv0, 0.0, dv2, v_inf)


# --------------------------------------------------------- geometric seed solve
def lambert_dv0(pv0, r1_si, tof):
    """Lambert from pv0 (synodic Earth orbit state) to inertial-Earth r1_si."""
    x, y, z = pv0[0]
    vx, vy, vz = pv0[1]
    r0 = np.array([(x + MU) * L, y * L, z * L])
    v0 = np.array([(vx - y) * V, (vy + x + MU) * V, vz * V])  # inertial, Earth-centered
    try:
        lp = pk.lambert_problem(r0.tolist(), r1_si.tolist(), tof * T,
                                MU_EARTH, False, 0)
    except Exception:
        return None
    v1 = np.array(lp.get_v1()[0])
    return (v1 - v0) / V


def moon_inertial_pos(pv_arr_syn):
    """Earth-centered inertial position of a synodic arrival state (m)."""
    x, y, z = pv_arr_syn[0]
    return np.array([(x + MU) * L, y * L, z * L])


def try_geom(udp, idE, idL, raan_E, argp_E, ea_dep, ea_arr, raan_M, argp_M,
             tof_d, idD):
    """Build a geometric seed: depart from perigee of Earth orbit at chosen
    free RAAN/argp, Lambert to a chosen point on the Moon orbit (arrival
    target with its own free RAAN/argp/EA), 6-D DC dv0+dv1, eccentric dv2.
    Return (mass, row, info) or None."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_E, argp_E, ea_dep)
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_M, argp_M, ea_arr)
    tof = tof_d * DAY

    # inertial-Earth target position = Moon orbit point + Moon position at tof.
    # Moon position in synodic frame is fixed at (1-MU,0,0); its inertial
    # position rotates with the frame. We target the synodic arrival position
    # directly via 6-D DC, seeding dv0 with a Lambert to the *synodic* point
    # mapped to inertial at t=0 (a crude seed; DC fixes the rest).
    r1_si = moon_inertial_pos(pv_tgt)
    dv0_seed = lambert_dv0(pv0, r1_si, tof)
    if dv0_seed is None or not np.all(np.isfinite(dv0_seed)):
        return None
    if np.linalg.norm(dv0_seed) * V > 6000.0:
        return None

    # 6-D DC: dv0 + dv1 (split TOF), match arrival pos+vel to pv_tgt.
    split = 0.55
    T1, T2 = split * tof, (1 - split) * tof

    def resid(p):
        dv0 = p[:3].tolist()
        dv1 = p[3:6].tolist()
        pv_a = propagate(pv0, 0.0, [dv0, dv1, [0, 0, 0]], [T1, T2])
        if len(pv_a) == 0:
            return [50.0] * 6
        return [pv_a[0][0] - pv_tgt[0][0], pv_a[0][1] - pv_tgt[0][1],
                pv_a[0][2] - pv_tgt[0][2], pv_a[1][0] - pv_tgt[1][0],
                pv_a[1][1] - pv_tgt[1][1], pv_a[1][2] - pv_tgt[1][2]]

    from scipy.optimize import least_squares
    x0 = np.array([*dv0_seed, 0.0, 0.0, 0.0])
    try:
        sol = least_squares(resid, x0, method="trf", xtol=1e-13, ftol=1e-13,
                            max_nfev=120)
    except Exception:
        return None
    dv0, dv1 = sol.x[:3], sol.x[3:6]
    pv_arr = propagate(pv0, 0.0, [dv0.tolist(), dv1.tolist(), [0, 0, 0]],
                       [T1, T2])
    if len(pv_arr) == 0:
        return None
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return None
    dv2 = res[0]
    row = [idE, idL, idD, 0.0, *pv0[0], *pv0[1], *dv0.tolist(),
           *dv1.tolist(), *dv2.tolist(), T1, T2]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv0n, dv1n, dv2n = (np.linalg.norm(dv0) * V, np.linalg.norm(dv1) * V,
                        np.linalg.norm(dv2) * V)
    return mass, row, dict(dv0=dv0n, dv1=dv1n, dv2=dv2n,
                           dv=dv0n + dv1n + dv2n,
                           dt=(T1 + T2) / DAY)


def scan_pair(udp, idE, idL, idD, tof_grid, n_dep, n_arr, n_raanM,
              t_budget):
    """Geometric scan: free Earth RAAN = aligned to encounter is realised
    by sweeping departure mean-anomaly + Moon-orbit RAAN/EA; we coarse-grid
    these and keep the best official-validated candidate."""
    aE, eE, iE = udp.earth_data[idE]
    best = None
    t0 = time.time()
    n_try = n_valid = 0
    # Earth departure at perigee (ea_dep=0); sweep Earth RAAN to align node.
    raanE_grid = np.linspace(0, 2 * np.pi, n_dep, endpoint=False)
    raanM_grid = np.linspace(0, 2 * np.pi, n_raanM, endpoint=False)
    eaM_grid = np.linspace(0, 2 * np.pi, n_arr, endpoint=False)
    for tof_d in tof_grid:
        for raanE in raanE_grid:
            for raanM in raanM_grid:
                for eaM in eaM_grid:
                    if time.time() - t0 > t_budget:
                        if best:
                            print(f"    [budget hit after {n_try} tries]",
                                  flush=True)
                        return best, n_try, n_valid
                    n_try += 1
                    r = try_geom(udp, idE, idL, raanE, 0.0, 0.0, eaM,
                                 raanM, 0.0, tof_d, idD)
                    if r is None:
                        continue
                    n_valid += 1
                    if best is None or r[0] > best[0]:
                        best = r
    return best, n_try, n_valid


def main():
    udp = LtlTrajectory(BASE)
    print("=" * 78)
    print("E-566 GO/NO-GO: impulsive-geometry bound realizability (official BCP)")
    print("=" * 78)
    results = []
    for idE, idL, idD, banked, label in PAIRS:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        dv_b, m_b, brk = patched_conic_bound(aE, eE, iE, aL, eL, iL)
        print(f"\n### {label}  idE={idE} idL={idL}")
        print(f"  Earth: a={aE/1e3:.0f}km e={eE:.3f} i={math.degrees(iE):.1f}deg"
              f"  | Moon: a={aL/1e3:.0f}km e={eL:.3f} i={math.degrees(iL):.1f}deg")
        print(f"  patched-conic CORRECTED bound: dv={dv_b:.0f} m/s "
              f"(dv0={brk[0]:.0f} dv2={brk[2]:.0f} v_inf={brk[3]:.0f}) "
              f"-> {m_b:.0f} kg   [banked={banked:.0f}]")
        t_st = time.time()
        # budget ~60s/pair scan; coarse grid
        best, n_try, n_valid = scan_pair(
            udp, idE, idL, idD,
            tof_grid=(4.0, 5.0, 6.0, 8.0, 10.0),
            n_dep=4, n_arr=8, n_raanM=4, t_budget=70.0)
        dt_scan = time.time() - t_st
        if best is None:
            print(f"  SCAN: no valid candidate ({n_try} tries, {dt_scan:.0f}s)")
            results.append((label, idE, idL, m_b, 0.0, banked, None))
            continue
        m, row, info = best
        ratio = m / m_b if m_b > 0 else float('nan')
        print(f"  SCAN: {n_valid}/{n_try} valid in {dt_scan:.0f}s; "
              f"BEST official mass={m:.1f} kg")
        print(f"        dv={info['dv']:.0f} (dv0={info['dv0']:.0f} "
              f"dv1={info['dv1']:.0f} dv2={info['dv2']:.0f}) dt={info['dt']:.1f}d"
              f"  ratio_to_bound={ratio:.2f}  vs_banked={m-banked:+.0f}")
        results.append((label, idE, idL, m_b, m, banked, info))

    # ---- summary table + verdict ----
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"{'pair':>10} {'bound_kg':>9} {'achieved':>9} {'ratio':>6} "
          f"{'banked':>8} {'vs_bank':>8}")
    ratios, beats = [], []
    for label, idE, idL, m_b, m, banked, info in results:
        ratio = m / m_b if m_b > 0 else 0.0
        if m > 0:
            ratios.append(ratio)
            beats.append(m > banked)
        print(f"{idE:4d},{idL:4d} {m_b:9.0f} {m:9.1f} {ratio:6.2f} "
              f"{banked:8.0f} {m-banked:+8.0f}")
    if ratios:
        med = float(np.median(ratios))
        all_beat = all(beats)
        print(f"\nmedian ratio-to-bound = {med:.2f}; "
              f"achieved>banked on all sampled = {all_beat}")
        verdict = "GO" if (med >= 0.85 and all_beat) else "NO-GO"
        print(f"VERDICT: {verdict}")
    else:
        print("\nVERDICT: NO-GO (no valid candidates constructed)")


if __name__ == "__main__":
    main()
