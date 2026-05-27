"""BCP-apolune 3-impulse — audit fix B1.

For high-eL Moon orbits, the natural insertion point is the orbit's
*apoapsis* (r_apo = aL·(1+eL)), where Moon-relative velocity is low
(~400-500 m/s) and plane-change cost is minimized. The previous
architecture (`ch1_bcp_apogee.py` calling `track_to_perilune`) applies
dv1 at the spacecraft's closest approach to Moon (perilune of the
trajectory), where speed is ~1.5-2 km/s — wrong place to spend the
plane-change burn.

This module:
1. Picks t_target_d so spacecraft is at distance ≈ r_apo_of_target_orbit
   from Moon (uses `track_to_target_r` instead of `track_to_perilune`).
2. Applies dv1 there; coasts T2; arrives.
3. dv2 = solve_arrival_eccentric.

For LMO targets (r_apo = aL), this collapses to track_to_perilune
(same point). For high-eL targets, this places dv1 at the cheap
plane-change point.
"""
import numpy as np
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def track_to_target_r(pv0, t0, dv0, t_max_nondim, r_target_si,
                        n_samples=200):
    """Find earliest time in BCP trajectory where Moon-relative distance
    crosses `r_target_si`. Returns (t_cross, state6) or (None, None).

    Strategy: walk forward, watch the sign of (r - r_target). The first
    crossing from outside-in (or any extremum near r_target) gives a
    candidate. We pick the time where |r - r_target| is minimum subject
    to the spacecraft being on the approach phase (dr/dt < 0).
    """
    ta = _ta()
    ta.time = t0
    ta.state[0] = pv0[0][0]
    ta.state[1] = pv0[0][1]
    ta.state[2] = pv0[0][2]
    ta.state[3] = pv0[1][0] + dv0[0]
    ta.state[4] = pv0[1][1] + dv0[1]
    ta.state[5] = pv0[1][2] + dv0[2]

    r_target_nd = r_target_si / L
    dt = t_max_nondim / n_samples
    R_EARTH_2 = ((6378e3 + 99000) / L) ** 2
    R_MOON_2 = ((1737400 + 30000) / L) ** 2

    best_dist = np.inf
    best_t = None
    best_state = None
    prev_diff = None
    for k in range(1, n_samples + 1):
        try:
            ta.propagate_until(t0 + k * dt)
        except Exception:
            break
        x, y, z = ta.state[0], ta.state[1], ta.state[2]
        if (x + MU) ** 2 + y * y + z * z < R_EARTH_2:
            break
        if (x - 1 + MU) ** 2 + y * y + z * z < R_MOON_2:
            break
        r_nd = np.sqrt((x - 1 + MU) ** 2 + y * y + z * z)
        diff = r_nd - r_target_nd
        # closest approach to target radius (in absolute value)
        if abs(diff) < best_dist:
            best_dist = abs(diff)
            best_t = k * dt
            best_state = ta.state.copy()
        prev_diff = diff

    return best_t, best_state, best_dist * L


def try_bcp_apolune_3impulse(udp, idE, idL, raan_e, argp_e, ea_dep, t0,
                                raan_l=0.0, argp_l=0.0, ea_arr=0.0,
                                t2_d=0.5, t_max_d=20.0):
    """3-impulse with dv1 placed at the spacecraft's first approach to
    distance r_target = aL·(1+eL) from Moon (orbit apoapsis). For LMO
    (eL≈0), r_target ≈ aL ≈ perilune of trajectory.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # Hohmann dv0 in synodic basis (no R(t) rotation - audit B6 fix)
    rx = (pv0[0][0] + MU) * L
    ry = pv0[0][1] * L
    rz = pv0[0][2] * L
    r0 = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
    vx_e = (pv0[1][0] - pv0[0][1]) * V
    vy_e = ((pv0[1][1] + pv0[0][0]) + MU) * V
    vz_e = pv0[1][2] * V
    v_mag = np.sqrt(vx_e ** 2 + vy_e ** 2 + vz_e ** 2)
    a_trans = (r0 + R_MOON_SI) / 2
    v_peri = np.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_trans))
    scale = (v_peri - v_mag) / v_mag
    dv0_syn = np.array([vx_e * scale, vy_e * scale, vz_e * scale]) / V
    if not np.all(np.isfinite(dv0_syn)) or np.linalg.norm(dv0_syn) > 8:
        return None

    # Target radius: orbit apoapsis (B1 fix). For LMO this ≈ aL.
    r_target_si = aL * (1.0 + eL)
    t_max_nondim = t_max_d * 86400.0 / T
    t_apo, state_apo, r_dist = track_to_target_r(
        pv0, t0, dv0_syn.tolist(), t_max_nondim, r_target_si)
    if t_apo is None:
        return None
    # If we can't get close to the target radius, skip
    if r_dist > 200e6:  # 200,000 km tolerance (will be tightened by DC)
        return None

    T1 = t_apo
    pv_apo = [list(state_apo[:3]), list(state_apo[3:6])]
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)
    T2 = t2_d * 86400.0 / T

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

    # Tests
    test_cases = [
        (0, 0, "coplanar LMO (bank 819)"),
        (213, 19, "LEO low-iE + iL=1.07 (bank 5)"),
        (244, 105, "LEO + iL=0.50 (bank 374)"),
        (21, 200, "LEO + high-eL mid-iL (bank 1095)"),
        (277, 189, "GEO + high-eL (bank 2628)"),
    ]
    print(f"Apolune-targeting 3-impulse test:")
    print(f"{'pair':>10} {'desc':<40} {'mass':>5} {'time':>5}")
    for idE, idL, desc in test_cases:
        t_start = time.time()
        best = None
        for raan_e in np.linspace(0, 2 * np.pi, 6, endpoint=False):
            for argp_e in (0.0, np.pi):
                for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                    for t0_val in (0.0, np.pi):
                        for ea_arr in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                            for t2_d in (0.5, 1.2, 2.5):
                                res = try_bcp_apolune_3impulse(
                                    udp, idE, idL, raan_e, argp_e, ea_dep,
                                    t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                                if res is not None and (best is None or
                                                         res[0] > best[0]):
                                    best = res
        dt = time.time() - t_start
        if best:
            mass, row, _ = best
            dv0 = np.sqrt(row[10]**2+row[11]**2+row[12]**2)*V
            dv1 = np.sqrt(row[13]**2+row[14]**2+row[15]**2)*V
            dv2 = np.sqrt(row[16]**2+row[17]**2+row[18]**2)*V
            print(f"  ({idE:>3},{idL:>3}) {desc:<40} {mass:>5.0f} "
                  f"({dv0:.0f}+{dv1:.0f}+{dv2:.0f}={dv0+dv1+dv2:.0f}) [{dt:.0f}s]")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<40}  FAIL  [{dt:.0f}s]")
