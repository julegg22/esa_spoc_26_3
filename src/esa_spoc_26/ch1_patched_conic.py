"""Patched-conic Earth→Moon transfer with SOI handoff + BCP refinement.

Standard textbook approach (Vallado §11, Wiesel §6):
1. Pick (idE, idL, ea_dep, ea_arr) and TOF
2. In 2-body EARTH-only: Lambert from Earth-orbit point → Moon SOI entry
3. Compute v_inf at SOI (Moon-relative)
4. In 2-body MOON-only: hyperbolic trajectory from SOI entry → periselene
5. dv2 at periselene → circular LLO at aL
6. Pack as chromosome row, propagate in BCP for verification
7. (Optional) DC: dv1 mid-course correction to fix BCP perturbation drift

This builds the SEED that Lambert+DC alone couldn't construct for
inclined pairs. The patched-conic geometry handles the inclination
change naturally via the SOI-side Lambert.
"""
from __future__ import annotations

import numpy as np
import pykep as pk
from scipy.optimize import brentq, least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv

MU = CR3BP_MU_EARTH_MOON
R_SOI = 66200e3  # Moon's sphere of influence radius, m
R_MOON_SI = 384400e3


def _syn_to_inertial_earth(pv_syn, t):
    """Synodic state → Earth-centered inertial (SI, m and m/s)."""
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    r_syn = np.array([x + MU, y, z])
    v_syn_in_synodic_axes = np.array([vx - y, vy + (x + MU), vz])
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return R @ r_syn * L, R @ v_syn_in_synodic_axes * V


def _moon_position_inertial_si(t):
    """Moon's position in inertial frame at nondim time t (Earth-centered)."""
    # Moon at (1-MU, 0, 0) in synodic, with rotation by t in z
    c, s = np.cos(t), np.sin(t)
    return np.array([(1 - MU) * c, (1 - MU) * s, 0.0]) * L


def _moon_velocity_inertial_si(t):
    """Moon's inertial velocity at time t (Earth-centered)."""
    # In synodic frame, Moon is stationary. So inertial velocity = omega × r.
    # omega = (0,0,1) nondim → 1 nondim per T sec. v_moon = nondim_omega_cross_r * L/T = V.
    c, s = np.cos(t), np.sin(t)
    return np.array([-(1 - MU) * s, (1 - MU) * c, 0.0]) * V


def patched_conic_seed(aE, eE, iE, aL, eL, iL, ea_dep, raan_e, argp_e,
                        ea_arr, raan_l, argp_l, tof_earth_d, tof_moon_d):
    """Construct patched-conic chromosome row + dv values.

    Args:
        aE, eE, iE: Earth orbit elements (SI, rad)
        aL, eL, iL: Moon orbit elements (SI, rad)
        ea_dep: departure anomaly on Earth orbit (rad)
        raan_e, argp_e: Earth orbit orientation knobs (rad) — chromosome-free
        ea_arr: arrival anomaly on Moon orbit (rad)
        raan_l, argp_l: Moon orbit orientation knobs (rad)
        tof_earth_d: TOF Earth side (departure → SOI entry) in days
        tof_moon_d: TOF Moon side (SOI entry → periselene) in days

    Returns:
        (dv0_syn, dv1_syn, dv2_syn, T1, T2, total_dv_ms, pv0) or None if infeasible.
    """
    # 1) Departure state in synodic + inertial
    pv0_syn = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    r0_si, v0_si = _syn_to_inertial_earth(pv0_syn, 0.0)

    # 2) SOI entry point (Moon-relative): pick a point at distance R_SOI from
    #    Moon center; for simplicity, on the Earth-Moon line at TOF_earth.
    tof_E = tof_earth_d * 86400.0 / T  # nondim
    tof_M = tof_moon_d * 86400.0 / T   # nondim
    total_tof = tof_E + tof_M
    # Arrival time in nondim
    t_arr = total_tof
    t_soi = tof_E

    # SOI entry: a point at R_SOI from Moon center, AHEAD of Moon along Earth-Moon line
    # (spacecraft arrives "from Earth side"). In inertial at t_soi:
    moon_pos_at_soi_si = _moon_position_inertial_si(t_soi)
    moon_vel_at_soi_si = _moon_velocity_inertial_si(t_soi)
    # SOI entry direction: from Moon toward Earth, then offset by R_SOI
    earth_dir = -moon_pos_at_soi_si / np.linalg.norm(moon_pos_at_soi_si)
    r_soi_entry_si = moon_pos_at_soi_si + earth_dir * R_SOI

    # 3) Earth-side Lambert: r0 → r_soi_entry over tof_E
    try:
        lp_e = pk.lambert_problem(r0_si.tolist(), r_soi_entry_si.tolist(),
                                    tof_E * T, MU_EARTH, False, 0)
        v1_si = np.array(lp_e.get_v1()[0])    # departure inertial velocity (post-burn)
        v_soi_arr_si = np.array(lp_e.get_v2()[0])  # arrival inertial v at SOI
    except Exception:
        return None
    dv0_si = v1_si - v0_si
    if np.linalg.norm(dv0_si) > 20000:  # > 20 km/s — reject
        return None
    if not np.all(np.isfinite(dv0_si)):
        return None

    # Moon-relative velocity at SOI entry (v_inf-ish)
    v_inf_si = v_soi_arr_si - moon_vel_at_soi_si

    # 4) Moon-side: from SOI entry to periselene at aL altitude
    # Moon-relative position at SOI entry:
    r_soi_moon_rel = r_soi_entry_si - moon_pos_at_soi_si  # = earth_dir * R_SOI
    # Target arrival point on Moon orbit:
    pv_target_syn = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)
    # In inertial at t_arr:
    r_tgt_inertial_earth, _ = _syn_to_inertial_earth(pv_target_syn, t_arr)
    r_tgt_moon_rel = r_tgt_inertial_earth - _moon_position_inertial_si(t_arr)

    # Moon-centered Lambert from SOI entry to target
    try:
        lp_m = pk.lambert_problem(r_soi_moon_rel.tolist(),
                                    r_tgt_moon_rel.tolist(),
                                    tof_M * T, MU_MOON, False, 0)
        v_soi_post_si_moonrel = np.array(lp_m.get_v1()[0])
        v_periselene_moonrel = np.array(lp_m.get_v2()[0])
    except Exception:
        return None

    # dv1 = post-SOI velocity (Moon-centered) - pre-SOI velocity (Moon-relative)
    # Add Moon's velocity back to get inertial:
    v_post_soi_inertial = v_soi_post_si_moonrel + moon_vel_at_soi_si
    dv1_si = v_post_soi_inertial - v_soi_arr_si
    if np.linalg.norm(dv1_si) > 20000:
        return None
    if not np.all(np.isfinite(dv1_si)):
        return None

    # 5) Periselene arrival: dv2 to circularize at aL with inclination iL
    # We'll let solve_arrival_dv handle this after BCP propagation
    # (it computes the right dv2 given the actual arrival state)

    # Convert to synodic dv (instantaneous burn = same vector / V)
    dv0_syn = dv0_si / V
    dv1_syn = dv1_si / V

    # T1 = tof_E (post-dv0 coast to SOI), T2 = tof_M (post-dv1 coast to periselene)
    T1, T2 = tof_E, tof_M

    return dv0_syn, dv1_syn, pv0_syn, T1, T2


