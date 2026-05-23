"""Ch1 Trajectory — Lambert seed + 3-DOF BCP differential corrector.

The current solve_transfer_direct gives 12.6 kg (single positive-mass
transfer at (0,0)). The Lambert 2-body prediction would give 980 kg.
To bridge: use Lambert's predicted arrival point as target, then DC
adjusts dv0 to drive BCP propagation endpoint exactly there.

Strategy per (idE, idL):
1. Grid search outer params (raan_e, argp_e, ea_e, raan_m, argp_m,
   ea_m, tof) to find best Lambert dv (smoke_test logic).
2. Convert Lambert dv1 to BCP synodic dv0_seed.
3. Compute target r_arr in synodic frame at t=tof_nondim:
     r_arr_inertial = r_moon_inertial(t_arr_si) + r_LLO_local
     Transform to synodic at t=tof_nondim → r_arr_synodic
4. DC: adjust (dv0_x, dv0_y, dv0_z) so BCP propagation endpoint
   matches r_arr_synodic. 3 residuals, 3 unknowns.
5. At endpoint, run solve_arrival_dv for the LOI burn (dv2).
6. Total dv = |dv0| + |dv2|. Mass = exp(-dv/...) * 5000 - 500.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON,
    LtlTrajectory, earth_orbit_state, moon_orbit_state, state2moon,
    propagate,
)
from esa_spoc_26.ch1_traj_lambert import (
    lambert_dv, moon_inertial_pos_vel, moon_orbit_around_moon_inertial,
)
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv


def inertial_to_synodic_pos(r_inert, t_nondim):
    """Transform inertial position (m, Earth-centered) to BCP synodic
    coordinates (nondim, barycentric).

    Synodic frame rotates with rate 1 (nondim) about z-axis.
    """
    ct, st = np.cos(t_nondim), np.sin(t_nondim)
    R = np.array([[ct, st, 0], [-st, ct, 0], [0, 0, 1]])
    r_syn = (R @ r_inert) / L
    # Add μ shift: synodic (x, y, z) has Earth at (-μ, 0, 0)
    r_syn[0] -= CR3BP_MU_EARTH_MOON
    return r_syn


def lambert_dc(udp, idE, idL, lambert_best, max_nfev=60, verbose=False):
    """3-DOF DC: refine dv0 so BCP endpoint matches Lambert r_arr."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    raan_e = lambert_best["raan_e"]
    argp_e = lambert_best["argp_e"]
    ea_e = lambert_best["ea_e"]
    tof_si = lambert_best["tof_d"] * 86400
    tof_nd = tof_si / T
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_e)
    dv0_seed = lambert_best["dv1"] / V  # synodic units (just /V; rotation
                                          # correction is zero at t=0 since
                                          # synodic and inertial coincide)
    # Target endpoint position in synodic frame at t=tof_nd
    r_arr_inertial = lambert_best["r_arr"]
    r_arr_syn = inertial_to_synodic_pos(r_arr_inertial, tof_nd)

    def resid(dv0):
        pv1 = propagate(pv0, 0.0, [list(dv0), [0, 0, 0], [0, 0, 0]],
                          [tof_nd, 0.0])
        if len(pv1) == 0:
            return np.array([100.0, 100.0, 100.0])
        return np.array(pv1[0]) - r_arr_syn

    try:
        sol = least_squares(resid, dv0_seed.tolist(), method="trf",
                              xtol=1e-12, max_nfev=max_nfev)
    except Exception as e:
        if verbose:
            print(f"  DC error: {e}")
        return None
    dv0_final = sol.x
    pv1 = propagate(pv0, 0.0, [list(dv0_final), [0, 0, 0], [0, 0, 0]],
                      [tof_nd, 0.0])
    if len(pv1) == 0:
        return None
    # Now apply arrival burn: solve_arrival_dv finds dv2 to match LLO
    dv2_res = solve_arrival_dv(pv1, aM, eM, iM)
    if dv2_res is None:
        if verbose:
            print(f"  arrival_dv failed; endpoint not near LLO")
        return None
    dv2, _ = dv2_res
    row = [idE, idL, 0, 0.0, *pv0[0], *pv0[1],
           *dv0_final.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(),
           float(tof_nd), 0.0]
    f = udp.fitness(row)
    return row, float(f[0]), sol.cost


def best_lambert_seed(udp, idE, idL, raan_grid=6, argp_grid=6, ea_grid=12,
                       raan_m_grid=4, ea_m_grid=4, tof_d_grid=(5, 10, 20, 30, 50, 80)):
    """Quick Lambert grid search for best 2-body dv."""
    aE, eE, iE = udp.earth_data[idE]
    aM, eM, iM = udp.moon_data[idL]
    best = None
    raan_e_arr = np.linspace(0, 2 * np.pi, raan_grid, endpoint=False)
    argp_e_arr = np.linspace(0, 2 * np.pi, argp_grid, endpoint=False)
    ea_e_arr = np.linspace(0, 2 * np.pi, ea_grid, endpoint=False)
    raan_m_arr = np.linspace(0, 2 * np.pi, raan_m_grid, endpoint=False)
    ea_m_arr = np.linspace(0, 2 * np.pi, ea_m_grid, endpoint=False)
    for re_ in raan_e_arr:
        for ae_ in argp_e_arr:
            for ee_ in ea_e_arr:
                for rm_ in raan_m_arr:
                    for em_ in ea_m_arr:
                        for tof_d in tof_d_grid:
                            r = lambert_dv(idE, idL, re_, ae_, ee_,
                                              rm_, 0.0, em_, 0.0,
                                              tof_d * 86400,
                                              aE, eE, iE, aM, eM, iM)
                            if r is None:
                                continue
                            if best is None or r["total"] < best["total"]:
                                best = {**r,
                                          "raan_e": re_, "argp_e": ae_,
                                          "ea_e": ee_, "raan_m": rm_,
                                          "argp_m": 0.0, "ea_m": em_,
                                          "tof_d": tof_d}
    return best


def pipeline(idE, idL, verbose=True):
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    if verbose:
        print(f"\n=== ({idE},{idL}) ===")
    t0 = time.time()
    best = best_lambert_seed(udp, idE, idL)
    if best is None:
        if verbose:
            print(f"  No Lambert seed found")
        return None
    if verbose:
        print(f"  Lambert: total dv = {best['total']:.0f} m/s "
              f"(dv1={best['dv1_mag']:.0f}, dv2={best['dv2_mag']:.0f}, "
              f"tof={best['tof_d']}d), wall={time.time()-t0:.0f}s")
    t0 = time.time()
    res = lambert_dc(udp, idE, idL, best, max_nfev=60, verbose=verbose)
    if res is None:
        if verbose:
            print(f"  DC failed (wall={time.time()-t0:.0f}s)")
        return None
    row, fit, cost = res
    mass = -fit if fit < 0 else 0.0
    if verbose:
        if fit < 0:
            print(f"  ✓ DC mass = {mass:.0f} kg "
                  f"(cost={cost:.2e}, wall={time.time()-t0:.0f}s)")
        else:
            print(f"  ✗ DC rejected by UDP (fit={fit:.4f}, cost={cost:.2e})")
    return row, mass


if __name__ == "__main__":
    idE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    idL = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    pipeline(idE, idL)
