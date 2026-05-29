"""BCP-aware 3-impulse with track-to-closest-approach phasing.

Key insight (S-2026-05-26 ultrathink): the 2-body Hohmann phasing
(raan_e = TOF - π) breaks down in BCP because Moon's gravity perturbs
the trajectory. Solution: use BCP propagation itself to find when
spacecraft is closest to Moon, then apply dv1 there.

Architecture:
1. pv0 in Earth orbit (tilted plane)
2. dv0 = pure prograde Hohmann (in Earth orbit's tilted plane)
   No plane change at Earth — this is the KEY structural fix.
3. BCP propagate forward, TRACKING closest approach to Moon
4. At closest approach: dv1 = plane change (cheap at low velocity)
5. Brief coast (T2 ~0.5d)
6. dv2 = LOI via solve_arrival_eccentric

For inclined Earth orbits (iE > 0.3) where current solver fails due to
plane-change-at-Earth cost, this architecture pays cost at Moon (low
velocity) instead. Expected per-pair gain: 5×-200× for failing pairs.
"""
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import track_to_perilune
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def syn_to_inertial_earth(pv_syn, t):
    """Earth-centered (r, v) in synodic-basis-at-instant convention.

    AUDIT FIX B6 (2026-05-28): previously applied R(t) rotation to convert
    to *fixed* inertial basis. The resulting dv was then used as-if it were
    in the synodic basis — silently flipping the x-component sign for
    t=π trajectories (impactors). Removed the rotation: result is in the
    same convention as state2earth, which makes the dv directly usable
    as a synodic-basis Δv (orbital elements being basis-invariant).
    The `t` parameter is unused but kept for backwards-compat.
    """
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    r_syn = np.array([x + MU, y, z])
    v_syn_inertial = np.array([vx - y, vy + (x + MU), vz])
    return r_syn * L, v_syn_inertial * V


def try_bcp_apogee_3impulse(udp, idE, idL, raan_e, argp_e, ea_dep, t0,
                               raan_l=0.0, argp_l=0.0, ea_arr=0.0,
                               t2_d=0.5, t_max_d=20):
    """3-impulse with BCP-tracked apogee placement.

    No analytical phasing assumed — let BCP propagation find closest
    approach to Moon, then dv1 there.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # Step 1: pure prograde Hohmann burn
    r0_si, v0_si = syn_to_inertial_earth(pv0, t0)
    r0_n = np.linalg.norm(r0_si)
    v_mag = np.linalg.norm(v0_si)
    a_trans = (r0_n + R_MOON_SI) / 2
    v_peri_trans = np.sqrt(MU_EARTH * (2.0 / r0_n - 1.0 / a_trans))
    dv0_si = v0_si * ((v_peri_trans - v_mag) / v_mag)
    if not np.all(np.isfinite(dv0_si)):
        return None
    dv0_syn = dv0_si / V
    if np.linalg.norm(dv0_syn) > 8:
        return None

    # Step 2: BCP propagation, find closest approach to Moon
    t_max_nondim = t_max_d * 86400.0 / T
    try:
        t_apo, state_apo, r_min_m, impacted = track_to_perilune(
            pv0, t0, dv0_syn.tolist(), t_max_nondim)
    except Exception:
        return None
    if impacted or r_min_m > 200e6:  # > 200k km — too far from Moon
        return None

    T1 = t_apo  # nondim time to closest approach
    pv_apo = [list(state_apo[:3]), list(state_apo[3:6])]

    # Step 3: target Moon orbit point
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)
    T2 = t2_d * 86400.0 / T

    # Step 4: DC on dv1 for arrival position match
    def residual(dv1):
        pv_arr = propagate(pv_apo, t0 + T1,
                            [[0, 0, 0], dv1.tolist(), [0, 0, 0]],
                            [0.0, T2])
        if len(pv_arr) == 0:
            return [100.0] * 3
        return [pv_arr[0][0] - pv_tgt[0][0],
                pv_arr[0][1] - pv_tgt[0][1],
                pv_arr[0][2] - pv_tgt[0][2]]

    try:
        sol = least_squares(residual, np.zeros(3), method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=60)
    except Exception:
        return None
    dv1_syn = sol.x
    if not np.all(np.isfinite(dv1_syn)) or np.linalg.norm(dv1_syn) > 5:
        return None

    pv_arr = propagate(pv_apo, t0 + T1,
                        [[0, 0, 0], dv1_syn.tolist(), [0, 0, 0]],
                        [0.0, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2_syn, _ = dv2_res

    # BUGFIX 2026-05-29: use BEST-c_ld idD for validation, return raw m_l.
    # Previously used idD=0; for idLs where c_ld[idL,0] is small, valid
    # trajectories with m_l=300 kg got rejected because m_d = min(m_l,
    # (200-dt)*c_ld) was near zero. Hungarian rebank computes m_l from
    # dv components anyway, so the m_d-filter was throwing away good pairs.
    best_d = 0
    best_cld = -1.0
    for d in range(400):
        if (idL, d) in udp.ltl_dict:
            c = udp.ltl_dict[(idL, d)]
            if c > best_cld:
                best_cld = c
                best_d = d
    row = [idE, idL, best_d, t0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), *dv1_syn.tolist(), *dv2_syn.tolist(),
            T1, T2]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    # Compute raw m_l from dv components (NOT the UDP-discounted m_d)
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv1_syn)
              + np.linalg.norm(dv2_syn)) * V
    import math as _m
    m_l = _m.exp(-dv_ms / (311.0 * 9.80665)) * 5000.0 - 500.0
    if m_l <= 0:
        return None
    return m_l, row, dv_ms


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar control (banked 819)"),
        (213, 19, "LEO+iL=1.07 (banked 5)"),
        (303, 109, "LEO+iL=1.08 (banked 24)"),
        (244, 105, "LEO+iL=0.50 (banked 49)"),
        (227, 315, "LEO+iL=0.47 (banked 27)"),
    ]

    print("BCP-tracked apogee 3-impulse test:", flush=True)
    print(f"{'pair':>10} {'desc':<28} {'mass':>5} {'dv0':>5} {'dv1':>5} {'dv2':>5} {'tot':>5}",
          flush=True)
    for idE, idL, desc in test_cases:
        t_start = time.time()
        best = None
        # Sweep raan_e (8), argp_e (3), ea_dep (4), t0 (3), ea_arr (4), t2_d (3)
        for raan_e in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            for argp_e in (0.0, np.pi, np.pi / 2):
                for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                    for t0_val in (0.0, np.pi, 2 * np.pi):
                        for ea_arr in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                            for t2_d in (0.3, 0.7, 1.5):
                                res = try_bcp_apogee_3impulse(
                                    udp, idE, idL, raan_e, argp_e, ea_dep,
                                    t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                                if res is not None and (best is None
                                                          or res[0] > best[0]):
                                    best = res
        dt = time.time() - t_start
        if best:
            mass, row, dv_tot = best
            dv0 = np.sqrt(row[10]**2+row[11]**2+row[12]**2) * V
            dv1 = np.sqrt(row[13]**2+row[14]**2+row[15]**2) * V
            dv2 = np.sqrt(row[16]**2+row[17]**2+row[18]**2) * V
            print(f"  ({idE:>3},{idL:>3}) {desc:<28} {mass:>5.0f} "
                  f"{dv0:>5.0f} {dv1:>5.0f} {dv2:>5.0f} {dv_tot:>5.0f} ({dt:.0f}s)",
                  flush=True)
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<28} FAIL ({dt:.0f}s)",
                  flush=True)
