"""Scan-arrival 2-impulse: sweep t* over BCP trajectory, pick best.

Replaces the old "dv1 at perilune" architecture (B1 fix) with a direct
scan: after applying dv0 (Hohmann burn), propagate the BCP trajectory
and at each time-grid point try `solve_arrival_eccentric`. Keep the t*
giving minimum total dv (B2 fix: arrival RAAN/argp/ea fully free).

This is structurally a 2-impulse architecture (dv0 + dv2_implicit, dv1=0).
For high-eL Moon orbits, the right t* is the spacecraft's natural
*apolune* (far from Moon, slow) or wherever solve_arrival_eccentric
yields lowest dv2.

For LMO targets, t* will naturally settle at perilune.
"""
import numpy as np

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def _hohmann_dv0_synbasis(pv0):
    """Pure prograde Hohmann burn from LEO position, synodic basis at t0=any.

    Uses the state2earth convention (no R(t) rotation), so result is
    directly applicable as synodic Δv regardless of t0. Avoids the t0=π
    flip bug in syn_to_inertial_earth.
    """
    [x, y, z], [vx, vy, vz] = pv0
    rx = (x + MU) * L
    ry = y * L
    rz = z * L
    r0 = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
    # v_inertial in synodic basis at instant
    vx_e = (vx - y) * V
    vy_e = ((vy + x) + MU) * V
    vz_e = vz * V
    v_mag = np.sqrt(vx_e ** 2 + vy_e ** 2 + vz_e ** 2)
    a_trans = (r0 + R_MOON_SI) / 2
    v_peri = np.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_trans))
    scale = (v_peri - v_mag) / v_mag
    return np.array([vx_e * scale, vy_e * scale, vz_e * scale]) / V


def try_scan_arrival(udp, idE, idL, raan_e, argp_e, ea_dep, t0,
                       t_max_d=20.0, n_samples=80):
    """Hohmann + scan-arrival 2-impulse.

    Returns (mass, row, dv_ms) or None.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    dv0_syn = _hohmann_dv0_synbasis(pv0)
    if not np.all(np.isfinite(dv0_syn)) or np.linalg.norm(dv0_syn) > 8:
        return None

    # Determine Moon-orbit r range for early-exit filter
    r_peri_target = aL * (1 - eL)
    r_apo_target = aL * (1 + eL)

    # Cached integrator
    ta = _ta()
    ta.time = t0
    ta.state[0] = pv0[0][0]
    ta.state[1] = pv0[0][1]
    ta.state[2] = pv0[0][2]
    ta.state[3] = pv0[1][0] + dv0_syn[0]
    ta.state[4] = pv0[1][1] + dv0_syn[1]
    ta.state[5] = pv0[1][2] + dv0_syn[2]

    t_max_nondim = t_max_d * 86400.0 / T
    R_EARTH_2 = ((6378e3 + 99000) / L) ** 2
    R_MOON_2 = ((1737400 + 30000) / L) ** 2

    # Walk forward, evaluating solve_arrival at each sample
    best = None  # (mass, row, dv_ms, t_star)
    dt = t_max_nondim / n_samples

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

        # Spacecraft-Moon distance (nondim)
        r_moon_nondim = np.sqrt((x - 1 + MU) ** 2 + y * y + z * z)
        r_moon_si = r_moon_nondim * L
        # Early skip if obviously out of range
        if r_moon_si < r_peri_target - L * 1e-2 or \
           r_moon_si > r_apo_target + L * 1e-2:
            continue

        pv_arr = [[float(ta.state[0]), float(ta.state[1]), float(ta.state[2])],
                  [float(ta.state[3]), float(ta.state[4]), float(ta.state[5])]]
        res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
        if res is None:
            continue
        dv2_syn, _ = res
        if not np.all(np.isfinite(dv2_syn)) or np.linalg.norm(dv2_syn) > 5:
            continue

        T1 = k * dt  # nondim time from t0
        row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
                *dv0_syn.tolist(), 0.0, 0.0, 0.0, *dv2_syn.tolist(),
                T1, 0.0]
        chr_padded = list(row)
        pad = (udp.dim - len(chr_padded)) // 21
        for _ in range(pad):
            chr_padded.extend([-1.0] + [0.0] * 20)
        f = udp.fitness(chr_padded)[0]
        if f >= 0:
            continue
        mass = -f
        dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv2_syn)) * V
        if best is None or mass > best[0]:
            best = (mass, row, dv_ms, T1)

    if best is None:
        return None
    return best[0], best[1], best[2]


def sweep_scan_arrival(udp, idE, idL):
    """Grid sweep (raan_e, argp_e, ea_dep, t0) — uses the *natural* perilune
    that the existing grid already explored, so this should at least match
    the old solver for cases where dv1=0 was optimal."""
    best = None
    for raan_e in np.linspace(0, 2 * np.pi, 6, endpoint=False):
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
                for t0_val in (0.0, np.pi):
                    res = try_scan_arrival(udp, idE, idL, raan_e, argp_e,
                                              ea_dep, t0_val)
                    if res is not None and (best is None or res[0] > best[0]):
                        best = res
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar LMO (bank 819)"),
        (213, 19, "LEO low-iE + iL=1.07 (bank 5)"),
        (244, 105, "LEO + iL=0.50 (bank 374)"),
        (21, 200, "LEO + high-eL mid-iL (bank 1095)"),
        (277, 189, "GEO + high-eL (bank 2628)"),
    ]
    print(f"{'pair':>10} {'desc':<40} {'mass':>5}  {'time':>5}")
    for idE, idL, desc in test_cases:
        t0_start = time.time()
        best = sweep_scan_arrival(udp, idE, idL)
        dt = time.time() - t0_start
        if best:
            print(f"  ({idE:>3},{idL:>3}) {desc:<40} {best[0]:>5.0f}  {dt:>5.1f}s")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<40}  FAIL  {dt:>5.1f}s")
