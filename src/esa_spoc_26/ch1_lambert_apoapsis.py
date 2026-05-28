"""B1 v2: Lambert-to-r_apo with apolune insertion (the proper structural fix).

The previous B1 attempt (ch1_bcp_apolune.py) fell back to perilune because
the *trajectory* never reached r_apo of the target orbit — dv0 was a
Hohmann burn aimed at Moon center, giving trajectory perilune at
~50,000-200,000 km from Moon while the target's r_apo is only ~8,000 km.

This version aims dv0 explicitly at a point offset from Moon by
r_apo_target × (direction_in_Moon_orbit_plane). The spacecraft arrives
at distance ≈ r_apo from Moon with low Moon-relative velocity. From
there, `solve_arrival_eccentric` finds dv2 to match (a, e, i) of the
target Moon orbit — which absorbs both plane change AND speed match,
both cheap at apoapsis velocity.

Architecture: 2-impulse (dv0 Lambert-aimed, dv2 LOI). The dv1 mid-burn
is unused (set to 0). The spec's 3-impulse limit allows this.
"""
import numpy as np
import pykep as pk

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def _R(theta):
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def try_lambert_apoapsis(udp, idE, idL, raan_e, argp_e, ea_dep, t0,
                           tof_d, direction_angle, offset_scale=1.0):
    """B1 v2: Lambert from LEO → (Moon_pos + offset) at arrival time.

    offset = r_apo_target × offset_scale × (cos(direction_angle),
                                              sin(direction_angle), 0)
    in Moon's orbital plane (inertial xy at arrival time).
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # pv0 in inertial frame at t0 (= synodic-basis-at-t0, rotated by R(t0))
    r0_synb = np.array([(pv0[0][0] + MU) * L, pv0[0][1] * L, pv0[0][2] * L])
    v0_synb = np.array([(pv0[1][0] - pv0[0][1]) * V,
                          ((pv0[1][1] + pv0[0][0]) + MU) * V,
                          pv0[1][2] * V])
    R_t0 = _R(t0)
    r0_in = R_t0 @ r0_synb
    v0_in = R_t0 @ v0_synb

    # Moon position at arrival, in inertial frame
    tof_nondim = tof_d * 86400.0 / T
    t_arr = t0 + tof_nondim
    R_arr = _R(t_arr)
    r_moon_in = R_arr @ np.array([(1 - MU) * L, 0.0, 0.0])

    # Target offset by r_apo in chosen direction (Moon's orbital plane)
    r_apo_target = aL * (1.0 + eL) * offset_scale
    offset_in = R_arr @ np.array([r_apo_target * np.cos(direction_angle),
                                    r_apo_target * np.sin(direction_angle),
                                    0.0])
    target_in = r_moon_in + offset_in

    # Lambert in Earth-centered inertial
    try:
        lp = pk.lambert_problem(r0_in.tolist(), target_in.tolist(),
                                  tof_d * 86400.0, MU_EARTH, False, 0)
        v1_in = np.array(lp.get_v1()[0])
    except Exception:
        return None
    if not np.all(np.isfinite(v1_in)):
        return None

    dv0_in = v1_in - v0_in
    # Convert to synodic-basis-at-t0 (= R(t0)^-1 applied)
    dv0_syn = (R_t0.T @ dv0_in) / V
    if np.linalg.norm(dv0_syn) > 8:
        return None

    # Propagate BCP for TOF
    T1 = tof_nondim
    pv_arr = propagate(pv0, t0, [dv0_syn.tolist(), [0, 0, 0], [0, 0, 0]],
                        [T1, 0.0])
    if len(pv_arr) == 0:
        return None

    # solve_arrival_eccentric handles plane change + speed match
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return None
    dv2_syn, _ = res
    if not np.all(np.isfinite(dv2_syn)) or np.linalg.norm(dv2_syn) > 5:
        return None

    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), 0.0, 0.0, 0.0, *dv2_syn.tolist(),
            T1, 0.0]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv2_syn)) * V
    return mass, row, dv_ms


def sweep_lambert_apoapsis(udp, idE, idL,
                              raan_grid=None, ea_grid=None,
                              t0_grid=None, tof_grid=None,
                              dir_grid=None, scale_grid=None):
    """Grid sweep for one pair."""
    if raan_grid is None:
        raan_grid = np.linspace(0, 2 * np.pi, 4, endpoint=False)
    if ea_grid is None:
        ea_grid = (0.0, np.pi)
    if t0_grid is None:
        t0_grid = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)
    if tof_grid is None:
        tof_grid = (5.0, 7.0, 9.0, 12.0)
    if dir_grid is None:
        dir_grid = np.linspace(0, 2 * np.pi, 8, endpoint=False)
    if scale_grid is None:
        scale_grid = (0.7, 1.0, 1.3)
    best = None
    for raan_e in raan_grid:
        for ea_dep in ea_grid:
            for t0 in t0_grid:
                for tof_d in tof_grid:
                    for direction_angle in dir_grid:
                        for scale in scale_grid:
                            res = try_lambert_apoapsis(
                                udp, idE, idL, raan_e, 0.0, ea_dep,
                                t0, tof_d, direction_angle, scale)
                            if res is not None and (best is None or
                                                     res[0] > best[0]):
                                best = res
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Tests: pairs where current architecture underperforms theory
    test_cases = [
        (0, 0, "coplanar LEO+LMO", 819),  # bank 819 (LMO, eL=0 → r_apo=aL)
        (8, 175, "LEO low-iE + high-eL Moon", 599),
        (213, 19, "LEO + iL=1.07 polar", 5),
        (244, 105, "LEO + iL=0.50", 374),
        (21, 200, "LEO+high-eL mid-iL", 1095),
        (38, 157, "LEO mid-iE + high-eL", 841),
        (67, 208, "low-iE + high-eL", 540),
    ]
    print(f"B1 v2 (Lambert→r_apo + apolune insertion) test:")
    print(f"{'pair':>10} {'desc':<30} {'bank':>5} {'B1v2':>5} {'Δ':>5} {'dv0':>5} {'dv2':>5} {'time':>5}")
    for idE, idL, desc, bank_m in test_cases:
        t_start = time.time()
        best = sweep_lambert_apoapsis(udp, idE, idL)
        dt = time.time() - t_start
        if best:
            mass, row, dv_ms = best
            dv0 = np.linalg.norm(row[10:13]) * V
            dv2 = np.linalg.norm(row[16:19]) * V
            print(f"  ({idE:>3},{idL:>3}) {desc:<30} {bank_m:>5} {mass:>5.0f} "
                  f"{mass-bank_m:>+5.0f} {dv0:>5.0f} {dv2:>5.0f} {dt:>4.0f}s")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<30} {bank_m:>5}  FAIL "
                  f"({dt:.0f}s)")