def evaluate_patched_conic(udp, idE, idL, ea_dep, ea_arr, tof_earth_d,
                             tof_moon_d, raan_e=0.0, argp_e=0.0,
                             raan_l=0.0, argp_l=0.0):
    """Build patched-conic seed → propagate in BCP → solve_arrival_dv → fitness.

    Returns (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    seed = patched_conic_seed(aE, eE, iE, aL, eL, iL,
                                 ea_dep, raan_e, argp_e,
                                 ea_arr, raan_l, argp_l,
                                 tof_earth_d, tof_moon_d)
    if seed is None:
        return None
    dv0_syn, dv1_syn, pv0_syn, T1, T2 = seed

    # BCP propagation with the patched-conic dv0 + dv1
    pv_arr = propagate(pv0_syn, 0.0,
                        [dv0_syn.tolist(), dv1_syn.tolist(), [0, 0, 0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None

    dv2_res = solve_arrival_dv(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0_syn[0], *pv0_syn[1],
            *dv0_syn.tolist(), *dv1_syn.tolist(), *dv2.tolist(),
            T1, T2]
    f = udp.fitness(row)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv1_syn)
              + np.linalg.norm(dv2)) * V
    return mass, row, dv_ms


def solve_pair_patched_conic(udp, idE, idL, n_ea_dep=8, n_ea_arr=8,
                                tof_earth_grid=(3, 5, 7), tof_moon_grid=(0.5, 1.5, 3.0),
                                verbose=False):
    """Multi-start patched-conic for ONE pair."""
    best = None
    n_tried, n_valid = 0, 0
    for ea_dep in np.linspace(0, 2 * np.pi, n_ea_dep, endpoint=False):
        for ea_arr in np.linspace(0, 2 * np.pi, n_ea_arr, endpoint=False):
            for tof_e in tof_earth_grid:
                for tof_m in tof_moon_grid:
                    n_tried += 1
                    res = evaluate_patched_conic(udp, idE, idL,
                                                    ea_dep, ea_arr,
                                                    tof_e, tof_m)
                    if res is not None:
                        n_valid += 1
                        mass, row, dv_ms = res
                        if best is None or mass > best[0]:
                            best = (mass, row, dv_ms,
                                    float(ea_dep), float(ea_arr), tof_e, tof_m)
                            if verbose:
                                print(f"  ✓ ea=({ea_dep:.2f},{ea_arr:.2f}) "
                                      f"tof=({tof_e},{tof_m})d: mass={mass:.0f}kg "
                                      f"dv={dv_ms:.0f}m/s", flush=True)
    return best, n_tried, n_valid


if __name__ == "__main__":
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    import time
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    test_pairs = [
        (0, 0),       # coplanar — sanity (should still work)
        (27, 116),    # LEO + low-iL: 5° plane angle (failed in prior test)
        (267, 185),   # GEO + inclined
        (294, 315),
    ]
    for idE, idL in test_pairs:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        print(f"\n=== Pair ({idE},{idL}): aE={aE/1e3:.0f}km iE={iE:.2f}, "
              f"aL={aL/1e3:.0f}km iL={iL:.2f} ===", flush=True)
        t0 = time.time()
        best, ntried, nvalid = solve_pair_patched_conic(
            udp, idE, idL, n_ea_dep=8, n_ea_arr=8,
            tof_earth_grid=(3, 5, 7), tof_moon_grid=(0.5, 1.5, 3.0),
            verbose=True)
        dt = time.time() - t0
        print(f"  scanned {ntried} ICs in {dt:.0f}s, {nvalid} valid", flush=True)
        if best:
            mass, row, dv_ms, ea_d, ea_a, tof_e, tof_m = best
            print(f"  BEST: mass={mass:.0f}kg dv={dv_ms:.0f}m/s "
                  f"ea=({ea_d:.2f},{ea_a:.2f}) tof=({tof_e},{tof_m})d",
                  flush=True)
