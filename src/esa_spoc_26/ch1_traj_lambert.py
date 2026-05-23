"""Ch1 Trajectory — proper Lambert seeding + BCP refinement.

The under-determined residual bug in solve_transfer_back (O-012) costs
us 4-15 km/s of "extra dv" beyond the physical Hohmann minimum. Per
T-005, validated pipeline exists but uses radius-only targeting.

The proper approach:
1. In Earth-centered INERTIAL frame, solve Lambert from a LEO point
   to a Moon-relative LLO point (with Moon at its actual inertial
   position at arrival time).
2. The Lambert dv1 + dv2 is the physical minimum 2-body dv.
3. Transform Lambert initial state to BCP synodic frame.
4. BCP-propagate forward; expect small residual due to Sun
   perturbation; differential corrector to fix.
5. Output a UDP-format row.

For circular LEO and LLO, Lambert + BCP correction should give
3-5 km/s dv (vs T-005's 20km/s) and 800-1500 kg/transfer mass.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pykep as pk
from scipy.optimize import minimize, least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, MU_SUN,
    CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S,
    LtlTrajectory, earth_orbit_state, moon_orbit_state, state2earth,
    state2moon,
)
from esa_spoc_26.ch1_trajectory_solve import (
    _back_state, _earth_inertial, _moon_inertial, solve_arrival_dv,
)


# Moon's mean motion around Earth (rad/s, SI)
N_MOON_SI = np.sqrt((MU_EARTH + MU_MOON) / L**3)


def moon_inertial_pos_vel(t_si):
    """Moon position and velocity in inertial Earth-centered frame at
    time t (seconds). Approximate as circular orbit at L radius."""
    th = N_MOON_SI * t_si
    r = L * np.array([np.cos(th), np.sin(th), 0])
    v = L * N_MOON_SI * np.array([-np.sin(th), np.cos(th), 0])
    return r, v


def earth_orbit_inertial(a_e, e_e, i_e, raan, argp, ea):
    """LEO orbit point in inertial frame at given Kepler elements."""
    r, v = pk.par2ic([a_e, e_e, i_e, raan, argp, ea], MU_EARTH)
    return np.array(r), np.array(v)


def moon_orbit_around_moon_inertial(a_m, e_m, i_m, raan, argp, ea):
    """LLO orbit point in MOON-CENTERED inertial frame."""
    r, v = pk.par2ic([a_m, e_m, i_m, raan, argp, ea], MU_MOON)
    return np.array(r), np.array(v)


def lambert_dv(idE, idL, raan_e, argp_e, ea_e,
                raan_m, argp_m, ea_m, t_dep_si, tof_si,
                aE, eE, iE, aM, eM, iM):
    """Compute Lambert 2-impulse dv in inertial Earth-centered frame.

    Returns (dv1_mag, dv2_mag, total_dv, dv1_vec, dv2_vec,
              r_dep, v_dep, r_arr, v_arr).
    """
    # LEO departure point
    r_dep, v_LEO = earth_orbit_inertial(aE, eE, iE, raan_e, argp_e, ea_e)
    # Moon position+velocity at arrival
    t_arr_si = t_dep_si + tof_si
    r_moon, v_moon = moon_inertial_pos_vel(t_arr_si)
    # LLO offset around Moon (rotated to inertial; here assume Moon's
    # inertial frame is just Earth's inertial frame translated)
    r_llo_local, v_llo_local = moon_orbit_around_moon_inertial(
        aM, eM, iM, raan_m, argp_m, ea_m)
    r_arr = r_moon + r_llo_local
    v_arr_target = v_moon + v_llo_local

    # Solve Lambert (Earth-centered)
    try:
        lp = pk.lambert_problem(r_dep.tolist(), r_arr.tolist(), tof_si,
                                  MU_EARTH, False, 5)
    except Exception:
        return None
    v_dep_lambert = np.array(lp.get_v1()[0])
    v_arr_lambert = np.array(lp.get_v2()[0])

    dv1 = v_dep_lambert - v_LEO
    dv2 = v_arr_target - v_arr_lambert
    return {
        "dv1": dv1, "dv2": dv2,
        "dv1_mag": float(np.linalg.norm(dv1)),
        "dv2_mag": float(np.linalg.norm(dv2)),
        "total": float(np.linalg.norm(dv1) + np.linalg.norm(dv2)),
        "r_dep": r_dep, "v_dep_lambert": v_dep_lambert,
        "r_arr": r_arr, "v_arr_lambert": v_arr_lambert,
        "v_LEO": v_LEO, "v_arr_target": v_arr_target,
    }


def smoke_test(idE=0, idL=0):
    """Find best Lambert 2-body dv for (idE, idL) via grid search."""
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    print(f"Lambert smoke (idE={idE}, idL={idL}):")
    print(f"  aE={aE/1e6:.1f} Mm, eE={eE:.3f}, iE={iE:.3f}")
    print(f"  aM={aM/1e6:.1f} Mm, eM={eM:.3f}, iM={iM:.3f}")
    best = None
    n_evals = 0
    t0 = time.time()
    for raan_e in np.linspace(0, 2 * np.pi, 6, endpoint=False):
        for argp_e in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            for ea_e in np.linspace(0, 2 * np.pi, 12, endpoint=False):
                for raan_m in [0.0, np.pi / 2, np.pi]:
                    for argp_m in [0.0, np.pi / 2, np.pi]:
                        for ea_m in [0.0, np.pi / 2, np.pi]:
                            for tof_d in [3, 5, 7, 10, 15, 30]:
                                t_dep_si = 0.0  # synodic frame init
                                tof_si = tof_d * 86400
                                r = lambert_dv(idE, idL, raan_e, argp_e, ea_e,
                                                  raan_m, argp_m, ea_m,
                                                  t_dep_si, tof_si,
                                                  aE, eE, iE, aM, eM, iM)
                                n_evals += 1
                                if r is None:
                                    continue
                                if best is None or r["total"] < best["total"]:
                                    best = {**r, "raan_e": raan_e,
                                              "argp_e": argp_e, "ea_e": ea_e,
                                              "raan_m": raan_m, "argp_m": argp_m,
                                              "ea_m": ea_m, "tof_d": tof_d}
    wall = time.time() - t0
    print(f"  Searched {n_evals} Lambert problems in {wall:.0f}s")
    if best is None:
        print("  NO Lambert solution found")
        return None
    mass = float(np.exp(-best["total"] / 311 / 9.80665) * 5000 - 500)
    print(f"  Best Lambert: |dv1|={best['dv1_mag']:.0f}, "
          f"|dv2|={best['dv2_mag']:.0f}, total={best['total']:.0f} m/s")
    print(f"  Implied mass: {mass:.0f} kg")
    print(f"  Params: raan_e={best['raan_e']:.2f}, argp_e={best['argp_e']:.2f}, "
          f"ea_e={best['ea_e']:.2f}, tof={best['tof_d']}d")
    return best


def lambert_to_bcp_row(udp, idE, idL, params):
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    raan_e = params["raan_e"]
    argp_e = params["argp_e"]
    ea_e = params["ea_e"]
    tof_si = params["tof_d"] * 86400
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
    dv1_inertial = params["dv1"]
    dv2_inertial = params["dv2"]
    dv0_syn = (dv1_inertial / V).tolist()
    dv2_syn = (dv2_inertial / V).tolist()
    tof_nondim = tof_si / T
    t0 = 0.0
    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
           *dv0_syn, 0.0, 0.0, 0.0, *dv2_syn,
           float(tof_nondim), 0.0]
    return row


def bcp_refine(udp, idE, idL, lambert_best, max_nfev=80):
    """Differential corrector: Lambert seed → BCP refinement.
    Variables: dv0[3], dv2[3], tof_nondim (7). Residuals: state2moon
    endpoint matches LLO (a, e, i)."""
    from esa_spoc_26.ch1_trajectory import propagate
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    raan_e = lambert_best["raan_e"]
    argp_e = lambert_best["argp_e"]
    ea_e = lambert_best["ea_e"]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
    dv0_seed = (lambert_best["dv1"] / V).tolist()
    dv2_seed = (lambert_best["dv2"] / V).tolist()
    tof_si = lambert_best["tof_d"] * 86400
    tof_nd = tof_si / T

    def resid(x):
        dv0 = list(x[0:3])
        dv2 = list(x[3:6])
        tof = float(x[6])
        pv1 = propagate(pv0, 0.0, [dv0, [0, 0, 0], dv2], [tof, 0.0])
        if len(pv1) == 0:
            return np.array([100.0, 100.0, 100.0])
        try:
            el = state2moon(pv1)
            return np.array([
                (el[0] - aM) / 1e6,
                (el[1] - eM) * 10,
                (el[2] - iM) * 10,
            ])
        except Exception:
            return np.array([100.0, 100.0, 100.0])

    x0 = np.array([*dv0_seed, *dv2_seed, tof_nd])
    try:
        sol = least_squares(resid, x0, method="trf", xtol=1e-10,
                              max_nfev=max_nfev)
    except Exception:
        return None
    dv0 = list(sol.x[0:3])
    dv2 = list(sol.x[3:6])
    tof = float(sol.x[6])
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
           *dv0, 0.0, 0.0, 0.0, *dv2, tof, 0.0]
    f = udp.fitness(row)
    return row, float(f[0]), float(sol.cost)


def lambert_full_pipeline(idE, idL):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    best = smoke_test(idE, idL)
    if best is None:
        print("  no Lambert found")
        return
    # First try raw Lambert without refinement
    row = lambert_to_bcp_row(udp, idE, idL, best)
    f = udp.fitness(row)
    print(f"\n  Raw Lambert UDP fitness: {f[0]:.4f}")
    if f[0] < 0:
        print(f"  ✓ raw Lambert POSITIVE mass = {-f[0]:.0f} kg")
    # Run BCP differential corrector
    print("\n  Running BCP differential corrector...")
    t0 = time.time()
    res = bcp_refine(udp, idE, idL, best)
    if res is None:
        print(f"  ✗ DC failed (wall={time.time()-t0:.1f}s)")
        return
    row, fit, cost = res
    if fit < 0:
        print(f"  ✓ DC POSITIVE mass = {-fit:.0f} kg "
              f"(cost={cost:.2e}, wall={time.time()-t0:.1f}s)")
    else:
        print(f"  ✗ DC rejected by UDP (fit={fit:.4f}, "
              f"cost={cost:.2e}, wall={time.time()-t0:.1f}s)")


if __name__ == "__main__":
    idE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    idL = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    lambert_full_pipeline(idE, idL)
