"""Proper 3-impulse with plane change at apogee (classical Wiesel §6.5).

Architecture:
1. pv0 in Earth orbit's tilted plane.
2. dv0 = pure prograde burn in Earth orbit's plane → raises apogee.
   NO plane change at Earth (avoids the 1500+ m/s tax for inclined LEO).
3. Coast to apogee (~Hohmann half-period).
4. dv1 = plane change at apogee where v is small (~few hundred m/s).
5. Coast briefly to Moon orbit point.
6. dv2 = capture (LOI).

Total dv = Hohmann + plane_change_at_apogee + LOI
        ~ 3242 + 200 + 800 = 4242 m/s for LEO+inclined Moon
        vs 5400 m/s achieved by our 2-impulse solver.

For each (idE, idL): sweep (raan_e, argp_e, ea_dep, TOF, t0) such that
apogee timing matches Moon position, then DC on dv1 for fine alignment.
"""
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def syn_to_inertial_earth(pv_syn, t):
    """Synodic state → Earth-centered inertial (SI)."""
    x, y, z = pv_syn[0]
    vx, vy, vz = pv_syn[1]
    r_syn = np.array([x + MU, y, z])
    v_syn_inertial = np.array([vx - y, vy + (x + MU), vz])
    c, s = np.cos(t), np.sin(t)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return R @ r_syn * L, R @ v_syn_inertial * V


def try_apogee_plane_change(udp, idE, idL, raan_e, argp_e, ea_dep,
                              raan_l, argp_l, ea_arr, t0, t2_d=1.5):
    """Build and DC-correct the 3-impulse plane-change-at-apogee trajectory.

    Args:
        raan_e, argp_e, ea_dep: Earth orbit orientation/anomaly knobs
        raan_l, argp_l, ea_arr: Moon orbit knobs
        t0: Sun phase (nondim)
        t2_d: Moon-side coast time (days)

    Returns: (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # 1. Compute dv0: pure prograde Hohmann to lunar distance, in Earth orbit's plane
    r0_si, v0_si = syn_to_inertial_earth(pv0, t0)
    r0_n = np.linalg.norm(r0_si)
    v0_mag = np.linalg.norm(v0_si)
    # Hohmann transfer apogee = R_MOON
    a_trans = (r0_n + R_MOON_SI) / 2
    # Velocity at perigee of transfer ellipse:
    v_peri_trans = np.sqrt(MU_EARTH * (2.0 / r0_n - 1.0 / a_trans))
    # dv0 = pure prograde (in direction of v0):
    dv0_si = v0_si * ((v_peri_trans - v0_mag) / v0_mag)
    if not np.all(np.isfinite(dv0_si)):
        return None

    # Hohmann half-period (Earth 2-body)
    T1_sec = np.pi * np.sqrt(a_trans**3 / MU_EARTH)
    T1 = T1_sec / T  # nondim

    # Total TOF = T1 + T2
    T2 = t2_d * 86400.0 / T

    # Synodic dv0 (instantaneous burn equality of vectors)
    dv0_syn = dv0_si / V

    # 2. Propagate in BCP to apogee point
    pv_apogee = propagate(pv0, t0, [dv0_syn.tolist(), [0, 0, 0], [0, 0, 0]],
                           [T1, 0.0])
    if len(pv_apogee) == 0:
        return None

    # 3. dv1: DC to align with Moon orbit (3-var DC for arrival position match)
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)

    def residual(dv1):
        pv_arr = propagate(pv_apogee, t0 + T1,
                            [[0, 0, 0], dv1.tolist(), [0, 0, 0]],
                            [0.0, T2])
        if len(pv_arr) == 0:
            return [100.0] * 3
        return [pv_arr[0][0] - pv_tgt[0][0],
                pv_arr[0][1] - pv_tgt[0][1],
                pv_arr[0][2] - pv_tgt[0][2]]

    # Initial dv1 seed: zero (try no plane change first)
    try:
        sol = least_squares(residual, np.zeros(3), method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=80)
    except Exception:
        return None
    dv1_syn = sol.x
    if not np.all(np.isfinite(dv1_syn)):
        return None
    if np.linalg.norm(dv1_syn) > 5:  # > 5 km/s — too much
        return None

    # 4. Final arrival
    pv_arr = propagate(pv_apogee, t0 + T1,
                        [[0, 0, 0], dv1_syn.tolist(), [0, 0, 0]],
                        [0.0, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2_syn, _ = dv2_res

    # 5. Build chromosome row and validate via UDP
    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), *dv1_syn.tolist(), *dv2_syn.tolist(),
            T1, T2]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv1_syn)
              + np.linalg.norm(dv2_syn)) * V
    return mass, row, dv_ms


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Test cases: previously low-mass LEO+inclined-Moon pairs
    test_cases = [
        (0, 0, "coplanar control (sanity)"),
        (213, 19, "LEO+iE=0.20, iL=1.07 (worst)"),
        (303, 109, "LEO+iE=0.19, iL=1.08"),
        (244, 105, "LEO+iE=0.34, iL=0.50"),
        (227, 315, "LEO+iE=0.41, iL=0.47"),
    ]

    print("Testing plane-change-at-apogee 3-impulse:", flush=True)
    print(f"{'pair':>10} {'desc':<30} {'mass':>6} {'dv0':>5} {'dv1':>5} {'dv2':>5} {'tot':>5}",
          flush=True)
    for idE, idL, desc in test_cases:
        t0 = time.time()
        best = None
        # Sweep: (raan_e, argp_e, ea_dep, t0, t2_d) × DC
        for raan_e in np.linspace(0, 2 * np.pi, 4, endpoint=False):
            for argp_e in np.linspace(0, 2 * np.pi, 3, endpoint=False):
                for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                    for t0_val in (0.0, np.pi):
                        for ea_arr in (0.0, np.pi / 2, np.pi):
                            for t2_d in (1.0, 2.0, 3.0):
                                res = try_apogee_plane_change(
                                    udp, idE, idL, raan_e, argp_e, ea_dep,
                                    0.0, 0.0, ea_arr, t0_val, t2_d)
                                if res is not None and (best is None or res[0] > best[0]):
                                    best = res
        dt = time.time() - t0
        if best:
            mass, row, dv_tot = best
            dv0 = np.sqrt(row[10]**2+row[11]**2+row[12]**2) * V
            dv1 = np.sqrt(row[13]**2+row[14]**2+row[15]**2) * V
            dv2 = np.sqrt(row[16]**2+row[17]**2+row[18]**2) * V
            print(f"  ({idE:>3},{idL:>3}) {desc:<30} {mass:>6.0f} "
                  f"{dv0:>5.0f} {dv1:>5.0f} {dv2:>5.0f} {dv_tot:>5.0f} ({dt:.0f}s)",
                  flush=True)
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<30} FAIL ({dt:.0f}s)",
                  flush=True)
